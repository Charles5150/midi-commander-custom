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

#include <string.h>

#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "tempo.h"

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
uint8_t *pBankExpRange   = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_BANK_EXP_RANGE_OFF);
uint8_t *pCycleLabels    = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_CYCLE_LABELS_OFF);
uint8_t *pCombos         = (uint8_t*)(FLASH_SLOT0_ADDR + CFG_COMBOS_OFF);

// The whole configuration must fit in the pages the tools erase and write.
_Static_assert(CFG_TOTAL_SIZE <= FLASH_SETTINGS_SIZE,
		"configuration does not fit in FLASH_SETTINGS_NO_PAGES pages");
// All four slots must fit below 256 kB, the smallest chip the firmware accepts.
_Static_assert(FLASH_SLOTN_ADDR(CONFIG_SLOTS) <= FLASH_BASE + 256U * 1024U,
		"configuration slots do not fit in 256 kB");
_Static_assert(FLASH_BANNER_ADDR + FLASH_PAGE_SIZE <= FLASH_BASE + 256U * 1024U,
		"the banner page does not fit in 256 kB");
_Static_assert(CFG_PAGE_SIZE == FLASH_PAGE_SIZE, "CFG_PAGE_SIZE must be the flash page size");
_Static_assert(CFG_DOUBLE_CMDS_SIZE <= FLASH_DOUBLE_PAGES * FLASH_PAGE_SIZE,
		"double press commands do not fit in the extension pages");
_Static_assert(FLASH_EXT_ADDR(CONFIG_SLOTS) <= FLASH_SLOT0_ADDR,
		"extension areas run into slot 0");
_Static_assert(FLASH_EXT2_ADDR(CONFIG_SLOTS) <= FLASH_BASE + 256U * 1024U,
		"second extension areas do not fit in 256 kB");
_Static_assert(EXT2_MAP_OFF + MIDI_MAP_COUNT * MIDI_MAP_STRIDE <= FLASH_EXT2_PAGES * FLASH_PAGE_SIZE,
		"the MIDI map does not fit in the second extension area");
_Static_assert(EXT2_LONG_LABELS_OFF + CFG_BUTTONS * BUTTON_LABEL_LEN <= FLASH_EXT2_PAGES * FLASH_PAGE_SIZE,
		"the long press labels do not fit in the second extension area");

_Static_assert(PATCH_LOG_ADDR + FLASH_PAGE_SIZE <= FLASH_BASE + 256U * 1024U,
		"the page patch copy and log do not fit in 256 kB");

static uint8_t active_slot = 0;
static uint8_t target_slot = 0;
// A tool chose the target: it no longer follows configuration switches, so an
// upload keeps writing where it started
static bool target_chosen = false;
// An erase or a write since the pedal started, and when the last one came
static volatile bool upload_on = false;
static volatile uint32_t upload_at;

static uint32_t slot_base(uint8_t slot){
	return (slot == 0) ? FLASH_SLOT0_ADDR : FLASH_SLOTN_ADDR(slot);
}

uint8_t flash_settings_active_slot(void){ return active_slot; }
uint8_t flash_settings_target_slot(void){ return target_slot; }

void flash_settings_set_target(uint8_t slot){
	if(slot < CONFIG_SLOTS){
		target_slot = slot;
		target_chosen = true;
	}
}

static void upload_touch(void){
	upload_at = HAL_GetTick();
	upload_on = true;
}

bool flash_settings_uploading(void){ return upload_on; }

/*
 * upload_at is written by the USB interrupt, so it is read before the tick: a
 * write landing in between then only makes it older than it is. Read the
 * other way round, a write between the two made the difference negative,
 * which as unsigned is some 50 days, and the pedal took the tool for gone
 * and restarted halfway through the upload (#147).
 */
bool flash_settings_upload_idle(uint32_t ms){
	if(!upload_on) return false;
	uint32_t at = upload_at;
	return (int32_t)(HAL_GetTick() - at) > (int32_t)ms;
}

void flash_settings_upload_end(void){ upload_on = false; }

const uint8_t *flash_settings_target_base(void){
	return (const uint8_t*)slot_base(target_slot);
}

bool flash_settings_double_stored(void){
	return pGlobalSettings[GLOBAL_SETTINGS_DOUBLE_STORED] == 1;
}

