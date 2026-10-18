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
#include "switch_router.h"

#define TAPS_AVERAGED	(4)		// intervals averaged into the tempo
#define TAP_TIMEOUT_MS	(2500)	// a longer gap starts a new measurement
#define TAP_MIN_MS		(200)	// 300 BPM
#define TAP_MAX_MS		(2000)	// 30 BPM
#define CLOCKS_PER_BEAT	(24)	// MIDI standard

static uint16_t bpm = 120;
static uint8_t tempo_sets = 0;	// counts every tempo set, for Tap Out
static volatile bool clock_running = false;

// Interval between clock bytes, in microseconds, and the accumulator the
// SysTick handler advances by 1000 us on every tick.
static volatile uint32_t clock_interval_us = 0;
static volatile uint32_t clock_acc_us = 0;
static volatile uint8_t clocks_due = 0;
// Clocks a burst (Clock_Burst) still sends, counted from a Start or a tempo
// set; BURST_NONE with no burst, when the clock goes out all along
#define BURST_NONE	(0xFFFF)
static uint16_t burst_left = BURST_NONE;

// The outputs Clock_Output turns off for the clock: CHAN_NO_USB, CHAN_NO_DIN
static uint8_t clock_off(void){
	const uint8_t *c = flash_settings_clock();
	return c ? (uint8_t)~c[0] & (CHAN_NO_USB | CHAN_NO_DIN) : 0;
}

static uint16_t burst_clocks(void){
	const uint8_t *c = flash_settings_clock();
	return c && (uint8_t)(c[1] - 1U) < CLOCK_BURST_MAX ? (uint16_t)(c[1] * CLOCKS_PER_BEAT) : BURST_NONE;
}

// Tap measurement
static uint32_t last_tap_tick = 0;
static bool tapped = false;	// no tap yet: the first one is not timed from boot
static uint32_t intervals[TAPS_AVERAGED];
static uint8_t interval_count = 0;
static uint8_t interval_next = 0;

// Beats, for the tap LED. The internal beat follows the running clock (a beat
// every 24 clock bytes, the first one right after Start) or, with the clock
// stopped, runs freely at the tempo, re-phased by every tap. The external beat
// counts the host's clock bytes the same way.
#define FLASH_MAX_MS	(100)	// length of the flash, at most a quarter beat

static volatile uint32_t int_beat_tick = 0;
static volatile uint32_t int_beat_num = 0;	// beats so far, for the LFOs
static volatile uint8_t clock_beat_count = 0;	// clocks sent since the last beat
static volatile uint32_t free_acc_us = 0;
static volatile uint32_t ext_beat_tick = 0;
static volatile uint32_t ext_beat_num = 0;
static volatile uint8_t ext_beat_count = 0;

// Bars, for a Wait on the grid: the beat each count starts its bars on. The
// pedal's clock starts one on its first beat after Start, the free beat on
// the first tap of a new tempo, and the host's clock on the beat its Start
// begins, or the one its Continue picks up from the last Song Position.
#define GRID_GRACE_MS	(40)	// a press this late is still on the beat

static volatile uint32_t int_bar_first = 0;
static volatile uint32_t ext_bar_first = 0;
static volatile uint32_t ext_song_clocks = 0;	// where the host's next run starts
static volatile bool ext_playing = false;	// between the host's Start or Continue and its Stop

// External clock following
#define EXT_BEATS_MEASURED	(2)		// window the tempo is measured over
#define EXT_TIMEOUT_MS		(500)	// longer silence means the clock stopped
#define EXT_DISPLAY_STEP	(2)		// BPM change worth redrawing the display for

static volatile uint32_t ext_last_clock_tick = 0;
static volatile uint32_t ext_window_start = 0;
static volatile uint16_t ext_clock_count = 0;
static volatile uint16_t ext_bpm_measured = 0;	// 0 until a full window
static volatile bool ext_seen = false;
static volatile uint32_t any_clock_tick = 0;	// last clock from the host, followed or not
static volatile bool ext_restart = true;
static uint16_t ext_bpm_shown = 0;
static bool display_update = false;

