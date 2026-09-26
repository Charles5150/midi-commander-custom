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
extern uint8_t *pBankExpSettings;	// Expression pedal CC and channel per bank, CFG_BANK_EXP_STRIDE bytes per bank
extern uint8_t *pBankExpRange;	// Expression pedal output range per bank, CFG_BANK_EXP_RANGE_STRIDE bytes per bank
extern uint8_t *pCycleLabels;	// Labels of the states of cycle buttons, BUTTON_LABEL_LEN chars each
extern uint8_t *pCombos;		// Two switch combinations, COMBO_STRIDE bytes each

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
 *   [11]   lowest value sent (0-127)          [12] highest value sent
 *   [13]   auto-engage button + 1 (0 none)    [14] auto-engage rest, 10 ms units
 *   [15]   what it sends: EXP_OUT_CC, EXP_OUT_PITCHBEND, EXP_OUT_CC14 or EXP_OUT_SPEED
 *   Blank flash (0xFF) means "not set" everywhere. Blank flash (0xFF) means "not set" everywhere. The tools
 *   used to write zeros after byte 10, so a range of 0 to 0 means the full
 *   range too.
 */
#define EXP_SETTINGS_STRIDE		(16)
#define EXP_CURVE_LINEAR		(0)
#define EXP_CURVE_LOG			(1)
#define EXP_CURVE_EXP			(2)
#define EXP_OUT_CC				(0)	// a 7-bit CC; also blank flash
#define EXP_OUT_PITCHBEND		(1)	// 14-bit Pitch Bend
#define EXP_OUT_CC14			(2)	// 14-bit CC pair: MSB on the CC, LSB on CC + 32
#define EXP_OUT_SPEED			(3)	// no MIDI: the speed of the LFOs and sequences

#define MIDI_NUM_BANKS			(32)
#define MIDI_NUM_SWITCHES		(8)

// Button labels shown on the display, BUTTON_LABEL_LEN ASCII chars per
// button indexed by (bank * 8 + switch), space padded. Follows the LED table.
// The characters are ASCII, so bit 7 is free, and that of the first one says
// the button goes back to off, and a cycle button to its start, when the bank
// changes. Older configurations always left it at zero; erased flash (0xFF)
// is an empty label and no reset.
#define BUTTON_LABEL_LEN		(4)
#define LABEL_RESET_BIT			(0x80)

// Button LED modes, one byte per button indexed by (bank * 8 + switch).
// Bits 0-1: 0 = Normal, 1 = Reverse, 2 = AlwaysOn. Bit 2: flash at the tempo,
// like a Tap button's LED. Bit 3: global, this button takes everything from
// the same button of the global bank. Bits 4-6: exclusive group, 0 for none.
// Bit 7: momentary when held (a toggle button held past the long press
// threshold goes back to its previous state on release). Erased flash (0xFF)
// reads as Normal with no group, not global, no tempo flash and no momentary
// hold.
#define LED_MODE_NORMAL		(0)
#define LED_MODE_REVERSE	(1)
#define LED_MODE_ALWAYS_ON	(2)
#define LED_MODE_MASK		(0x03)
#define BUTTON_TEMPO_FLASH	(0x04)
#define BUTTON_GLOBAL		(0x08)
#define BUTTON_GROUP_SHIFT	(4)
#define BUTTON_GROUP_MASK	(0x07)
#define BUTTON_MOMENTARY_HOLD	(0x80)


// Number of flash pages reserved for the settings. Pages are 2 kB on the
// STM32F103RE (FLASH_PAGE_SIZE). Must stay in sync with ALLOWED_NUM_FLASH_PAGES
// and FLASH_PAGE_SIZE in python/CSV_to_Flash.py.
#define FLASH_SETTINGS_NO_PAGES	(12)
#define FLASH_SETTINGS_SIZE		(FLASH_SETTINGS_NO_PAGES * FLASH_PAGE_SIZE)

