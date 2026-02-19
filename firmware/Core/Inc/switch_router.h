/*
 * switch_router.h
 *
 *  Created on: 8 Jul 2021
 *      Author: D Harvie
 */

#ifndef INC_SWITCH_ROUTER_H_
#define INC_SWITCH_ROUTER_H_

void handle_switches(void);
void sw_led_init(void);
void update_leds_on_bank_change(void);
void set_all_leds(uint8_t state);
void setIsSuspended(uint8_t suspended);

#endif /* INC_SWITCH_ROUTER_H_ */
