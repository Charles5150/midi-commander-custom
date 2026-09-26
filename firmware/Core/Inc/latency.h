/*
 * latency.h
 *
 * How long a press takes to leave as MIDI, measured by the pedal itself.
 */

#ifndef INC_LATENCY_H_
#define INC_LATENCY_H_

#include <stdint.h>

#define LATENCY_SAMPLES		(16)	// the last presses kept

void latency_init(void);
uint32_t latency_now(void);
void latency_mark(uint32_t when);
void latency_take_mark(void);
void latency_begin(void);
void latency_end(void);
void latency_sent(void);
uint8_t latency_report(uint8_t *out, uint8_t clear);

#endif /* INC_LATENCY_H_ */
