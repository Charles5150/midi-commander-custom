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

// Per pedal: [0..1] min ADC (LE), [2..3] max ADC (LE), [4] curve, [5] invert,
// [6] channel (0 = global, 1-16), rest reserved. Blank flash = defaults.
#define EXP_SETTINGS_STRIDE		(16)
#define EXP_CURVE_LINEAR		(0)
#define EXP_CURVE_LOG			(1)
#define EXP_CURVE_EXP			(2)

#define MIDI_NUM_BANKS			(8)
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
#define FLASH_SETTINGS_NO_PAGES	(3)
#define FLASH_SETTINGS_SIZE		(FLASH_SETTINGS_NO_PAGES * FLASH_PAGE_SIZE)

#define MIDI_ROM_CMD_SIZE	(4)
#define MIDI_NUM_COMMANDS_PER_SWITCH (10)
#define MIDI_ROM_KEY_STRIDE	(MIDI_NUM_COMMANDS_PER_SWITCH*MIDI_ROM_CMD_SIZE)

void flash_settings_erase(void);
void flash_settings_write(uint8_t* data, uint32_t offset);

#endif /* INC_FLASH_MIDI_SETTINGS_H_ */
