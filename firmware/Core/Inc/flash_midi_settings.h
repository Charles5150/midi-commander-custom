/*
 * flash_midi_settings.h
 *
 *  Created on: 12 Jul 2021
 *      Author: D Harvie
 */

#ifndef INC_FLASH_MIDI_SETTINGS_H_
#define INC_FLASH_MIDI_SETTINGS_H_

#include "main.h"
#include <stdbool.h>

extern uint8_t *pSwitchCmds;
extern uint8_t *pGlobalSettings;
extern uint8_t *pBankStrings;
extern uint8_t *pButtonLedModes;
extern uint8_t *pButtonLabels;
extern uint8_t *pLongPressCmds;	// Second command set per button, same layout as pSwitchCmds
extern uint8_t *pDoublePressCmds;	// Third command set per button, in the slot's extension area
extern uint8_t *pExpSettings;	// Expression pedal calibration, EXP_SETTINGS_STRIDE bytes per pedal
extern uint8_t *pBankEnterCmds;	// Commands sent when a bank is entered, same shape as one button's list per bank
extern uint8_t *pSysExStrings;	// Table of stored SysEx payloads: [length][up to SYSEX_STRING_MAX data bytes]
extern uint8_t *pBankSwitchCmds;	// Command lists for the Bank Down/Up switches
extern uint8_t *pSetlist;		// Bank numbers in setlist order, 0xFF ends the list

/*
 * Four command lists, one per switch and press length, in this order:
 *   0 Down short   1 Down long   2 Up short   3 Up long
 * They are global rather than per bank: the switches are navigation, so the
 * same thing should happen wherever you are.
 */
#define BANK_SWITCH_DOWN	(0)
#define BANK_SWITCH_UP		(1)
#define BANK_SWITCH_LISTS	(4)

#define SYSEX_STRING_COUNT	(16)
#define SYSEX_STRING_MAX	(23)	// data bytes, F0 and F7 are added when sending
#define SYSEX_STRING_STRIDE	(SYSEX_STRING_MAX + 1)

/*
 * Per pedal:
 *   [0..1] min ADC (LE)        [2..3] max ADC (LE)
 *   [4]    curve               [5]    invert
 *   [6]    channel (0 = global, 1-16)
 *   [7]    button triggered when the pedal reaches the toe (0-7, 0xFF none)
 *   [8]    button triggered when it returns to the heel (0-7, 0xFF none)
 *   [9]    toe threshold, as a 7-bit value    [10] heel threshold
 *   rest reserved. Blank flash (0xFF) means "not set" everywhere.
 */
#define EXP_SETTINGS_STRIDE		(16)
#define EXP_CURVE_LINEAR		(0)
#define EXP_CURVE_LOG			(1)
#define EXP_CURVE_EXP			(2)

#define MIDI_NUM_BANKS			(32)
#define MIDI_NUM_SWITCHES		(8)

// Button labels shown on the display, BUTTON_LABEL_LEN ASCII chars per
// button indexed by (bank * 8 + switch), space padded. Follows the LED table.
#define BUTTON_LABEL_LEN		(4)

// Button LED modes, one byte per button indexed by (bank * 8 + switch).
// 0 = Normal, 1 = Reverse, 2 = AlwaysOn. Erased flash (0xFF) reads as Normal.
#define LED_MODE_NORMAL		(0)
#define LED_MODE_REVERSE	(1)
#define LED_MODE_ALWAYS_ON	(2)


// Number of flash pages reserved for the settings. Pages are 2 kB on the
// STM32F103RE (FLASH_PAGE_SIZE). Must stay in sync with ALLOWED_NUM_FLASH_PAGES
// and FLASH_PAGE_SIZE in python/CSV_to_Flash.py.
#define FLASH_SETTINGS_NO_PAGES	(12)
#define FLASH_SETTINGS_SIZE		(FLASH_SETTINGS_NO_PAGES * FLASH_PAGE_SIZE)

/*
 * Configuration slots. Slot 0 keeps the address the configuration always had,
 * so a pedal that never uses the others behaves exactly as before. The state
 * journal follows it, then slots 1-3, which end at 256 kB.
 *
 *   0x08020000  slot 0     12 pages
 *   0x08026000  journal     4 pages
 *   0x0802E000  slot 1     12 pages
 *   0x08034000  slot 2     12 pages
 *   0x0803A000  slot 3     12 pages
 *   0x08040000  end
 */
#define CONFIG_SLOTS			(4)
#define FLASH_STATE_PAGES		(4)
#define FLASH_SETTINGS_OFFSET	(1024U * 128U)
#define FLASH_SLOT0_ADDR		(FLASH_BASE + FLASH_SETTINGS_OFFSET)
#define FLASH_STATE_ADDR		(FLASH_SLOT0_ADDR + FLASH_SETTINGS_SIZE)
#define FLASH_SLOTN_ADDR(n)		(FLASH_STATE_ADDR + FLASH_STATE_PAGES * FLASH_PAGE_SIZE + ((n) - 1U) * FLASH_SETTINGS_SIZE)

/*
 * Extension area. The double press commands did not fit in the 12 pages of a
 * slot, and slot 0 cannot grow without moving the journal and every other
 * slot. Each slot therefore gets FLASH_DOUBLE_PAGES more pages above 256 kB,
 * which the stock firmware never used:
 *
 *   0x08040000  slot 0 double press    5 pages
 *   0x08042800  slot 1 double press
 *   0x08045000  slot 2 double press
 *   0x08047800  slot 3 double press
 *   0x0804A000  end
 *
 * To the tools it is simply the continuation of the configuration: offsets
 * from CFG_DOUBLE_CMDS_OFF (the end of the slot's pages) map to it. It needs a
 * 512 kB chip; on a smaller one double press is unavailable.
 */
