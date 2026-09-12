/*
 * state_store.c
 *
 * Journal of (bank, toggle states) entries in one dedicated flash page.
 *
 * Flash bits can only be cleared by programming, so instead of rewriting
 * one slot we append a new entry each time and erase the page only when it
 * is full. With 10 byte entries a 2 kB page holds 204 saves per erase cycle,
 * which spreads the 10k erase cycle endurance over about two million saves.
 *
 * Entry layout (halfword writes, 2 byte aligned):
 *   bytes 0..7  toggle state bitmask of buttons 1,2,3,4,A,B,C,D (bit n = bank n)
 *   byte  8     bank number 0..7
 *   byte  9     marker 0xA5, written together with the bank as the final
 *               halfword so a torn write leaves an entry that is skipped
 */

#include "state_store.h"
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "switch_router.h"
#include <string.h>

#define STATE_STORE_ADDR	(FLASH_BASE + (1024U * 128U) + FLASH_SETTINGS_NO_PAGES * FLASH_PAGE_SIZE)
#define STATE_ENTRY_SIZE	(10U)
#define STATE_ENTRIES		(FLASH_PAGE_SIZE / STATE_ENTRY_SIZE)
#define STATE_MARKER		(0xA5U)
#define STATE_SAVE_DELAY_MS	(2000U)

static uint32_t next_free = STATE_ENTRIES; // Forces a scan on first use
static uint8_t last_saved_bank = 0xFF;
static uint8_t last_saved_toggles[8];
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
	return e[9] == STATE_MARKER && e[8] < MIDI_NUM_BANKS;
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
			last_saved_bank = e[8];
			memcpy(last_saved_toggles, e, 8);
		}
	}
}

static inline bool enabled(void){
	return pGlobalSettings[GLOBAL_SETTINGS_REMEMBER_STATE] == 1;
}

bool state_store_load(uint8_t *bank, uint8_t toggles[8]){
	scan();
	if(last_saved_bank == 0xFF){
		return false;
	}
	*bank = last_saved_bank;
	memcpy(toggles, last_saved_toggles, 8);
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

static void write_entry(uint8_t bank, const uint8_t toggles[8]){
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
	if(status == HAL_OK){
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + 8, bank | (STATE_MARKER << 8));
	}

	HAL_FLASH_Lock();
	__enable_irq();

	next_free++;
	if(status == HAL_OK){
		last_saved_bank = bank;
		memcpy(last_saved_toggles, toggles, 8);
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
	uint8_t toggles[8];
	sw_get_toggle_states(toggles);

	if(bank == last_saved_bank && memcmp(toggles, last_saved_toggles, 8) == 0){
		return; // Nothing changed since the last save
	}
	if(next_free > STATE_ENTRIES){
		scan();
	}
	write_entry(bank, toggles);
}
