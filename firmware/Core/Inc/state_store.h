/*
 * state_store.h
 *
 * Persists the current bank and the per-button toggle states across power
 * cycles, in a journal kept in its own flash page so it survives the
 * configuration being re-flashed.
 */

#ifndef INC_STATE_STORE_H_
#define INC_STATE_STORE_H_

#include <stdint.h>
#include <stdbool.h>

// Load the last saved state, including the configuration slot that was
// active. Returns false if nothing valid is stored.
bool state_store_load(uint8_t *bank, uint32_t toggles[8], uint32_t long_toggles[8], uint8_t *slot);

// Call whenever the bank or a toggle state changes. The save itself is
// deferred until the state has been stable for a couple of seconds.
void state_store_mark_dirty(void);

// Call from the main loop.
void state_store_task(void);
// Save a pending change now, before the main loop stops calling the task
void state_store_flush(void);

#endif /* INC_STATE_STORE_H_ */
