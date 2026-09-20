/*
 * kemper.h
 *
 * Two way talk with a Kemper Profiler (Player, Stage or head): the pedal asks
 * the amp to report itself and follows what comes back, so the display shows
 * the rig you are on and the LEDs show which effect modules are running,
 * whether they were switched from the pedal, from the amp's own buttons or
 * from anywhere else.
 */

#ifndef INC_KEMPER_H_
#define INC_KEMPER_H_

#include <stdbool.h>
#include <stdint.h>

// Kemper_Mode is on in the configuration in use
bool kemper_is_on(void);

// From the main loop: sends the beacon that keeps the amp reporting, and asks
// for the rig name after a change. Does nothing while Kemper_Mode is off.
void kemper_task(void);

/*
 * A System Exclusive message that is not ours, handed over in the three byte
 * pieces it arrives in from the USB interrupt. Too small to tell whose the
 * message is by the first one, so they are put together and read when the
 * message ends. The caller still forwards them to the DIN output as before.
 */
void kemper_sysex_chunk(const uint8_t *data, uint8_t len, bool is_end);

// Start again: called when the configuration changes, so nothing is carried
// over from the amp that was there before.
void kemper_reset(void);

#endif /* INC_KEMPER_H_ */