static const uint8_t *ext2_part(uint16_t offset){
	const uint8_t *ext = (const uint8_t*)FLASH_EXT2_ADDR(active_slot);
	return *(const uint32_t*)ext == EXT2_MARKER ? ext + offset : NULL;
}

const uint8_t *flash_settings_midi_map(void){
	return ext2_part(EXT2_MAP_OFF);
}

const uint8_t *flash_settings_long_labels(void){
	return ext2_part(EXT2_LONG_LABELS_OFF);
}

/*
 * Where 16 bytes at a tools offset live: the slot's own pages, or past them the
 * slot's extension areas. 0 when the chunk is outside all of them.
 */
static uint32_t image_address(uint8_t slot, uint32_t offset){
	if(offset + 16 <= FLASH_SETTINGS_SIZE){
		return slot_base(slot) + offset;
	}
	if(offset >= CFG_DOUBLE_CMDS_OFF && offset + 16 <= FLASH_IMAGE_SIZE){
		return FLASH_EXT_ADDR(slot) + (offset - CFG_DOUBLE_CMDS_OFF);
	}
	if(offset >= CFG_EXT2_OFF && offset + 16 <= FLASH_IMAGE2_SIZE){
		return FLASH_EXT2_ADDR(slot) + (offset - CFG_EXT2_OFF);
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
	pBankExpRange   = (uint8_t*)(b + CFG_BANK_EXP_RANGE_OFF);
	pCycleLabels    = (uint8_t*)(b + CFG_CYCLE_LABELS_OFF);
	pCombos         = (uint8_t*)(b + CFG_COMBOS_OFF);
	active_slot = slot;
	if(!target_chosen) target_slot = slot;
	return true;
}

/*
 * Erase the pages of the target slot, before writing them again. A failure is
 * reported to the tool, never a reason to stop the pedal. It runs from the
 * main loop (sysex_flash_task), which stops using the configuration first
 * when the slot erased is the one running.
 */
/*
 * The processor runs from flash, and stops while a page is erased or a half
 * word written, interrupts or not: up to 40 ms a page. The 1 ms tick misses
 * that time, and with it the pedal's MIDI clock, the LFOs and every timer
 * (#109). The cycle counter keeps counting, so flash_hold() notes it, with
 * interrupts off, and flash_release() gives the milliseconds missed back
 * before turning them on again: the clocks owed go out at once and the
 * tempo stays in its place. With interrupts off, a SysEx flash write arriving
 * over USB cannot walk into the middle either.
 */
static uint32_t held_primask;

uint32_t flash_hold(void){
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	held_primask = primask;
	HAL_FLASH_Unlock();
	return DWT->CYCCNT;
}

void flash_release(uint32_t start){
	HAL_FLASH_Lock();
	uint32_t ms = (DWT->CYCCNT - start) / (SystemCoreClock / 1000U);
	if(ms && (SCB->ICSR & SCB_ICSR_PENDSTSET_Msk)) ms--;	// that one still comes
	while(ms--){
		HAL_IncTick();
		tempo_tick_1ms();
	}
	if(!held_primask) __enable_irq();
}

bool flash_settings_erase(void){
	uint32_t pageError;
	upload_touch();

	FLASH_EraseInitTypeDef eraseInit ={
			.TypeErase = FLASH_TYPEERASE_PAGES,
			.Banks = FLASH_BANK_1,
			.PageAddress = slot_base(target_slot),
			.NbPages = FLASH_SETTINGS_NO_PAGES
	};

	uint32_t start = flash_hold();
	HAL_StatusTypeDef status = HAL_FLASHEx_Erase(&eraseInit, &pageError);
	// The extension areas belong to the slot too: a tool that writes no double
	// press commands or MIDI map must not leave the previous ones behind
	if(status == HAL_OK){
		eraseInit.PageAddress = FLASH_EXT_ADDR(target_slot);
		eraseInit.NbPages = FLASH_DOUBLE_PAGES;
		status = HAL_FLASHEx_Erase(&eraseInit, &pageError);
	}
	if(status == HAL_OK){
		eraseInit.PageAddress = FLASH_EXT2_ADDR(target_slot);
		eraseInit.NbPages = FLASH_EXT2_PAGES;
		status = HAL_FLASHEx_Erase(&eraseInit, &pageError);
	}
	flash_release(start);

	return status == HAL_OK;
}

/*
 * Change a few bytes of the running configuration, for the on-pedal editor
 * and a scene saved from the pedal. Flash can only be cleared a whole page at
 * a time, so the page those bytes live in is copied to RAM, changed there,
 * erased and written back. A power cut between the erase and the end of the
 * write would lose the whole page, 2 kB of configuration, so the new page is
 * written to a copy page first, and a note of where it goes to a log page;
 * the note is marked done once the page is in place. A note not marked done
 * at power on means the page was cut halfway, and flash_settings_recover()
 * writes it again from the copy.
 *
 *   log entry: [0..3] page address   [4..5] sum of the copy   [6..7] 0 when done
 *
 * The sum is written first and the address last, so a note cut halfway has
 * no address and is ignored: the page itself was not touched yet.
 */
#define PATCH_ENTRY_SIZE	(8U)
#define PATCH_ENTRIES		(FLASH_PAGE_SIZE / PATCH_ENTRY_SIZE)

static const volatile uint16_t *patch_entry(uint32_t i){
	return (const volatile uint16_t*)(PATCH_LOG_ADDR + i * PATCH_ENTRY_SIZE);
}

// The last note written, or -1 when the log is empty
static int32_t patch_last(void){
	for(int32_t i = PATCH_ENTRIES - 1; i >= 0; i--){
		const volatile uint16_t *e = patch_entry(i);
		if((e[0] & e[1] & e[2] & e[3]) != 0xFFFF) return i;
	}
	return -1;
}

static uint16_t page_sum(const uint8_t *p){
	uint16_t sum = 0x5A5A;
	for(uint32_t i = 0; i < FLASH_PAGE_SIZE; i += 2){
		sum = (uint16_t)(((sum << 1) | (sum >> 15)) + (p[i] | (p[i+1] << 8)));
	}
	return sum;
}

// A page of some slot the editor may patch: its main pages or double press area
static bool patch_page_ok(uint32_t page){
	if(page & (FLASH_PAGE_SIZE - 1)) return false;
	for(uint8_t s = 0; s < CONFIG_SLOTS; s++){
		if(page >= slot_base(s) && page < slot_base(s) + FLASH_SETTINGS_SIZE) return true;
		if(page >= FLASH_EXT_ADDR(s) && page < FLASH_EXT_ADDR(s) + FLASH_DOUBLE_PAGES * FLASH_PAGE_SIZE) return true;
	}
	return false;
}

static HAL_StatusTypeDef erase_page(uint32_t page){
	uint32_t pageError;
	FLASH_EraseInitTypeDef eraseInit = {
			.TypeErase = FLASH_TYPEERASE_PAGES,
			.Banks = FLASH_BANK_1,
			.PageAddress = page,
			.NbPages = 1
	};
	return HAL_FLASHEx_Erase(&eraseInit, &pageError);
}

// Write an erased page, skipping the half words erased flash already holds
static HAL_StatusTypeDef program_page(uint32_t page, const uint8_t *data){
	HAL_StatusTypeDef status = HAL_OK;
	for(uint32_t i = 0; status == HAL_OK && i < FLASH_PAGE_SIZE; i += 2){
		uint16_t half = (uint16_t)(data[i] | (data[i+1] << 8));
		if(half != 0xFFFF) status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, page + i, half);
	}
	return status;
}

