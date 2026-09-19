/*
 * midi_defines.h
 *
 *  Created on: 4 Jul 2021
 *      Author: D Harvie
 */

#ifndef INC_MIDI_DEFINES_H_
#define INC_MIDI_DEFINES_H_

/* Code Index Number Classifications */
// See page 16 of "USB Device Class Definition for MIDI Devices"
#define CIN_MISCELLANEOUS				(0x0)
#define CIN_CABLE_EVENTS				(0x1)
#define CIN_TWO_BYTE_SYSTEM_COMMON		(0x2)
#define CIN_THREE_BYTE_SYSTEM_COMMON	(0x3)
#define CIN_SYSEX_STARTS_OR_CONTINUES	(0x4)
#define CIN_SINGLE_BYTE_SYSTEM_COMMON	(0x5)
#define CIN_SYSEX_ENDS_WITH_FOLLOWING_SINGLE_BYTE	(0x5)
#define CIN_SYSEX_ENDS_WITH_FOLLOWING_TWO_BYTES		(0x6)
#define CIN_SYSEX_ENDS_WITH_FOLLOWING_THREE_BYTES	(0x7)
#define CIN_NOTE_OFF					(0x8)
#define CIN_NOTE_ON						(0x9)
#define CIN_POLY_KEYPRESS				(0xA)
#define CIN_CONTROL_CHANGE				(0xB)
#define CIN_PROGRAM_CHANGE				(0xC)
#define CIN_CHANNEL_PRESSURE			(0xD)
#define CIN_PITCHBEND_CHANGE			(0xE)
#define CIN_SINGLE_BYTE					(0xF)

#define MIDI_PC_BANK_SELECT_MSB	(0x00)
#define MIDI_PC_BANK_SELECT_LSB (0X20)

#define MIDI_CONTROL_ON		(1)
#define MIDI_CONTROL_OFF	(0)

// using the private use manufacturer ID
#define MIDI_MANUF_ID	(0x7D)

// SysEx commands for this device
#define SYSEX_CMD_ERASE_FLASH	(52) // must contain two bytes of 0x42 and 0x24 as check words.
#define SYSEX_RSP_ERASE_FLASH	(53) // zero length response to confirm success
#define SYSEX_CMD_WRITE_FLASH	(54) // first byte is the page address (16 byte pages), valid range 0-63.  Following 16 bytes are the data to write
#define SYSEX_RSP_WRITE_FLASH	(55) // zero length response to confirm write
#define SYSEX_CMD_READ_FLASH	(56) // two bytes: chunk address high/low (7 bits each, 16 byte chunks)
#define SYSEX_RSP_READ_FLASH	(57) // echoes the chunk address, followed by 16 bytes as 32 nibbles (high nibble first)
#define SYSEX_CMD_GET_VERSION	(58) // no parameters
#define SYSEX_RSP_GET_VERSION	(59) // firmware version string as 7-bit ASCII
#define SYSEX_CMD_RESET			(60) // Reset the device
#define SYSEX_CMD_GET_PEDALS	(62) // no parameters
#define SYSEX_RSP_GET_PEDALS	(63) // per pedal: raw ADC high 7 bits, low 7 bits, current CC value
#define SYSEX_CMD_SELECT_SLOT	(64) // one byte: slot 0-3 the next erase/write/read act on, 0x7F only asks
#define SYSEX_RSP_SELECT_SLOT	(65) // target slot, active slot, bit mask of slots holding a configuration
#define SYSEX_CMD_PRESS_BUTTON	(66) // switch 0-7 (1..4, A..D), 8 Bank Down, 9 Bank Up; then 1 down / 0 up
#define SYSEX_RSP_PRESS_BUTTON	(67) // echoes the switch and the action
#define SYSEX_CMD_GET_STATE	(68) // no parameters
#define SYSEX_RSP_GET_STATE	(69) // bank, slot, toggles (low 7 bits, bit 7), bank name x4, labels 8x4, LED levels x10,
                                  // screen frame count (low 7, high 7), asleep
#define SYSEX_CMD_GET_SCREEN	(70) // part 0-15: half (0 left, 1 right) of screen page part/2
#define SYSEX_RSP_GET_SCREEN	(71) // part, then its 65 bytes packed 7 in 8 (a byte of high bits, then 7 low parts)
#define SYSEX_CMD_SET_TEXT	(72) // place (0 info line, 1 bank name, 2 whole top line large, 3 small), how (0 until the bank changes, 1 kept, 2 for a moment), then the text
#define SYSEX_RSP_SET_TEXT	(73) // echoes the place and how

#define SYSEX_START (0xF0)
#define SYSEX_END	(0xF7)

