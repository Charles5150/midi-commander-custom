/*
 * tempo.h
 *
 * Tap tempo and MIDI clock generation.
 *
 * A Tap command records the time of each press; the tempo is the average of
 * the last few intervals. When the clock is running, 24 MIDI clock bytes per
 * quarter note are emitted to both USB and the DIN output.
 *
 * The clock is generated from the SysTick handler with fractional
 * accumulation, so the average tempo is exact even though the tick is 1 ms:
 * a tick is emitted whenever the accumulated time passes the interval, and
 * the remainder carries over. Jitter is therefore under a millisecond and
 * does not drift.
 */

#ifndef INC_TEMPO_H_
#define INC_TEMPO_H_

#include <stdint.h>
#include <stdbool.h>

#define TEMPO_BPM_MIN	(30)
#define TEMPO_BPM_MAX	(300)

void tempo_init(void);

// Register a tap. Returns the tempo in BPM known after this tap, or 0 if
// there is not enough information yet.
uint16_t tempo_tap(void);

void tempo_set_bpm(uint16_t bpm);
uint16_t tempo_get_bpm(void);

// Clock transport. Starting sends MIDI Start, stopping sends MIDI Stop.
void tempo_clock_start(void);
void tempo_clock_stop(void);
void tempo_clock_toggle(void);
bool tempo_clock_running(void);

// Called from SysTick every millisecond.
void tempo_tick_1ms(void);

// Called from the main loop: emits the clock bytes the tick asked for.
void tempo_task(void);

#endif /* INC_TEMPO_H_ */
