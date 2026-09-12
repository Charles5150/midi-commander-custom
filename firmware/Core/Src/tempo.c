/*
 * tempo.c
 *
 * See tempo.h.
 */

#include "tempo.h"
#include "main.h"
#include "midi_cmds.h"
#include "midi_defines.h"
#include "flash_midi_settings.h"

#define TAPS_AVERAGED	(4)		// intervals averaged into the tempo
#define TAP_TIMEOUT_MS	(2500)	// a longer gap starts a new measurement
#define TAP_MIN_MS		(200)	// 300 BPM
#define TAP_MAX_MS		(2000)	// 30 BPM
#define CLOCKS_PER_BEAT	(24)	// MIDI standard

static uint16_t bpm = 120;
static volatile bool clock_running = false;

// Interval between clock bytes, in microseconds, and the accumulator the
// SysTick handler advances by 1000 us on every tick.
static volatile uint32_t clock_interval_us = 0;
static volatile uint32_t clock_acc_us = 0;
static volatile uint8_t clocks_due = 0;

// Tap measurement
static uint32_t last_tap_tick = 0;
static uint32_t intervals[TAPS_AVERAGED];
static uint8_t interval_count = 0;
static uint8_t interval_next = 0;

static void recalc_interval(void){
	uint32_t b = bpm ? bpm : 120;
	// 60 s / (bpm * 24) expressed in microseconds
	clock_interval_us = 60000000UL / (b * CLOCKS_PER_BEAT);
}

void tempo_init(void){
	bpm = 120;
	clock_running = false;
	interval_count = 0;
	interval_next = 0;
	last_tap_tick = 0;
	clock_acc_us = 0;
	clocks_due = 0;
	recalc_interval();
}

uint16_t tempo_get_bpm(void){
	return bpm;
}

void tempo_set_bpm(uint16_t new_bpm){
	if(new_bpm < TEMPO_BPM_MIN) new_bpm = TEMPO_BPM_MIN;
	if(new_bpm > TEMPO_BPM_MAX) new_bpm = TEMPO_BPM_MAX;
	bpm = new_bpm;
	recalc_interval();
}

uint16_t tempo_tap(void){
	uint32_t now = HAL_GetTick();
	uint32_t since = now - last_tap_tick;
	last_tap_tick = now;

	// First tap, or too long since the last one: start over
	if(interval_count == 0 && since > TAP_TIMEOUT_MS){
		return 0;
	}
	if(since > TAP_TIMEOUT_MS){
		interval_count = 0;
		interval_next = 0;
		return 0;
	}
	if(since < TAP_MIN_MS || since > TAP_MAX_MS){
		return bpm; // implausible interval (bounce or a very long wait): ignore
	}

	intervals[interval_next] = since;
	interval_next = (uint8_t)((interval_next + 1) % TAPS_AVERAGED);
	if(interval_count < TAPS_AVERAGED) interval_count++;

	uint32_t sum = 0;
	for(uint8_t i=0; i<interval_count; i++) sum += intervals[i];
	uint32_t avg_ms = sum / interval_count;
	if(avg_ms == 0) return bpm;

	tempo_set_bpm((uint16_t)((60000UL + avg_ms / 2) / avg_ms));
	return bpm;
}

void tempo_clock_start(void){
	if(clock_running) return;
	clock_acc_us = 0;
	clocks_due = 0;
	clock_running = true;
	midiCmd_send_start_command();
}

void tempo_clock_stop(void){
	if(!clock_running) return;
	clock_running = false;
	clocks_due = 0;
	midiCmd_send_stop_command();
}

void tempo_clock_toggle(void){
	if(clock_running) tempo_clock_stop();
	else tempo_clock_start();
}

bool tempo_clock_running(void){
	return clock_running;
}

/*
 * Called every millisecond. Only counts how many clock bytes are due; the
 * bytes themselves are sent from the main loop, so nothing MIDI happens in
 * interrupt context.
 */
void tempo_tick_1ms(void){
	if(!clock_running || clock_interval_us == 0) return;

	clock_acc_us += 1000UL;
	while(clock_acc_us >= clock_interval_us){
		clock_acc_us -= clock_interval_us;
		if(clocks_due < 8) clocks_due++;   // cap: never queue a burst
	}
}

void tempo_task(void){
	while(clocks_due){
		__disable_irq();
		clocks_due--;
		__enable_irq();
		midiCmd_send_clock_command();
	}
}