static inline bool follow_enabled(void){
	return pGlobalSettings[GLOBAL_SETTINGS_CLOCK_FOLLOW] == 1;
}

void tempo_external_clock(void){
	uint32_t now = HAL_GetTick();
	any_clock_tick = now;
	if(!follow_enabled()) return;
	if(ext_restart || !ext_seen || (now - ext_last_clock_tick) > EXT_TIMEOUT_MS){
		// First clock of a new run: the measurement window starts here
		ext_restart = false;
		ext_window_start = now;
		ext_clock_count = 0;
		ext_last_clock_tick = now;
		ext_seen = true;
		// The song may pick up half way through a beat
		uint32_t pos = ext_song_clocks;
		ext_song_clocks = 0;
		if(pos % CLOCKS_PER_BEAT == 0){
			ext_beat_tick = now;
			ext_beat_num++;
		} else {
			// When that beat began, at the tempo known so far
			ext_beat_tick = now - (pos % CLOCKS_PER_BEAT) * clock_interval_us / 1000;
		}
		ext_beat_count = (uint8_t)((pos + 1) % CLOCKS_PER_BEAT);
		ext_bar_first = ext_beat_num - pos / CLOCKS_PER_BEAT;
		return;
	}
	ext_last_clock_tick = now;
	if(ext_beat_count == 0){
		ext_beat_tick = now;
		ext_beat_num++;
	}
	ext_beat_count = (uint8_t)((ext_beat_count + 1) % CLOCKS_PER_BEAT);
	if(++ext_clock_count >= CLOCKS_PER_BEAT * EXT_BEATS_MEASURED){
		uint32_t ms = now - ext_window_start;
		if(ms) ext_bpm_measured = (uint16_t)((60000UL * EXT_BEATS_MEASURED + ms / 2) / ms);
		ext_window_start = now;
		ext_clock_count = 0;
	}
}

void tempo_external_transport(uint8_t b){
	// Start or Continue: the next clock begins a fresh measurement
	if(b == 0xFA) ext_song_clocks = 0;
	if(b == 0xFA || b == 0xFB) ext_restart = true;
	ext_playing = (b != 0xFC);
}

void tempo_external_position(uint16_t sixteenths){
	ext_song_clocks = (uint32_t)sixteenths * (CLOCKS_PER_BEAT / 4);
}

bool tempo_external_present(void){
	if(!follow_enabled() || !ext_seen) return false;
	uint32_t last = ext_last_clock_tick;	// read before now, so now >= last
	return (HAL_GetTick() - last) <= EXT_TIMEOUT_MS;
}

bool tempo_keeping_time(void){
	uint32_t last = any_clock_tick;	// read before now, so now >= last
	return clock_running || (HAL_GetTick() - last) <= EXT_TIMEOUT_MS;
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
	tapped = false;
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
	tempo_sets++;
	burst_left = burst_clocks();
	recalc_interval();
}

uint16_t tempo_tap(void){
	uint32_t now = HAL_GetTick();
	uint32_t since = tapped ? now - last_tap_tick : UINT32_MAX;
	last_tap_tick = now;
	tapped = true;

	// The tap is a beat: with the clock stopped the LED flashes with the foot
	if(!clock_running){
		__disable_irq();
		free_acc_us = 0;
		int_beat_tick = now;
		int_beat_num++;
		__enable_irq();
	}

	// First tap, or too long since the last one: start over, and on a bar
	if(since > TAP_TIMEOUT_MS && !clock_running) int_bar_first = int_beat_num;
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
	__disable_irq();
	clock_acc_us = 0;
	clocks_due = 0;
	clock_beat_count = 0;
	int_bar_first = int_beat_num + 1;	// the first clock is its first beat
	clock_running = true;
	__enable_irq();
	burst_left = burst_clocks();
	midiCmd_send_realtime(0xFA, clock_off());
}