#define CMD_NO_CMD_NIBBLE	(0x00)
// Wait: shares the empty command type, low nibble 1. Byte 2 holds the pause in
// 10ms units, so an all zero (empty) command stays an empty command. Byte 1 is
// left at 0 because its top bit is what marks a command as toggling.
#define CMD_WAIT_MODE		(1)
// Ramp: same empty command type, low nibble 2. Turns the CC command right
// below it into a ramp: bytes 2 (low) and 3 (high) hold its time in 10ms units.
#define CMD_RAMP_MODE		(2)
// Cycle: same empty command type, low nibble 3. Only in a button's short press
// list, where each one starts a new state: the list before the first is state
// 1, and every press sends the next state's commands, round and round. Byte 1
// is the state's label, an index into the cycle label table, or CYCLE_NO_LABEL
// to show the button's own.
#define CMD_CYCLE_MODE		(3)
#define CYCLE_NO_LABEL		(0x7F)
// Leave: same empty command type, low nibble 4. Only in a bank's enter list,
// which it splits in two: the commands above it are sent on entering the bank,
// those below it on leaving it. The other bytes are 0.
#define CMD_LEAVE_MODE		(4)
// Exp: same empty command type, low nibble 5. Changes what an expression pedal
// sends until another Exp command or a bank change. Byte 1 is the pedal (0 or
// 1), with the top bit marking a toggling command, which puts the pedal back
// to its own target when switched off. Byte 2 is the CC, EXP_TARGET_OFF to
// silence the pedal or EXP_TARGET_RESET to give it back its own target. Byte 3
// is the channel 1-16, or 0 to keep the pedal's own.
#define CMD_EXP_MODE		(5)
#define EXP_TARGET_OFF		(0x80)
#define EXP_TARGET_RESET	(0x81)
// LFO: same empty command type, low nibble 6. Like a Ramp, turns the CC
// command right below it into an LFO that swings between its Off and On
// values, locked to the tempo. Byte 2 is the length of one cycle, an index
// into the LFO_DIV_ table below, byte 3 the shape, one of the LFO_SHAPE_ values.
#define CMD_LFO_MODE		(6)
// Cycle lengths in 24ths of a beat (MIDI clocks), shortest first:
// 1/16T 1/16 1/8T 1/8 1/4T 1/8. 1/4 1/2T 1/4. 1/2 1/2. 1/1 2/1 4/1
#define LFO_DIV_TICKS		{4, 6, 8, 12, 16, 18, 24, 32, 36, 48, 72, 96, 192, 384}
#define LFO_DIV_COUNT		(14)
#define LFO_SHAPE_SINE		(0)
#define LFO_SHAPE_TRIANGLE	(1)
#define LFO_SHAPE_SAW_UP	(2)
#define LFO_SHAPE_SAW_DOWN	(3)
#define LFO_SHAPE_SQUARE	(4)
#define LFO_SHAPE_RANDOM	(5)
#define LFO_SHAPE_COUNT		(6)
#define CMD_PC_NIBBLE		(0xC0)
// Relative Program Change: a PC whose byte 2 (the Bank Select MSB, 0x80 and up
// meaning none) holds one of these markers. Byte 1 is the step, byte 3 the last
// program in the range, with bit 7 set to wrap round at the ends. The REPEAT
// markers also fire the command again while the button is held.
#define PC_REL_UP			(0x81)
#define PC_REL_DOWN			(0x82)
#define PC_REL_UP_REPEAT	(0x83)
#define PC_REL_DOWN_REPEAT	(0x84)
#define PC_IS_RELATIVE(b2)	((b2) >= PC_REL_UP && (b2) <= PC_REL_DOWN_REPEAT)
#define CMD_CC_NIBBLE		(0xB0)
#define CMD_PB_NIBBLE		(0xE0)
#define CMD_NOTE_NIBBLE		(0x90)
#define CMD_KEY_NIBBLE		(0xD0)
#define CMD_TAP_NIBBLE		(0x70)	// Tap tempo: low nibble = mode, see the TAP_MODE_ values
// Tap command modes. Set: bytes 2 (low 7 bits) and 3 (high bits) hold the BPM.
// Up / Down: byte 2 is the step in BPM, with TAP_REPEAT_BIT to repeat while
// held. Byte 1 stays 0, as its top bit marks a toggling command.
#define TAP_MODE_TAP		(0)
#define TAP_MODE_CLOCK		(1)
#define TAP_MODE_SET		(2)
#define TAP_MODE_UP			(3)
#define TAP_MODE_DOWN		(4)
#define TAP_REPEAT_BIT		(0x80)
#define CMD_CCINC_NIBBLE	(0x50)	// Relative CC: byte1 = CC | wrap<<7, byte2 = step | repeat<<7, byte3 = down<<7 | start value
#define CCINC_REPEAT_BIT	(0x80)	// In the step byte of CCInc: repeat while held
#define CMD_SYSEX_NIBBLE	(0x60)	// Stored SysEx string: byte1 = index into the string table
#define CMD_BANK_NIBBLE		(0x40)	// Bank change: low nibble = mode (0 go to, 1 up by, 2 down by), byte 1 = value
#define CMD_MEDIA_NIBBLE	(0x30)	// Consumer control (media) key: bytes 1-2 = usage (10 bits), byte 3 = duration | toggle
#define CMD_START_NIBBLE	(0x10)
#define CMD_STOP_NIBBLE		(0x20)
#define CMD_PANIC_NIBBLE	(0x80)	// All Sound Off and All Notes Off on every channel
#define BANK_MODE_CONFIG	(3)	// Bank command low nibble: switch to configuration slot byte 1
#define BANK_MODE_NEXT_CONFIG	(4)	// Bank command low nibble: switch to the next slot holding one
#define BANK_MODE_PAGE		(5)	// Bank command low nibble: show bank byte 1 as this bank's second page, or go back
#define CONFIG_NEXT		(0x80)
#define CMD_SCENE_NIBBLE	(0xA0)	// Scene: byte1 = buttons affected (bit 0 = button 1 .. bit 7 = D), byte2 = wanted states

