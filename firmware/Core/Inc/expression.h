/*
 * expression.h
 *
 *  Expression pedal sampling and MIDI forwarding helpers.
 */

#ifndef INC_EXPRESSION_H_
#define INC_EXPRESSION_H_

#include <stdint.h>

void expression_init(void);
void expression_task(void);

// Live values for the calibration tool: filtered 12-bit ADC reading and the
// last CC value sent. pedal is 0 or 1.
uint16_t expression_get_raw(uint8_t pedal);
uint8_t expression_get_midi(uint8_t pedal);

#endif /* INC_EXPRESSION_H_ */
