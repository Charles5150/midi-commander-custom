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

/*
 * True during the short flash at the start of each beat, for the tap LED.
 * The beat is the host's while its clock is followed, the pedal's clock while
 * it runs, and otherwise the tempo running freely from the last tap.
 */
bool tempo_beat_flash(void);

/*
 * Following an external clock (Clock_Follow). The USB receive path reports
 * every clock byte and Start/Continue; the tempo is measured over two beats.
 * While that clock keeps arriving the pedal adopts its tempo and does not
 * emit a clock of its own on top of it. If it stops, the internal clock, if
 * running, carries on at the adopted tempo.
 */
void tempo_external_clock(void);			// interrupt context, 0xF8
void tempo_external_transport(uint8_t b);	// interrupt context, 0xFA / 0xFB
bool tempo_external_present(void);

// True once each time the display should show a changed external tempo.
bool tempo_take_display_update(void);

#endif /* INC_TEMPO_H_ */
