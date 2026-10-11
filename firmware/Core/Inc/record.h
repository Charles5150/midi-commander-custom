/*
 * record.h
 *
 * Recorded runs of presses (1.24). Played once with the clock running, the
 * presses of a bank's eight switches are kept with the beat each began on;
 * from then on, whenever the clock runs in that bank, the pedal presses them
 * itself on those beats, as a foot would. See record.c.
 */

#ifndef INC_RECORD_H_
#define INC_RECORD_H_

#include <stdint.h>
#include <stdbool.h>

// How a recorded press ended, so it is played back as the same press
#define REC_HOLD_FREE	(0)	// any length: a button with no long press list
#define REC_HOLD_SHORT	(1)	// let go before the long press threshold
#define REC_HOLD_LONG	(2)	// held past it

// The Tap command's recording actions (TAP_MODE_RECORD, _PLAYBACK, _ERASE)
void record_toggle(void);
void record_playback_toggle(void);
void record_erase(void);

// True while a recording waits for the clock or is under way, for the LEDs
bool record_active(void);

// A command switch went down or up, from handle_switches
void record_switch_down(uint8_t sw, bool second);
void record_switch_up(uint8_t sw, uint8_t hold);

// Called from handle_switches: starts and ends recordings, plays them back
void record_task(void);

#endif /* INC_RECORD_H_ */
