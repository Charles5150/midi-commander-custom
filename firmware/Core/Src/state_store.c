/*
 * state_store.c
 *
 * Journal of (toggle states, bank) entries in one dedicated flash page.
 *
 * Flash bits can only be cleared by programming, so instead of rewriting one
 * slot we append a new entry each time and erase the page only when it is
 * full. With MIDI_NUM_BANKS banks an entry holds two 32-bit masks per button,
 * so a 2 kB page still fits enough entries to spread the 10k erase cycle
 * endurance over hundreds of thousands of saves.
 *
 * Entry layout (halfword writes, 2 byte aligned):
 *   [0 .. 4n-1]   short press toggle masks, one uint32 LE per button
 *   [4n .. 8n-1]  same for the long press command sets
 *   [8n]          bank number
 *   [8n+1]        marker, written together with the bank as the final
 *                 halfword so a torn write leaves an entry that is skipped
 *
 * The marker doubles as a format version: entries written by firmware with a
 * different layout carry another marker and are ignored.
 */

#include "state_store.h"
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "switch_router.h"
#include <string.h>

#define STATE_STORE_ADDR	(FLASH_BASE + (1024U * 128U) + FLASH_SETTINGS_NO_PAGES * FLASH_PAGE_SIZE)
#define STATE_MASK_BYTES	(MIDI_NUM_SWITCHES * 4U)		// one uint32 per button
#define STATE_BANK_OFF		(2U * STATE_MASK_BYTES)
#define STATE_ENTRY_SIZE	(STATE_BANK_OFF + 2U)
#define STATE_ENTRIES		(FLASH_PAGE_SIZE / STATE_ENTRY_SIZE)
#define STATE_MARKER		(0xA7U)
#define STATE_SAVE_DELAY_MS	(2000U)

static uint32_t next_free = STATE_ENTRIES + 1; // Forces a scan on first use
static uint8_t last_saved_bank = 0xFF;
static uint32_t last_saved_toggles[MIDI_NUM_SWITCHES];
static uint32_t last_saved_long[MIDI_NUM_SWITCHES];
static volatile uint8_t dirty = 0;
static volatile uint32_t dirty_since = 0;

static inline const uint8_t *entry_ptr(uint32_t index){
	return (const uint8_t*)(STATE_STORE_ADDR + index * STATE_ENTRY_SIZE);
}

static bool entry_is_blank(const uint8_t *e){
	for(uint32_t i=0; i<STATE_ENTRY_SIZE; i++){
		if(e[i] != 0xFF) return false;
	}
	return true;
}

static bool entry_is_valid(const uint8_t *e){
	return e[STATE_BANK_OFF + 1] == STATE_MARKER && e[STATE_BANK_OFF] < MIDI_NUM_BANKS;
}

static void read_masks(const uint8_t *src, uint32_t *out){
	for(uint32_t i=0; i<MIDI_NUM_SWITCHES; i++){
		out[i] = (uint32_t)src[4*i] | ((uint32_t)src[4*i+1] << 8)
		       | ((uint32_t)src[4*i+2] << 16) | ((uint32_t)src[4*i+3] << 24);
	}
}

// Scan the page once: find the latest valid entry and the first blank slot.
static void scan(void){
	next_free = STATE_ENTRIES;
	last_saved_bank = 0xFF;
	for(uint32_t i=0; i<STATE_ENTRIES; i++){
		const uint8_t *e = entry_ptr(i);
		if(entry_is_blank(e)){
			next_free = i;
			break;
		}
		if(entry_is_valid(e)){
			last_saved_bank = e[STATE_BANK_OFF];
			read_masks(e, last_saved_toggles);
			read_masks(e + STATE_MASK_BYTES, last_saved_long);
		}
	}
}

static inline bool enabled(void){
	return pGlobalSettings[GLOBAL_SETTINGS_REMEMBER_STATE] == 1;
}

bool state_store_load(uint8_t *bank, uint32_t toggles[8], uint32_t long_toggles[8]){
	scan();
	if(last_saved_bank == 0xFF){
		return false;
	}
	*bank = last_saved_bank;
	memcpy(toggles, last_saved_toggles, sizeof(last_saved_toggles));
	memcpy(long_toggles, last_saved_long, sizeof(last_saved_long));
	return true;
}

void state_store_mark_dirty(void){
	dirty = 1;
	dirty_since = HAL_GetTick();
}

static void erase_page(void){
	uint32_t pageError;
	FLASH_EraseInitTypeDef eraseInit = {
			.TypeErase = FLASH_TYPEERASE_PAGES,
			.Banks = FLASH_BANK_1,
			.PageAddress = STATE_STORE_ADDR,
			.NbPages = 1
	};
	HAL_FLASHEx_Erase(&eraseInit, &pageError);
}

static void write_entry(uint8_t bank, const uint32_t *toggles, const uint32_t *long_toggles){
	// Flash programming stalls the CPU anyway; disabling interrupts keeps a
	// SysEx flash write arriving over USB from re-entering the HAL flash lock.
	__disable_irq();
	HAL_FLASH_Unlock();

	if(next_free >= STATE_ENTRIES){
		erase_page();
		next_free = 0;
	}

	uint32_t addr = STATE_STORE_ADDR + next_free * STATE_ENTRY_SIZE;
	HAL_StatusTypeDef status = HAL_OK;
	for(uint32_t i=0; i<MIDI_NUM_SWITCHES && status == HAL_OK; i++){
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + 4*i, toggles[i] & 0xFFFF);
		if(status == HAL_OK){
			status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + 4*i + 2, toggles[i] >> 16);
		}
	}
	for(uint32_t i=0; i<MIDI_NUM_SWITCHES && status == HAL_OK; i++){
		uint32_t a = addr + STATE_MASK_BYTES + 4*i;
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, a, long_toggles[i] & 0xFFFF);
		if(status == HAL_OK){
			status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, a + 2, long_toggles[i] >> 16);
		}
	}
	if(status == HAL_OK){
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + STATE_BANK_OFF,
				bank | (STATE_MARKER << 8));
	}

	HAL_FLASH_Lock();
	__enable_irq();

	next_free++;
	if(status == HAL_OK){
		last_saved_bank = bank;
		memcpy(last_saved_toggles, toggles, sizeof(last_saved_toggles));
		memcpy(last_saved_long, long_toggles, sizeof(last_saved_long));
	}
}

void state_store_task(void){
	if(!dirty || !enabled()){
		dirty = 0;
		return;
	}
	if(HAL_GetTick() - dirty_since < STATE_SAVE_DELAY_MS){
		return;
	}
	dirty = 0;

	uint8_t bank = sw_get_current_page();
	uint32_t toggles[MIDI_NUM_SWITCHES], long_toggles[MIDI_NUM_SWITCHES];
	sw_get_toggle_states(toggles);
	sw_get_long_toggle_states(long_toggles);

	if(bank == last_saved_bank
			&& memcmp(toggles, last_saved_toggles, sizeof(last_saved_toggles)) == 0
			&& memcmp(long_toggles, last_saved_long, sizeof(last_saved_long)) == 0){
		return; // Nothing changed since the last save
	}
	if(next_free > STATE_ENTRIES){
		scan();
	}
	write_entry(bank, toggles, long_toggles);
}