static bool page_blank(uint32_t page){
	const uint32_t *p = (const uint32_t*)page;
	for(uint32_t i = 0; i < FLASH_PAGE_SIZE / 4; i++){
		if(p[i] != 0xFFFFFFFFU) return false;
	}
	return true;
}

static HAL_StatusTypeDef patch_done(uint32_t i){
	return HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, (uint32_t)&patch_entry(i)[3], 0);
}

bool flash_settings_patch(uint8_t *dst, const uint8_t *data, uint8_t len){
	static uint8_t page_buf[CFG_PAGE_SIZE];
	uint32_t address = (uint32_t)dst;
	uint32_t base = slot_base(active_slot);
	uint32_t ext = FLASH_EXT_ADDR(active_slot);

	if(len == 0) return false;
	bool in_slot = address >= base && address + len <= base + FLASH_SETTINGS_SIZE;
	bool in_ext = address >= ext && address + len <= ext + FLASH_DOUBLE_PAGES * CFG_PAGE_SIZE;
	if(!in_slot && !in_ext) return false;

	uint32_t page = address & ~(uint32_t)(CFG_PAGE_SIZE - 1);
	uint32_t at = address - page;
	if(at + len > CFG_PAGE_SIZE) return false;	// never straddles two pages
	if(memcmp(dst, data, len) == 0) return true;	// already what it should be

	memcpy(page_buf, (const uint8_t*)page, CFG_PAGE_SIZE);
	memcpy(page_buf + at, data, len);

	// In steps, each short enough for the clock: the processor stands still
	// through each (see flash_hold), and the clocks owed go out in between.
	// The copy page is left erased after each patch, so the stall of writing
	// it is no longer than that of the page itself was before.
	uint32_t start = flash_hold();
	HAL_StatusTypeDef status = page_blank(PATCH_COPY_ADDR) ? HAL_OK : erase_page(PATCH_COPY_ADDR);
	if(status == HAL_OK) status = program_page(PATCH_COPY_ADDR, page_buf);
	flash_release(start);
	tempo_task();
	if(status != HAL_OK) return false;

	uint32_t i = (uint32_t)(patch_last() + 1);
	start = flash_hold();
	if(i >= PATCH_ENTRIES){
		// Every note before is done: a pending one was finished at power on
		status = erase_page(PATCH_LOG_ADDR);
		i = 0;
	}
	uint32_t e = (uint32_t)patch_entry(i);
	if(status == HAL_OK) status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, e + 4, page_sum(page_buf));
	if(status == HAL_OK) status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, e, page & 0xFFFF);
	if(status == HAL_OK) status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, e + 2, page >> 16);
	if(status == HAL_OK) status = erase_page(page);
	if(status == HAL_OK) status = program_page(page, page_buf);
	if(status == HAL_OK) status = patch_done(i);
	flash_release(start);
	tempo_task();

	// Ready for the next one; a note left pending keeps its copy
	if(status == HAL_OK){
		start = flash_hold();
		erase_page(PATCH_COPY_ADDR);
		flash_release(start);
	}

	return status == HAL_OK;
}

