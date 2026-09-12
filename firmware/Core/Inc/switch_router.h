/*
 * switch_router.h
 *
 *  Created on: 8 Jul 2021
 *      Author: D Harvie
 */

#ifndef INC_SWITCH_ROUTER_H_
#define INC_SWITCH_ROUTER_H_

#include <stdint.h>

void handle_switches(void);
void sw_led_init(void);
void update_leds_on_bank_change(void);
void set_all_leds(uint8_t state);
void setIsSuspended(uint8_t suspended);

// Current bank and per-button toggle bitmasks, for persisting/restoring state
uint8_t sw_get_current_page(void);
void sw_get_toggle_states(uint32_t out[8]);
void sw_get_long_toggle_states(uint32_t out[8]);
void sw_restore_state(uint8_t page, const uint32_t toggles[8], const uint32_t long_toggles[8]);

// Ask for a bank change from outside the main loop (e.g. an incoming MIDI
// message handled in the USB interrupt). Applied by handle_switches.
void sw_request_bank(uint8_t bank);

// Per button/bank queries used by the display
uint8_t sw_button_is_toggle(uint8_t bank, uint8_t sw);
uint8_t sw_get_toggle_state(uint8_t bank, uint8_t sw);

#endif /* INC_SWITCH_ROUTER_H_ */
