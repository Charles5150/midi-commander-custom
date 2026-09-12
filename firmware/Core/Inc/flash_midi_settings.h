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


// Number of 1kB flash pages reserved for the settings. Must stay in sync with
// ALLOWED_NUM_FLASH_PAGES in python/CSV_to_Flash.py.
#define FLASH_SETTINGS_NO_PAGES	(3)
#define FLASH_SETTINGS_SIZE		(FLASH_SETTINGS_NO_PAGES * 1024)

#define MIDI_ROM_CMD_SIZE	(4)
#define MIDI_NUM_COMMANDS_PER_SWITCH (10)
#define MIDI_ROM_KEY_STRIDE	(MIDI_NUM_COMMANDS_PER_SWITCH*MIDI_ROM_CMD_SIZE)

void flash_settings_erase(void);
void flash_settings_write(uint8_t* data, uint32_t offset);

#endif /* INC_FLASH_MIDI_SETTINGS_H_ */