#define CFG_PAGE_SIZE			(2048)
#define FLASH_DOUBLE_PAGES		(5)
#define FLASH_EXT_OFFSET		(1024U * 256U)
#define FLASH_EXT_ADDR(n)		(FLASH_BASE + FLASH_EXT_OFFSET + (n) * FLASH_DOUBLE_PAGES * FLASH_PAGE_SIZE)

#define MIDI_ROM_CMD_SIZE	(4)
#define MIDI_NUM_COMMANDS_PER_SWITCH (10)
#define MIDI_ROM_KEY_STRIDE	(MIDI_NUM_COMMANDS_PER_SWITCH*MIDI_ROM_CMD_SIZE)

/*
 * Configuration layout. Every offset is derived from these sizes, so changing
 * the bank count moves everything consistently. Must match the offsets in
 * python/lib/binaryUnpacker.py.
 *
 *   GLOBAL       global settings + config name
 *   BANK_STRINGS 4 char large name + 8 char small name per bank
 *   CMDS         banks x switches x commands x 4 bytes
 *   LED_MODES    one byte per button
 *   LABELS       BUTTON_LABEL_LEN chars per button
 *   LONG_CMDS    second command set, same size as CMDS
 *   EXP          two pedal calibration records
 */
#define CFG_BUTTONS			(MIDI_NUM_BANKS * MIDI_NUM_SWITCHES)
/*
 * 0..15   individual settings
 * 16..31  ConfigName
 * 32..47  room for new settings; the first is the idle sleep timeout
 */
#define CFG_GLOBAL_SIZE		(48)
#define CFG_BANK_STRING_SIZE	(12)
#define CFG_BANK_STRINGS_SIZE	(MIDI_NUM_BANKS * CFG_BANK_STRING_SIZE)
#define CFG_CMDS_SIZE		(CFG_BUTTONS * MIDI_ROM_KEY_STRIDE)
#define CFG_LED_MODES_SIZE	(CFG_BUTTONS)
#define CFG_LABELS_SIZE		(CFG_BUTTONS * BUTTON_LABEL_LEN)
#define CFG_EXP_SIZE		(2 * EXP_SETTINGS_STRIDE)

#define CFG_BANK_STRINGS_OFF	(CFG_GLOBAL_SIZE)
#define CFG_CMDS_OFF		(CFG_BANK_STRINGS_OFF + CFG_BANK_STRINGS_SIZE)
#define CFG_LED_MODES_OFF	(CFG_CMDS_OFF + CFG_CMDS_SIZE)
#define CFG_LABELS_OFF		(CFG_LED_MODES_OFF + CFG_LED_MODES_SIZE)
#define CFG_LONG_CMDS_OFF	(CFG_LABELS_OFF + CFG_LABELS_SIZE)
#define CFG_EXP_OFF			(CFG_LONG_CMDS_OFF + CFG_CMDS_SIZE)
#define CFG_BANK_ENTER_SIZE	(MIDI_NUM_BANKS * MIDI_ROM_KEY_STRIDE)
#define CFG_BANK_ENTER_OFF	(CFG_EXP_OFF + CFG_EXP_SIZE)
#define CFG_SYSEX_SIZE		(SYSEX_STRING_COUNT * SYSEX_STRING_STRIDE)
#define CFG_SYSEX_OFF		(CFG_BANK_ENTER_OFF + CFG_BANK_ENTER_SIZE)
#define CFG_BANK_SWITCH_SIZE	(BANK_SWITCH_LISTS * MIDI_ROM_KEY_STRIDE)
#define CFG_BANK_SWITCH_OFF	(CFG_SYSEX_OFF + CFG_SYSEX_SIZE)
#define SETLIST_MAX		(32)
#define CFG_SETLIST_SIZE	(SETLIST_MAX)
#define CFG_SETLIST_OFF		(CFG_BANK_SWITCH_OFF + CFG_BANK_SWITCH_SIZE)
#define CFG_TOTAL_SIZE		(CFG_SETLIST_OFF + CFG_SETLIST_SIZE)
// Double press commands, same size as CMDS, stored in the extension area
#define CFG_DOUBLE_CMDS_OFF	(FLASH_SETTINGS_NO_PAGES * CFG_PAGE_SIZE)
#define CFG_DOUBLE_CMDS_SIZE	(CFG_CMDS_SIZE)
#define FLASH_IMAGE_SIZE		(CFG_DOUBLE_CMDS_OFF + FLASH_DOUBLE_PAGES * CFG_PAGE_SIZE)

// Erase and write act on the target slot, see flash_settings_set_target()
void flash_settings_erase(void);
void flash_settings_write(uint8_t* data, uint32_t offset);

// Point every configuration pointer at a slot; it becomes active and the target
bool flash_settings_select(uint8_t slot);
uint8_t flash_settings_active_slot(void);
// The slot the tools erase, write and read; follows the active one until changed
void flash_settings_set_target(uint8_t slot);
uint8_t flash_settings_target_slot(void);
const uint8_t *flash_settings_target_base(void);
// 16 bytes of the target slot's image at a tools offset, or NULL out of range
const uint8_t *flash_settings_target_ptr(uint32_t offset);
// Double press needs the extension area, which needs a 512 kB chip
bool flash_settings_double_available(void);
// True when a slot holds a configuration (see the .c file for the test)
bool flash_settings_slot_valid(uint8_t slot);
uint8_t flash_settings_valid_mask(void);

#endif /* INC_FLASH_MIDI_SETTINGS_H_ */