void tempo_clock_stop(void){
	if(!clock_running) return;
	__disable_irq();
	clock_running = false;
	clocks_due = 0;
	// The free beat carries on in the phase the clock left it
	free_acc_us = (uint32_t)((clock_beat_count + CLOCKS_PER_BEAT - 1) % CLOCKS_PER_BEAT)
			* clock_interval_us + clock_acc_us;
	__enable_irq();
	midiCmd_send_realtime(0xFC, clock_off());
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
	if(clock_interval_us == 0) return;

	if(clock_running){
		clock_acc_us += 1000UL;
		while(clock_acc_us >= clock_interval_us){
			clock_acc_us -= clock_interval_us;
			if(clocks_due < 8) clocks_due++;   // cap: never queue a burst
			if(clock_beat_count == 0){
				int_beat_tick = HAL_GetTick();
				int_beat_num++;
			}
			clock_beat_count = (uint8_t)((clock_beat_count + 1) % CLOCKS_PER_BEAT);
		}
	} else {
		uint32_t beat_us = clock_interval_us * CLOCKS_PER_BEAT;
		free_acc_us += 1000UL;
		if(free_acc_us >= beat_us){
			free_acc_us -= beat_us;
			if(free_acc_us >= beat_us) free_acc_us = 0;	// tempo just got faster
			int_beat_tick = HAL_GetTick();
			int_beat_num++;
		}
	}
}

bool tempo_beat_flash(void){
	uint32_t beat = tempo_external_present() ? ext_beat_tick : int_beat_tick;
	uint32_t flash = 60000UL / (bpm ? bpm : 120) / 4;
	if(flash > FLASH_MAX_MS) flash = FLASH_MAX_MS;
	return (HAL_GetTick() - beat) < flash;
}

void tempo_beat_now(uint32_t *beat, uint32_t *ms_since){
	bool ext = tempo_external_present();
	__disable_irq();
	uint32_t tick = ext ? ext_beat_tick : int_beat_tick;
	*beat = ext ? ext_beat_num : int_beat_num;
	__enable_irq();
	*ms_since = HAL_GetTick() - tick;
}

bool tempo_bar_beat(uint8_t per_bar, uint32_t *bar, uint8_t *beat){
	bool ext = tempo_external_present();
	if(!per_bar || (ext ? !ext_playing : !clock_running)) return false;
	__disable_irq();
	int32_t d = (int32_t)(ext ? ext_beat_num - ext_bar_first : int_beat_num - int_bar_first);
	__enable_irq();
	if(d < 0) return false;	// Start sent, its first beat not yet
	*bar = (uint32_t)d / per_bar + 1;
	*beat = (uint8_t)((uint32_t)d % per_bar + 1);
	return true;
}

bool tempo_song_clock(uint32_t *clocks){
	bool ext = tempo_external_present();
	if(ext ? !ext_playing : !clock_running) return false;
	__disable_irq();
	int32_t d = (int32_t)(ext ? ext_beat_num - ext_bar_first : int_beat_num - int_bar_first);
	uint8_t count = ext ? ext_beat_count : clock_beat_count;
	__enable_irq();
	if(d < 0) return false;
	// The beat's first clock leaves its count at 1, its last at 0
	*clocks = (uint32_t)d * CLOCKS_PER_BEAT + (uint32_t)((count + CLOCKS_PER_BEAT - 1) % CLOCKS_PER_BEAT);
	return true;
}

uint32_t tempo_grid_wait(uint8_t beats, uint32_t *target, bool *ext, bool count){
	*ext = tempo_external_present();
	__disable_irq();
	uint32_t num = *ext ? ext_beat_num : int_beat_num;
	uint32_t tick = *ext ? ext_beat_tick : int_beat_tick;
	uint32_t first = *ext ? ext_bar_first : int_bar_first;
	__enable_irq();
	uint32_t since = HAL_GetTick() - tick;
	if(!beats) beats = 1;

	// Beats into the grid; just before the pedal's first beat it is -1
	int32_t d = (int32_t)(num - first) % beats;
	uint32_t into = (uint32_t)(d < 0 ? d + beats : d);
	bool on_beat = into == 0 && since < GRID_GRACE_MS && (int32_t)(num - first) >= 0;
	if(on_beat && !count) return 0;

	// A count-in counts a whole bar at least: from this beat, or the next bar
	uint32_t left = beats - into;
	if(count && into) left += beats;
	*target = num + left;
	uint32_t beat_ms = 60000UL / (bpm ? bpm : 120);
	uint32_t ms = left * beat_ms;
	ms = (ms > since) ? ms - since : 0;
	return ms + beat_ms;	// a beat late at most, should the clock stall
}

