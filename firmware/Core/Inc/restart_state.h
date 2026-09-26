/*
 * restart_state.h
 *
 * Coming back where the pedal was after the watchdog restarts it, from a copy
 * of the live state kept in RAM, which a reset leaves as it was.
 */

#ifndef INC_RESTART_STATE_H_
#define INC_RESTART_STATE_H_

#include <stdint.h>
#include <stdbool.h>

typedef struct {
	uint32_t toggles[8];
	uint32_t long_toggles[8];
	uint16_t bpm;
	uint8_t bank;
	uint8_t slot;
} live_state_t;

// Call once at boot, first thing: true when this start is the watchdog's and
// the copy is sound, with the state it held. Clears the reset flags.
bool restart_state_load(live_state_t *out);

// Call from the main loop: keeps the copy up to date.
void restart_state_task(void);

#endif /* INC_RESTART_STATE_H_ */