/*
 * At power on, before the configuration is read: finish a page patch a power
 * cut left halfway, from its copy. A note whose copy does not add up, or that
 * points outside the configuration, is only marked done: that is not a page
 * this firmware wrote.
 */
void flash_settings_recover(void){
	int32_t i = patch_last();
	if(i < 0) return;
	const volatile uint16_t *e = patch_entry((uint32_t)i);
	if(e[3] != 0xFFFF) return;

	uint32_t page = e[0] | ((uint32_t)e[1] << 16);
	const uint8_t *copy = (const uint8_t*)PATCH_COPY_ADDR;
	uint32_t start = flash_hold();
	if(patch_page_ok(page) && e[2] == page_sum(copy)
			&& memcmp((const uint8_t*)page, copy, FLASH_PAGE_SIZE) != 0
			&& erase_page(page) == HAL_OK){
		program_page(page, copy);
	}
	patch_done((uint32_t)i);
	erase_page(PATCH_COPY_ADDR);
	flash_release(start);
}

/*
 * Write one 16 byte chunk of the target slot. False when it cannot be done,
 * for the tool to report: an offset outside the slot, or flash that is
 * neither erased nor already holding the data. A half word already holding
 * its value is left alone, so a chunk sent twice is written once; programming
 * it again would fail on the F1, and that used to stop the pedal for good.
 */
bool flash_settings_write(uint8_t* data, uint32_t offset){
	// Never write outside the slot: the offset comes straight from a SysEx message
	uint32_t flash_address = image_address(target_slot, offset);
	if(flash_address == 0){
		return false;
	}
	upload_touch();

	bool ok = true;
	HAL_FLASH_Unlock();
	for(int i=0; ok && i<8; i++){
		uint32_t at = flash_address + 2*i;
		uint16_t want = data[2*i] | (data[2*i+1] << 8);
		uint16_t now = *(volatile uint16_t*)at;
		if(now == want) continue;
		ok = now == 0xFFFF
				&& HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, at, want) == HAL_OK;
	}
	HAL_FLASH_Lock();
	return ok;
}