/*
 * Tap out. A device that takes a tap CC but not the clock gets one on each
 * beat the tap LED shows, so the first two are a whole beat apart and the
 * taps line up with the pedal's own; a tap on the pedal is a beat too, so
 * tapping the pedal taps the device as well, and the run goes on after it.
 */
#define TAPOUT_SLOTS	(4)

typedef struct {
	uint32_t beat;		// the last beat seen
	uint32_t sent;		// when the last tap went
	uint8_t sets;		// the tempo set the run is for
	uint8_t channel, cc, value;
	uint8_t count;		// taps a run sends, 0 for every beat
	uint8_t left;
	bool active;
} tapout_t;

static tapout_t tapouts[TAPOUT_SLOTS];

void tempo_tapout_start(uint8_t channel, uint8_t cc, uint8_t value, uint8_t count){
	tapout_t *t = NULL;
	for(uint8_t i=0; i<TAPOUT_SLOTS && t == NULL; i++){
		if(tapouts[i].active && tapouts[i].channel == channel && tapouts[i].cc == cc) t = &tapouts[i];
	}
	for(uint8_t i=0; i<TAPOUT_SLOTS && t == NULL; i++){
		if(!tapouts[i].active) t = &tapouts[i];
	}
	if(t == NULL) return;
	uint32_t ms;
	tempo_beat_now(&t->beat, &ms);
	t->sets = tempo_sets;
	t->sent = HAL_GetTick() - 60000UL;
	t->channel = channel;
	t->cc = cc;
	t->value = value;
	t->count = count;
	t->left = count;
	t->active = true;
}

void tempo_tapout_stop(uint8_t channel, uint8_t cc){
	for(uint8_t i=0; i<TAPOUT_SLOTS; i++){
		if(tapouts[i].channel == channel && tapouts[i].cc == cc) tapouts[i].active = false;
	}
}

void tempo_tapout_stop_all(void){
	for(uint8_t i=0; i<TAPOUT_SLOTS; i++) tapouts[i].active = false;
}

static void tapout_task(void){
	uint32_t beat, ms;
	tempo_beat_now(&beat, &ms);
	for(uint8_t i=0; i<TAPOUT_SLOTS; i++){
		tapout_t *t = &tapouts[i];
		if(!t->active) continue;
		if(t->sets != tempo_sets){	// a tempo set, even the same again: a new run
			t->sets = tempo_sets;
			t->left = t->count;
		}
		if(beat == t->beat) continue;
		t->beat = beat;
		// A tap on the pedal right on the free beat makes two beats at once:
		// the device gets one tap, never two a moment apart
		uint32_t now = HAL_GetTick();
		if(now - t->sent < 30000UL / (bpm ? bpm : 120)) continue;
		if(t->count){
			if(!t->left) continue;
			t->left--;
		}
		midiCmd_send_cc(t->channel, t->cc, t->value);
		t->sent = now;
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

	// Where the clock goes: nowhere in a bank Clock_Off_Banks names
	const uint8_t *c = flash_settings_clock();
	uint8_t off = clock_off();
	if(c && !((*(const uint32_t*)(c + 2) >> sw_get_home_bank()) & 1U)) off = CHAN_NO_USB | CHAN_NO_DIN;
	while(clocks_due){
		__disable_irq();
		clocks_due--;
		__enable_irq();
		if(!ext){
			// A burst runs its time out in a bank without the clock too
			if(burst_left){
				if(burst_left != BURST_NONE) burst_left--;
				midiCmd_send_clock_command(off);
			}
		} else if(pGlobalSettings[GLOBAL_SETTINGS_REALTIME_PASS] != 1){
			// The host's clock is not forwarded, so re-clock the DIN output
			// at its tempo; USB already has the host's own clock
			if(!(off & CHAN_NO_DIN)) midiCmd_send_byte_serial(0xF8);
		}
		// With passthrough on, the host's clock already reaches DIN: stay quiet
	}
	tapout_task();
}
