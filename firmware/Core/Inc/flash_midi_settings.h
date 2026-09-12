/*
 * flash_midi_settings.h
 *
 *  Created on: 12 Jul 2021
 *      Author: D Harvie
 */

#ifndef INC_FLASH_MIDI_SETTINGS_H_
#define INC_FLASH_MIDI_SETTINGS_H_

#include "main.h"

extern uint8_t *pSwitchCmds;
extern uint8_t *pGlobalSettings;
extern uint8_t *pBankStrings;
extern uint8_t *pButtonLedModes;
extern uint8_t *pButtonLabels;
extern uint8_t *pLongPressCmds;	// Second command set per button, same layout as pSwitchCmds
extern uint8_t *pExpSettings;	// Expression pedal calibration, EXP_SETTINGS_STRIDE bytes per pedal
extern uint8_t *pBankEnterCmds;	// Commands sent when a bank is entered, same shape as one button's list per bank
extern uint8_t *pSysExStrings;	// Table of stored SysEx payloads: [length][up to SYSEX_STRING_MAX data bytes]

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
#define CFG_GLOBAL_SIZE		(32)
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
#define CFG_TOTAL_SIZE		(CFG_SYSEX_OFF + CFG_SYSEX_SIZE)

void flash_settings_erase(void);
void flash_settings_write(uint8_t* data, uint32_t offset);

#endif /* INC_FLASH_MIDI_SETTINGS_H_ */
