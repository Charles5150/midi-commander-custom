/*
 * leds.h
 *
 * Software PWM for the ten front-panel LEDs (8 buttons + Bank Down / Up),
 * giving each LED a brightness level instead of just on/off. Driven from a
 * TIM2 interrupt at 8 kHz with 16 levels, i.e. a 500 Hz refresh, which is
 * flicker free.
 *
 * Two brightness values come from the configuration:
 *   LED_Brightness       level of a lit LED (button active, or blinking)
 *   LED_Rest_Brightness  level of an LED lit "at rest" by the Reverse and
 *                        AlwaysOn modes, so active and idle can differ
 */

#ifndef INC_LEDS_H_
#define INC_LEDS_H_

#include <stdint.h>

#define LEDS_COUNT			(10)
#define LEDS_LEVELS			(16)		// 0 = off .. 16 = fully on

// LED ids: 0-7 are buttons 1,2,3,4,A,B,C,D (same order as the switch table)
#define LED_ID_BANK_DOWN	(8)
#define LED_ID_BANK_UP		(9)

void leds_init(void);						// start the PWM timer, load brightness from config
void leds_set(uint8_t led, uint8_t level);	// level 0..LEDS_LEVELS
void leds_set_all(uint8_t level);

uint8_t leds_level_active(void);			// configured "on" level
uint8_t leds_level_rest(void);				// configured "lit at rest" level

#endif /* INC_LEDS_H_ */