#define GLOBAL_SETTINGS_CHANNEL (0)
#define GLOBAL_SETTINGS_REALTIME_PASS (1)	// Forward Clock/Start/Continue/Stop from USB to DIN
#define GLOBAL_SETTINGS_EXP1_CC (2)
#define GLOBAL_SETTINGS_EXP2_CC (3)
#define GLOBAL_SETTINGS_BANK_UP_LED (4)
#define GLOBAL_SETTINGS_BANK_DOWN_LED (5)
#define GLOBAL_SETTINGS_USB_THRU (6)		// Forward channel, system common and foreign SysEx from USB to DIN
#define GLOBAL_SETTINGS_REMEMBER_STATE (7)	// Restore last bank and toggle states at power on
#define GLOBAL_SETTINGS_LONG_PRESS (8)		// Long press threshold in 10 ms units (0/0xFF = 500 ms)
#define GLOBAL_SETTINGS_LED_BRIGHTNESS (9)		// Lit LED brightness in percent (0xFF = 100)
#define GLOBAL_SETTINGS_LED_REST_BRIGHTNESS (10)	// Brightness of LEDs lit at rest by Reverse/AlwaysOn (0xFF = 100)
#define GLOBAL_SETTINGS_BANK_JUMP_STEP (11)	// Banks skipped by a long press on Bank Up/Down (0/0xFF = 8)
#define GLOBAL_SETTINGS_BANK_CHANGE_MODE (12)	// 0 off, 1 Program Change, 2 Control Change
#define GLOBAL_SETTINGS_BANK_CHANGE_CHANNEL (13)	// 0 = any channel, 1-16 = that channel only
#define GLOBAL_SETTINGS_BANK_CHANGE_CC (14)	// CC number when the mode is Control Change
#define GLOBAL_SETTINGS_BANK_SWITCH_MODE (15)	// What the Bank Up/Down switches do
// Bytes 16..31 hold ConfigName, so anything new starts at 32
#define GLOBAL_SETTINGS_SLEEP_AFTER_MIN (32)	// Idle minutes before the display and LEDs go out (0 = never)
#define GLOBAL_SETTINGS_SETLIST_MODE (33)	// 1 = Bank Up/Down follow the setlist order instead of bank numbers
#define GLOBAL_SETTINGS_CLOCK_FOLLOW (34)	// 1 = adopt the tempo of MIDI clock arriving over USB
#define GLOBAL_SETTINGS_LED_FEEDBACK (35)	// 1 = incoming CC/Note over USB set matching toggle buttons
#define GLOBAL_SETTINGS_DOUBLE_PRESS (36)	// Double press window in 10 ms units (0/0xFF = 300 ms)
#define GLOBAL_SETTINGS_DOUBLE_STORED (37)	// 1 = the tools wrote this slot's double press area
#define GLOBAL_SETTINGS_REMOTE_MODE (38)	// Remote press: 0 off, 1 Control Change, 2 Note
#define GLOBAL_SETTINGS_REMOTE_CHANNEL (39)	// 0 = any channel, 1-16 = that channel only
#define GLOBAL_SETTINGS_REMOTE_FIRST (40)	// CC or note for switch 1; the next nine follow

#define BANK_SWITCH_BANK_ONLY	(0)	// change bank, send nothing (the original behaviour)
#define BANK_SWITCH_BANK_MIDI	(1)	// change bank and send the switch's commands
#define BANK_SWITCH_MIDI_ONLY	(2)	// send the commands only, never change bank

#define REMOTE_OFF		(0)
#define REMOTE_CC		(1)
#define REMOTE_NOTE		(2)

#define BANK_CHANGE_OFF		(0)
#define BANK_CHANGE_PC		(1)
#define BANK_CHANGE_CC		(2)

#endif /* INC_MIDI_DEFINES_H_ */
