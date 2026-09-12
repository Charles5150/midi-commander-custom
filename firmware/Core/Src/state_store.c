/*
 * state_store.c
 *
 * Journal of (toggle states, bank) entries in one dedicated flash page.
 *
 * Flash bits can only be cleared by programming, so instead of rewriting
 * one slot we append a new entry each time and erase the page only when it
 * is full. With 18 byte entries a 2 kB page holds 113 saves per erase cycle,
 * which spreads the 10k erase cycle endurance over about a million saves.
 *
 * Entry layout (halfword writes, 2 byte aligned):
 *   bytes  0..7   toggle state bitmask of buttons 1,2,3,4,A,B,C,D (bit n = bank n)
 *   bytes  8..15  same for the long press command sets
 *   byte  16      bank number 0..7
 *   byte  17      marker, written together with the bank as the final
 *                 halfword so a torn write leaves an entry that is skipped
 *
 * The marker doubles as a format version: entries written by older firmware
 * with a different layout carry another marker and are ignored.
 */

#include "state_store.h"
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "switch_router.h"
#include <string.h>

#define STATE_STORE_ADDR	(FLASH_BASE + (1024U * 128U) + FLASH_SETTINGS_NO_PAGES * FLASH_PAGE_SIZE)
#define STATE_ENTRY_SIZE	(18U)
#define STATE_ENTRIES		(FLASH_PAGE_SIZE / STATE_ENTRY_SIZE)
#define STATE_MARKER		(0xA6U)
#define STATE_SAVE_DELAY_MS	(2000U)

static uint32_t next_free = STATE_ENTRIES + 1; // Forces a scan on first use
static uint8_t last_saved_bank = 0xFF;
static uint8_t last_saved_toggles[8];
static uint8_t last_saved_long[8];
static volatile uint8_t dirty = 0;
static volatile uint32_t dirty_since = 0;

static inline const uint8_t *entry_ptr(uint32_t index){
	return (const uint8_t*)(STATE_STORE_ADDR + index * STATE_ENTRY_SIZE);
}

static bool entry_is_blank(const uint8_t *e){
	for(int i=0; i<STATE_ENTRY_SIZE; i++){
		if(e[i] != 0xFF) return false;
	}
	return true;
}

static bool entry_is_valid(const uint8_t *e){
	return e[17] == STATE_MARKER && e[16] < MIDI_NUM_BANKS;
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
			last_saved_bank = e[16];
			memcpy(last_saved_toggles, e, 8);
			memcpy(last_saved_long, e + 8, 8);
		}
	}
}

static inline bool enabled(void){
	return pGlobalSettings[GLOBAL_SETTINGS_REMEMBER_STATE] == 1;
}

bool state_store_load(uint8_t *bank, uint8_t toggles[8], uint8_t long_toggles[8]){
	scan();
	if(last_saved_bank == 0xFF){
		return false;
	}
	*bank = last_saved_bank;
	memcpy(toggles, last_saved_toggles, 8);
	memcpy(long_toggles, last_saved_long, 8);
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

static void write_entry(uint8_t bank, const uint8_t toggles[8], const uint8_t long_toggles[8]){
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
	for(int i=0; i<4 && status == HAL_OK; i++){
		uint16_t hw = toggles[2*i] | (toggles[2*i+1] << 8);
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + 2*i, hw);
	}
	for(int i=0; i<4 && status == HAL_OK; i++){
		uint16_t hw = long_toggles[2*i] | (long_toggles[2*i+1] << 8);
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + 8 + 2*i, hw);
	}
	if(status == HAL_OK){
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + 16, bank | (STATE_MARKER << 8));
	}

	HAL_FLASH_Lock();
	__enable_irq();

	next_free++;
	if(status == HAL_OK){
		last_saved_bank = bank;
		memcpy(last_saved_toggles, toggles, 8);
		memcpy(last_saved_long, long_toggles, 8);
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
	uint8_t toggles[8], long_toggles[8];
	sw_get_toggle_states(toggles);
	sw_get_long_toggle_states(long_toggles);

	if(bank == last_saved_bank
			&& memcmp(toggles, last_saved_toggles, 8) == 0
			&& memcmp(long_toggles, last_saved_long, 8) == 0){
		return; // Nothing changed since the last save
	}
	if(next_free > STATE_ENTRIES){
		scan();
	}
	write_entry(bank, toggles, long_toggles);
}
