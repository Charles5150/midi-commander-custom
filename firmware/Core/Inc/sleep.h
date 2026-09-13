/*
 * sleep.h
 *
 * Idle sleep: after a configurable time with nobody touching the pedal, the
 * display and the LEDs are switched off. Any press or expression pedal
 * movement brings them straight back.
 *
 * This complements the USB suspend path in usbd_conf.c, which only fires when
 * a host suspends the bus. On batteries there is no host, so without this
 * nothing ever switched off.
 *
 * Unlike USB suspend, presses are NOT blocked while asleep: the press that
 * wakes the pedal also does its job, because on stage a lost press is worse
 * than a bright screen.
 */

#ifndef INC_SLEEP_H_
#define INC_SLEEP_H_

#include <stdint.h>

void sleep_init(void);

// Called from the switch scan (interrupt context) and the expression pedals.
// Must stay trivial: it only takes a timestamp.
void sleep_note_activity(void);

// Called from the main loop: decides when to switch off and when to come back.
void sleep_task(void);

uint8_t sleep_is_asleep(void);

#endif /* INC_SLEEP_H_ */
