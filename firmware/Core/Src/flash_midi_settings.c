/*
 * flash_midi_settings.c
 *
 *  Created on: 12 Jul 2021
 *      Author: D Harvie
 *
 * Configuration slots. Every access to the configuration goes through the
 * pointers below, so switching slot is a matter of repointing them; see
 * flash_settings_select(). The tools erase, write and read the "target" slot,
 * which follows the active one unless SysEx SELECT_SLOT picked another.
 */

#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"

uint8_t *pGlobalSettings = (uint8_t*)(FLASH_SLOT0_ADDR);
uint8_t *pBankStrings    = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_BANK_STRINGS_OFF);
uint8_t *pSwitchCmds     = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_CMDS_OFF);
uint8_t *pButtonLedModes = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_LED_MODES_OFF);
uint8_t *pButtonLabels   = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_LABELS_OFF);
uint8_t *pLongPressCmds  = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_LONG_CMDS_OFF);
uint8_t *pDoublePressCmds = (uint8_t*)(FLASH_EXT_ADDR(0));
uint8_t *pExpSettings    = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_EXP_OFF);
uint8_t *pBankEnterCmds  = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_BANK_ENTER_OFF);
uint8_t *pSysExStrings   = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_SYSEX_OFF);
uint8_t *pBankSwitchCmds = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_BANK_SWITCH_OFF);
uint8_t *pSetlist        = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_SETLIST_OFF);
uint8_t *pBankExpSettings = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_BANK_EXP_OFF);

// The whole configuration must fit in the pages the tools erase and write.
_Static_assert(CFG_TOTAL_SIZE <= FLASH_SETTINGS_SIZE,
		"configuration does not fit in FLASH_SETTINGS_NO_PAGES pages");
// All four slots must fit below 256 kB, the smallest chip the firmware accepts.
_Static_assert(FLASH_SLOTN_ADDR(CONFIG_SLOTS) <= FLASH_BASE + 256U * 1024U,
		"configuration slots do not fit in 256 kB");
_Static_assert(CFG_PAGE_SIZE == FLASH_PAGE_SIZE, "CFG_PAGE_SIZE must be the flash page size");
_Static_assert(CFG_DOUBLE_CMDS_SIZE <= FLASH_DOUBLE_PAGES * FLASH_PAGE_SIZE,
		"double press commands do not fit in the extension pages");
_Static_assert(FLASH_EXT_ADDR(CONFIG_SLOTS) <= FLASH_SLOT0_ADDR,
		"extension areas run into slot 0");

static uint8_t active_slot = 0;
static uint8_t target_slot = 0;

static uint32_t slot_base(uint8_t slot){
	return (slot == 0) ? FLASH_SLOT0_ADDR : FLASH_SLOTN_ADDR(slot);
}

uint8_t flash_settings_active_slot(void){ return active_slot; }
uint8_t flash_settings_target_slot(void){ return target_slot; }

void flash_settings_set_target(uint8_t slot){
	if(slot < CONFIG_SLOTS) target_slot = slot;
}

const uint8_t *flash_settings_target_base(void){
	return (const uint8_t*)slot_base(target_slot);
}

bool flash_settings_double_stored(void){
	return pGlobalSettings[GLOBAL_SETTINGS_DOUBLE_STORED] == 1;
}

/*
 * Where 16 bytes at a tools offset live: the slot's own pages, or past them the
 * slot's extension area. 0 when the chunk is outside both.
 */
static uint32_t image_address(uint8_t slot, uint32_t offset){
	if(offset + 16 <= FLASH_SETTINGS_SIZE){
		return slot_base(slot) + offset;
	}
	if(offset >= CFG_DOUBLE_CMDS_OFF && offset + 16 <= FLASH_IMAGE_SIZE){
		return FLASH_EXT_ADDR(slot) + (offset - CFG_DOUBLE_CMDS_OFF);
	}
	return 0;
}

const uint8_t *flash_settings_target_ptr(uint32_t offset){
	uint32_t address = image_address(target_slot, offset);
	return address ? (const uint8_t*)address : NULL;
}

