/*
 * expression.h
 *
 *  Expression pedal sampling and MIDI forwarding helpers.
 */

#ifndef INC_EXPRESSION_H_
#define INC_EXPRESSION_H_

#include <stdint.h>
#include <stdbool.h>

void expression_init(void);
void expression_task(void);
// Safe mode: after expression_init, keep the pedals' first position unsent;
// they speak from their first movement on
void expression_quiet_start(void);

// Live values for the calibration tool: filtered 12-bit ADC reading and the
// last CC value sent. pedal is 0 or 1.
uint16_t expression_get_raw(uint8_t pedal);
uint8_t expression_get_midi(uint8_t pedal);

// Exp commands: send pedal to cc (EXP_TARGET_OFF silences it, EXP_TARGET_RESET
// gives it back its own target) on channel 1-16, or 0 for its own channel.
void expression_set_target(uint8_t pedal, uint8_t cc, uint8_t channel);
void expression_clear_targets(void);

// A pedal moved from the computer (SysEx SET_PEDAL): held at position 0
// (heel) to 16383 (toe) of its calibrated travel, as if by foot, until
// released back to its jack. Called from the USB interrupt.
void expression_set_virtual(uint8_t pedal, bool hold, uint16_t position);

#endif /* INC_EXPRESSION_H_ */
