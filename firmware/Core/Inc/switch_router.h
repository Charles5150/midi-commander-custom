/*
 * switch_router.h
 *
 *  Created on: 8 Jul 2021
 *      Author: D Harvie
 */

#ifndef INC_SWITCH_ROUTER_H_
#define INC_SWITCH_ROUTER_H_

#include <stdint.h>
#include <stdbool.h>

void handle_switches(void);
void sw_led_init(void);
void update_leds_on_bank_change(void);
void set_all_leds(uint8_t state);
void setIsSuspended(uint8_t suspended);

// Current bank and per-button toggle bitmasks, for persisting/restoring state
uint8_t sw_get_current_page(void);
// The bank the song is in: the one shown, or the one whose page is shown
uint8_t sw_get_home_bank(void);
uint8_t sw_preview_bank(void);	// the bank previewed, 0xFF when none
void sw_get_toggle_states(uint32_t out[8]);
void sw_get_long_toggle_states(uint32_t out[8]);
void sw_restore_state(uint8_t page, const uint32_t toggles[8], const uint32_t long_toggles[8]);

// Safe mode: true if a footswitch was held at power on, which is then not
// taken as a press. Checked once at boot; sw_safe_mode tells from then on.
bool sw_check_safe_mode(void);
bool sw_safe_mode(void);

// Act as if a button of the current bank was tapped: used by the expression
// pedals when they cross a threshold. Must be called from the main loop.
void sw_trigger_button(uint8_t sw);
// An expression pedal on Speed: the division every LFO and Seq goes at, an
// index into LFO_DIV_TICKS, or MOD_SPEED_OWN to give each its own back
#define MOD_SPEED_OWN	(0xFF)
void sw_set_mod_speed(uint8_t index);

// Ask for a bank change from outside the main loop (e.g. an incoming MIDI
// message handled in the USB interrupt). Applied by handle_switches.
void sw_request_bank(uint8_t bank);

// LED_Feedback: queue an incoming CC, Note On or Note Off (the three MIDI
// bytes) from the USB interrupt. handle_switches applies it to the toggle
// buttons whose command matches, without sending anything.
void sw_feedback_message(const uint8_t *data);

// The same, for a state read back from an amp that has no MIDI channel of its
// own (the Kemper): the command that sends this CC or note is matched whatever
// channel it carries, and LED_Feedback does not have to be on.
void sw_feedback_any_channel(const uint8_t *data);

// Remember the program last selected on a channel (0-15), whether by a PC
// command or by one arriving over USB, for the relative Program Change
// command to move from. A single byte store, safe from the USB interrupt.
void sw_note_program(uint8_t channel, uint8_t program);

// Virtual pedal: press (down) or release a switch from the USB interrupt, as
// SysEx PRESS_BUTTON does. 0-7 are the command switches, 8 Bank Down, 9 Bank
// Up. Applied by handle_switches exactly like a foot on the switch.
#define SW_VIRTUAL_BANK_DOWN	(8)
#define SW_VIRTUAL_BANK_UP		(9)
#define SW_VIRTUAL_COUNT		(10)
void sw_virtual_press(uint8_t id, uint8_t down);

// Per button/bank queries used by the display
uint8_t sw_button_is_toggle(uint8_t bank, uint8_t sw);
uint8_t sw_get_toggle_state(uint8_t bank, uint8_t sw);
// The BUTTON_LABEL_LEN chars a button shows: its own label, or for a cycle
// button the label of the state it last sent
const uint8_t *sw_button_label(uint8_t bank, uint8_t sw);
// One of the eight values a Var command keeps and an If command looks at
uint8_t sw_get_value(uint8_t which);

#endif /* INC_SWITCH_ROUTER_H_ */
