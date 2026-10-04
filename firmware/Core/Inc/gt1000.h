/*
 * gt1000.h
 *
 * Two way talk with a Boss GT-1000 or GT-1000CORE: the pedal asks the unit
 * for its state and follows what comes back, so the display shows the patch
 * you are on and the LEDs show which effects are running, whether they were
 * switched from the pedal, from the unit's own switches or from anywhere else.
 */

#ifndef INC_GT1000_H_
#define INC_GT1000_H_

#include <stdbool.h>
#include <stdint.h>

// GT1000_Mode is on in the configuration in use
bool gt1000_is_on(void);

// From the main loop: asks the unit what it is doing, and asks again what
// changed. Does nothing while GT1000_Mode is off.
void gt1000_task(void);

/*
 * A System Exclusive message that is not ours, handed over in the three byte
 * pieces it arrives in from the USB interrupt, put together and read when the
 * message ends. The caller still forwards them to the DIN output as before.
 */
void gt1000_sysex_chunk(const uint8_t *data, uint8_t len, bool is_end);

// Start again: called when the configuration changes, so nothing is carried
// over from the unit that was there before.
void gt1000_reset(void);

#endif /* INC_GT1000_H_ */