/*
 * A slot holds a configuration when its ConfigName is 16 printable
 * characters: the tools always pad the name with spaces, whereas erased flash
 * (0xFF) or whatever an older firmware left behind does not pass.
 */
bool flash_settings_slot_valid(uint8_t slot){
	if(slot >= CONFIG_SLOTS) return false;
	const uint8_t *g = (const uint8_t*)slot_base(slot);
	for(int i=16; i<32; i++){
		if(g[i] < 0x20 || g[i] > 0x7E) return false;
	}
	return true;
}

uint8_t flash_settings_valid_mask(void){
	uint8_t mask = 0;
	for(uint8_t s=0; s<CONFIG_SLOTS; s++){
		if(flash_settings_slot_valid(s)) mask |= (uint8_t)(1U << s);
	}
	return mask;
}

bool flash_settings_select(uint8_t slot){
	if(slot >= CONFIG_SLOTS) return false;
	uint32_t b = slot_base(slot);
	pGlobalSettings = (uint8_t*)(b);
	pBankStrings    = (uint8_t*)(b + CFG_BANK_STRINGS_OFF);
	pSwitchCmds     = (uint8_t*)(b + CFG_CMDS_OFF);
	pButtonLedModes = (uint8_t*)(b + CFG_LED_MODES_OFF);
	pButtonLabels   = (uint8_t*)(b + CFG_LABELS_OFF);
	pLongPressCmds  = (uint8_t*)(b + CFG_LONG_CMDS_OFF);
	pDoublePressCmds = (uint8_t*)(FLASH_EXT_ADDR(slot));
	pExpSettings    = (uint8_t*)(b + CFG_EXP_OFF);
	pBankEnterCmds  = (uint8_t*)(b + CFG_BANK_ENTER_OFF);
	pSysExStrings   = (uint8_t*)(b + CFG_SYSEX_OFF);
	pBankSwitchCmds = (uint8_t*)(b + CFG_BANK_SWITCH_OFF);
	pSetlist        = (uint8_t*)(b + CFG_SETLIST_OFF);
	pBankExpSettings = (uint8_t*)(b + CFG_BANK_EXP_OFF);
	active_slot = slot;
	target_slot = slot;
	return true;
}

void flash_settings_erase(void){
	// Erase the pages of the target slot. Must be done before re-writing them.
	uint32_t pageError;

	FLASH_EraseInitTypeDef eraseInit ={
			.TypeErase = FLASH_TYPEERASE_PAGES,
			.Banks = FLASH_BANK_1,
			.PageAddress = slot_base(target_slot),
			.NbPages = FLASH_SETTINGS_NO_PAGES
	};

	HAL_FLASH_Unlock();
	HAL_StatusTypeDef status = HAL_FLASHEx_Erase(&eraseInit, &pageError);
	// The extension area belongs to the slot too: a tool that writes no double
	// press commands must not leave the previous ones behind
	if(status == HAL_OK){
		eraseInit.PageAddress = FLASH_EXT_ADDR(target_slot);
		eraseInit.NbPages = FLASH_DOUBLE_PAGES;
		status = HAL_FLASHEx_Erase(&eraseInit, &pageError);
	}
	HAL_FLASH_Lock();

	if(status != HAL_OK){
		Error("Flash erase error");
	}
}

void flash_settings_write(uint8_t* data, uint32_t offset){
	// Never write outside the slot: the offset comes straight from a SysEx message
	uint32_t flash_address = image_address(target_slot, offset);
	if(flash_address == 0){
		return;
	}

	HAL_FLASH_Unlock();

	// Programming 16bytes, so 8 iterations of 16bit
	for(int i=0; i<8; i++){
		uint16_t write_data = data[2*i] + (data[2*i+1] << 8);
		HAL_StatusTypeDef status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, flash_address + 2*i, write_data);
		if(status != HAL_OK){
			Error("Flash write error");
		}
	}

	HAL_FLASH_Lock();
}