/*
 * Configuration slots. Slot 0 keeps the address the configuration always had,
 * so a pedal that never uses the others behaves exactly as before. The state
 * journal follows it, then slots 1-3, then the power on banner's own text.
 * Nothing goes above 256 kB.
 *
 *   0x08020000  slot 0     12 pages
 *   0x08026000  journal     4 pages
 *   0x08028000  slot 1     12 pages
 *   0x0802E000  slot 2     12 pages
 *   0x08034000  slot 3     12 pages
 *   0x0803A000  banner      1 page
 *   0x0803A800  free       11 pages
 *   0x08040000  end
 *
 * The slots are full to the last byte and so are the global bytes, so the
 * next settings that need flash go in the free pages: two per slot from
 * 0x0803A800, a second extension area that the tools see as the
 * configuration going on after the double press area. With no global byte
 * left to say the tools wrote it, it will start with a marker of its own and
 * count only when that is there. That leaves three pages over.
 */
#define CONFIG_SLOTS			(4)
#define FLASH_STATE_PAGES		(4)
#define FLASH_SETTINGS_OFFSET	(1024U * 128U)
#define FLASH_SLOT0_ADDR		(FLASH_BASE + FLASH_SETTINGS_OFFSET)
#define FLASH_STATE_ADDR		(FLASH_SLOT0_ADDR + FLASH_SETTINGS_SIZE)
#define FLASH_SLOTN_ADDR(n)		(FLASH_STATE_ADDR + FLASH_STATE_PAGES * FLASH_PAGE_SIZE + ((n) - 1U) * FLASH_SETTINGS_SIZE)
#define FLASH_BANNER_ADDR		(FLASH_SLOTN_ADDR(CONFIG_SLOTS))

/*
 * Extension area. The double press commands did not fit in the 12 pages of a
 * slot, and slot 0 cannot grow without moving the journal and every other
 * slot. Each slot therefore gets FLASH_DOUBLE_PAGES more pages in the gap
 * between the end of the firmware and slot 0. Nothing above 256 kB is used:
 * pedals exist whose chip reports 256 kB.
 *
 *   0x08003000  firmware, at most 76 kB (the linker scripts enforce it)
 *   0x08016000  slot 0 double press    5 pages
 *   0x08018800  slot 1 double press
 *   0x0801B000  slot 2 double press
 *   0x0801D800  slot 3 double press
 *   0x08020000  slot 0
 *
 * The stock firmware ended at 0x08015E8A, so the area starts out erased on a
 * pedal that ran it. Older firmware or tools may still have left something
 * there, so the firmware only reads a slot's area when its global setting
 * GLOBAL_SETTINGS_DOUBLE_STORED says the tools wrote it.
 *
 * To the tools it is simply the continuation of the configuration: offsets
 * from CFG_DOUBLE_CMDS_OFF (the end of the slot's pages) map to it.
 */
#define CFG_PAGE_SIZE			(2048)
#define FLASH_DOUBLE_PAGES		(5)
#define FLASH_EXT_OFFSET		(1024U * 88U)
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
/*
 * Expression pedals per bank: [pedal 1 CC, pedal 1 channel, pedal 2 CC, pedal 2
 * channel]. CC 0-127 replaces the pedal's CC in that bank, BANK_EXP_CC_OFF
 * silences it there and BANK_EXP_CC_SPEED makes it set the speed of the LFOs
 * and sequences; channel 1-16 replaces its channel. Erased flash (0xFF),
 * which is all a configuration written before 0.28 holds here, keeps the
 * pedal's own settings.
 */
#define CFG_BANK_EXP_STRIDE	(4)
#define CFG_BANK_EXP_SIZE	(MIDI_NUM_BANKS * CFG_BANK_EXP_STRIDE)
#define CFG_BANK_EXP_OFF	(CFG_SETLIST_OFF + CFG_SETLIST_SIZE)
#define BANK_EXP_CC_OFF		(128)	// 0x80, above any CC number
#define BANK_EXP_CC_SPEED	(130)	// 0x82, EXP_TARGET_SPEED
/*
 * Expression pedal output range per bank: [pedal 1 lowest, pedal 1 highest,
 * pedal 2 lowest, pedal 2 highest], 0-127 each. Erased flash (0xFF), which is
 * all a configuration written before 0.33 holds here, keeps the pedal's own.
 */
