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

// External clock following
#define EXT_BEATS_MEASURED	(2)		// window the tempo is measured over
#define EXT_TIMEOUT_MS		(500)	// longer silence means the clock stopped
#define EXT_DISPLAY_STEP	(2)		// BPM change worth redrawing the display for

static volatile uint32_t ext_last_clock_tick = 0;
static volatile uint32_t ext_window_start = 0;
static volatile uint16_t ext_clock_count = 0;
static volatile uint16_t ext_bpm_measured = 0;	// 0 until a full window
static volatile bool ext_seen = false;
static volatile bool ext_restart = true;
static uint16_t ext_bpm_shown = 0;
static bool display_update = false;

static inline bool follow_enabled(void){
	return pGlobalSettings[GLOBAL_SETTINGS_CLOCK_FOLLOW] == 1;
}

void tempo_external_clock(void){
	if(!follow_enabled()) return;
	uint32_t now = HAL_GetTick();
	if(ext_restart || !ext_seen || (now - ext_last_clock_tick) > EXT_TIMEOUT_MS){
		// First clock of a new run: the measurement window starts here
		ext_restart = false;
		ext_window_start = now;
		ext_clock_count = 0;
		ext_last_clock_tick = now;
		ext_seen = true;
		return;
	}
	ext_last_clock_tick = now;
	if(++ext_clock_count >= CLOCKS_PER_BEAT * EXT_BEATS_MEASURED){
		uint32_t ms = now - ext_window_start;
		if(ms) ext_bpm_measured = (uint16_t)((60000UL * EXT_BEATS_MEASURED + ms / 2) / ms);
		ext_window_start = now;
		ext_clock_count = 0;
	}
}

void tempo_external_transport(uint8_t b){
	// Start or Continue: the next clock begins a fresh measurement
	if(b == 0xFA || b == 0xFB) ext_restart = true;
}

bool tempo_external_present(void){
	if(!follow_enabled() || !ext_seen) return false;
	uint32_t last = ext_last_clock_tick;	// read before now, so now >= last
	return (HAL_GetTick() - last) <= EXT_TIMEOUT_MS;
}

bool tempo_take_display_update(void){
	bool u = display_update;
	display_update = false;
	return u;
}

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
	bool ext = tempo_external_present();

	if(ext){
		uint16_t m = ext_bpm_measured;
		if(m >= TEMPO_BPM_MIN && m <= TEMPO_BPM_MAX){
			if(m != bpm) tempo_set_bpm(m);
			int d = (int)m - (int)ext_bpm_shown;
			if(ext_bpm_shown == 0 || d >= EXT_DISPLAY_STEP || d <= -EXT_DISPLAY_STEP){
				ext_bpm_shown = m;
				display_update = true;
			}
		}
	} else if(ext_bpm_shown){
		// Lost it: show the tempo again as soon as a clock returns
		ext_bpm_shown = 0;
		ext_bpm_measured = 0;
	}

	while(clocks_due){
		__disable_irq();
		clocks_due--;
		__enable_irq();
		if(!ext){
			midiCmd_send_clock_command();
		} else if(!pGlobalSettings[GLOBAL_SETTINGS_REALTIME_PASS]){
			// The host's clock is not forwarded, so re-clock the DIN output
			// at its tempo; USB already has the host's own clock
			midiCmd_send_byte_serial(0xF8);
		}
		// With passthrough on, the host's clock already reaches DIN: stay quiet
	}
}