#define CFG_BANK_EXP_RANGE_STRIDE	(4)
#define CFG_BANK_EXP_RANGE_SIZE	(MIDI_NUM_BANKS * CFG_BANK_EXP_RANGE_STRIDE)
#define CFG_BANK_EXP_RANGE_OFF	(CFG_BANK_EXP_OFF + CFG_BANK_EXP_SIZE)
/*
 * Labels of the states of cycle buttons, BUTTON_LABEL_LEN chars each, space
 * padded. A Cycle command names its state's label by its index in this table,
 * so the tools store a label used in many places only once. Erased flash,
 * which is all a configuration written before 0.38 holds here, is never read:
 * such a configuration has no Cycle commands.
 */
#define CYCLE_LABEL_COUNT	(48)
#define CFG_CYCLE_LABELS_SIZE	(CYCLE_LABEL_COUNT * BUTTON_LABEL_LEN)
#define CFG_CYCLE_LABELS_OFF	(CFG_BANK_EXP_RANGE_OFF + CFG_BANK_EXP_RANGE_SIZE)
/*
 * Two switches pressed together. Each entry names a pair of the command
 * switches and the list the pair runs, which is any button's list, as a Macro
 * names one, so an entry costs four bytes rather than ten commands:
 *   [0] first switch 0-7 in the low nibble, second in the high one; 0xFF unused
 *   [1] the bank it counts in plus one, 0 for every bank
 *   [2] bank of the list it runs, 0-31
 *   [3] button of it 0-7 in the low nibble, which list (MACRO_LIST_) in the high
 * Erased flash, which is all a configuration written before 0.59 holds here,
 * is no entry at all. They take the last bytes a slot had free.
 */
#define COMBO_COUNT			(12)
#define COMBO_STRIDE		(4)
#define COMBO_EVERY_BANK	(0)
#define COMBO_UNUSED		(0xFF)
#define CFG_COMBOS_SIZE		(COMBO_COUNT * COMBO_STRIDE)
#define CFG_COMBOS_OFF		(CFG_CYCLE_LABELS_OFF + CFG_CYCLE_LABELS_SIZE)
#define CFG_TOTAL_SIZE		(CFG_COMBOS_OFF + CFG_COMBOS_SIZE)
// Double press commands, same size as CMDS, stored in the extension area
#define CFG_DOUBLE_CMDS_OFF	(FLASH_SETTINGS_NO_PAGES * CFG_PAGE_SIZE)
#define CFG_DOUBLE_CMDS_SIZE	(CFG_CMDS_SIZE)
#define FLASH_IMAGE_SIZE		(CFG_DOUBLE_CMDS_OFF + FLASH_DOUBLE_PAGES * CFG_PAGE_SIZE)

// Erase and write act on the target slot, see flash_settings_set_target()
bool flash_settings_erase(void);
bool flash_settings_write(uint8_t* data, uint32_t offset);
// Change a few bytes of the running configuration in place, for the on-pedal
// editor: the page they live in is rewritten around them. False if the
// address is outside the active configuration or the write failed.
bool flash_settings_patch(uint8_t *dst, const uint8_t *data, uint8_t len);

// Point every configuration pointer at a slot; it becomes active and the target
bool flash_settings_select(uint8_t slot);
uint8_t flash_settings_active_slot(void);
// The slot the tools erase, write and read; follows the active one until changed
void flash_settings_set_target(uint8_t slot);
uint8_t flash_settings_target_slot(void);
const uint8_t *flash_settings_target_base(void);
// 16 bytes of the target slot's image at a tools offset, or NULL out of range
const uint8_t *flash_settings_target_ptr(uint32_t offset);
// True when the active slot's double press area was written by the tools
bool flash_settings_double_stored(void);
// True when a slot holds a configuration (see the .c file for the test)
bool flash_settings_slot_valid(uint8_t slot);
uint8_t flash_settings_valid_mask(void);

#endif /* INC_FLASH_MIDI_SETTINGS_H_ */
