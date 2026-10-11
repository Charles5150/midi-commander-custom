/*
 * record.c
 *
 * See record.h.
 *
 * Recording. A Record command arms the bank it is pressed in. The recording
 * begins with the clock's first beat, or at once if the clock runs already,
 * and keeps every press of the bank's eight switches as a gesture: the beat
 * nearest to where the foot went down, which switch, how long it was held,
 * in clocks, whether a second press made it a double press, and whether it
 * was a short or a long press for a button that tells them apart. Positions
 * count from the first beat of the run, as the bar and beat on the display
 * do, so a song played from Start always lines up. It ends, and is kept, when
 * the clock stops, the bank or the configuration changes, or Record is
 * pressed again; a press still held then, as the one that ended it, is left
 * out. A recording with nothing in it leaves the one before it alone.
 *
 * Playback. Whenever the clock runs in a bank with a recording, from Start
 * or from wherever a host's Continue picks up, each gesture presses its
 * switch on its beat through the virtual pedal, so short, long and double
 * presses, combinations, LEDs and toggles all go exactly as with a foot. A
 * long press is held past the threshold whatever the tempo, a short one let
 * go before it. Leaving the bank, or the clock stopping, ends it. Playback
 * can be switched off and on, and a bank being recorded does not play, nor
 * one with the on-pedal editor open.
 *
 * Storage. One flash page, a log of entries appended one after the other:
 *   [0] gestures, 0 for none (erased)   [1] bank
 *   [2] slot                            [3] REC_MARKER, written last
 *   then 6 bytes per gesture:
 *   [0..1] beat (LE)   [2..3] hold in clocks (LE)
 *   [4] switch in bits 0-2, REC_DOUBLE, the hold in bits 4-5   [5] 0xFF
 * The latest entry of a slot and bank is its recording. When the page is
 * full it is rewritten with the latest entries alone; that erase stalls the
 * pedal for a moment, so it waits while the clock runs.
 */

#include "record.h"
#include "main.h"
#include "tempo.h"
#include "display.h"
#include "switch_router.h"
#include "editor.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include <string.h>
#include <stdio.h>

#define CLOCKS_PER_BEAT		(24)
#define REC_MAX				(128)	// gestures in one recording
#define REC_PAGE_SIZE		(FLASH_PAGE_SIZE)
#define REC_HEADER			(4U)
#define REC_GESTURE			(6U)
#define REC_MARKER			(0x5CU)
#define REC_DOUBLE			(0x08U)
#define REC_HOLD_SHIFT		(4)
#define REC_OPEN			(0x80U)	// in RAM only: not let go yet

#define TAP_GAP_MS			(40U)	// the first tap of a double press, and the gap after it
#define THRESHOLD_MARGIN_MS	(30U)	// a short press lets go this much before the threshold

typedef struct {
	uint16_t beat;
	uint16_t hold;
	uint8_t flags;
} gesture_t;

enum { REC_OFF, REC_ARMED, REC_ON };

static uint8_t rec_state = REC_OFF;
static uint8_t rec_bank, rec_slot;
static gesture_t rec[REC_MAX];
static uint8_t rec_count = 0;
static uint8_t rec_open[MIDI_NUM_SWITCHES];		// gesture of a switch still down, or 0xFF
static uint8_t rec_last[MIDI_NUM_SWITCHES];		// its last gesture, for a second press
static uint32_t rec_down_pos[MIDI_NUM_SWITCHES];
static uint32_t rec_pos = 0;			// where the run is, for the presses
static bool rec_pos_valid = false;
static bool rec_full_shown = false;
static bool save_pending = false;		// kept, waiting for the clock to stop

static bool play_on = true;
static bool playing = false;
static uint8_t play_bank, play_slot;
static uint32_t play_last_pos = 0;
static const uint8_t *play_entry = NULL;
static uint8_t play_next = 0;
static uint8_t store_gen = 0, play_gen = 0;	// a write may move every entry

// A switch being pressed by the playback
enum { V_IDLE, V_TAP, V_GAP, V_HOLD };
typedef struct {
	uint8_t phase;
	uint8_t kind;
	uint16_t hold;
	uint32_t pos0;
	uint32_t t0;
} voice_t;
static voice_t voice[MIDI_NUM_SWITCHES];

static uint8_t page_buf[REC_PAGE_SIZE];

/* ---------------------------------------------------------------- storage */

static inline const uint8_t *page(void){
	return (const uint8_t *)FLASH_RECORD_ADDR;
}

static inline uint32_t entry_size(const uint8_t *e){
	return REC_HEADER + (uint32_t)e[0] * REC_GESTURE;
}

static inline bool entry_valid(const uint8_t *e){
	return e[3] == REC_MARKER && e[1] < MIDI_NUM_BANKS && e[2] < CONFIG_SLOTS && e[0] <= REC_MAX;
}

/*
 * Walks the log: calls back with every entry, valid or not, and returns
 * where the free space begins, or REC_PAGE_SIZE when something written but
 * not finished is in the way and only a rewrite gets past it.
 */
static uint32_t log_end(void){
	const uint8_t *p = page();
	uint32_t off = 0;
	while(off + REC_HEADER <= REC_PAGE_SIZE){
		const uint8_t *e = p + off;
		if(e[0] == 0xFF && e[1] == 0xFF && e[2] == 0xFF && e[3] == 0xFF) break;
		if(e[0] > REC_MAX) return REC_PAGE_SIZE;	// torn: no length to skip by
		off += entry_size(e);
	}
	if(off > REC_PAGE_SIZE) return REC_PAGE_SIZE;
	// Everything after must be erased, or writing there would fail
	for(uint32_t i=off; i<REC_PAGE_SIZE; i++){
		if(p[i] != 0xFF) return REC_PAGE_SIZE;
	}
	return off;
}

// The latest entry of a slot and bank, or NULL. An erased one counts too.
static const uint8_t *find_entry(uint8_t slot, uint8_t bank){
	const uint8_t *p = page();
	const uint8_t *found = NULL;
	uint32_t off = 0;
	while(off + REC_HEADER <= REC_PAGE_SIZE){
		const uint8_t *e = p + off;
		if(e[0] > REC_MAX) break;	// erased, or torn
		if(off + entry_size(e) > REC_PAGE_SIZE) break;
		if(entry_valid(e) && e[1] == bank && e[2] == slot) found = e;
		off += entry_size(e);
	}
	return found;
}

static const uint8_t *find_recording(uint8_t slot, uint8_t bank){
	const uint8_t *e = find_entry(slot, bank);
	return (e && e[0]) ? e : NULL;
}

static void read_gesture(const uint8_t *e, uint8_t n, gesture_t *g){
	const uint8_t *q = e + REC_HEADER + (uint32_t)n * REC_GESTURE;
	g->beat = (uint16_t)(q[0] | (q[1] << 8));
	g->hold = (uint16_t)(q[2] | (q[3] << 8));
	g->flags = q[4];
}

static bool program(uint32_t addr, const uint8_t *data, uint32_t len){
	for(uint32_t i=0; i<len; i+=2){
		uint16_t half = (uint16_t)(data[i] | (((i + 1 < len) ? data[i + 1] : 0xFF) << 8));
		if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, addr + i, half) != HAL_OK) return false;
	}
	return true;
}

/*
 * Rewrites the page with the latest entry of every slot and bank but the one
 * about to be replaced, leaving out erased ones. Returns where the free space
 * then begins.
 */
static uint32_t compact(uint8_t slot, uint8_t bank){
	const uint8_t *p = page();
	uint32_t len = 0, off = 0;
	while(off + REC_HEADER <= REC_PAGE_SIZE){
		const uint8_t *e = p + off;
		if(e[0] > REC_MAX || off + entry_size(e) > REC_PAGE_SIZE) break;
		if(entry_valid(e) && e[0] && !(e[1] == bank && e[2] == slot)
				&& find_entry(e[2], e[1]) == e){
			memcpy(page_buf + len, e, entry_size(e));
			len += entry_size(e);
		}
		off += entry_size(e);
	}
	FLASH_EraseInitTypeDef erase = {
			.TypeErase = FLASH_TYPEERASE_PAGES,
			.Banks = FLASH_BANK_1,
			.PageAddress = FLASH_RECORD_ADDR,
			.NbPages = 1
	};
	uint32_t error;
	if(HAL_FLASHEx_Erase(&erase, &error) != HAL_OK) return REC_PAGE_SIZE;
	if(len && !program(FLASH_RECORD_ADDR, page_buf, len)) return REC_PAGE_SIZE;
	return len;
}

/*
 * Appends an entry: the header's first half, the gestures, then the half
 * with the marker, so one cut short is never taken for a recording. Rewrites
 * the page first when it has no room, unless `may_erase` is false; returns
 * false then, or when even a rewritten page has no room.
 */
static bool append(uint8_t slot, uint8_t bank, const gesture_t *g, uint8_t n, bool may_erase, bool *no_room){
	uint32_t size = REC_HEADER + (uint32_t)n * REC_GESTURE;
	*no_room = false;
	uint32_t off = log_end();
	if(off + size > REC_PAGE_SIZE && !may_erase) return false;

	uint32_t start = flash_hold();
	bool ok = true;
	if(off + size > REC_PAGE_SIZE){
		off = compact(slot, bank);
		if(off + size > REC_PAGE_SIZE){
			*no_room = true;
			ok = false;
		}
	}
	if(ok){
		uint8_t head[2] = { n, bank };
		ok = program(FLASH_RECORD_ADDR + off, head, 2);
		for(uint8_t i=0; ok && i<n; i++){
			uint8_t q[REC_GESTURE] = {
				(uint8_t)g[i].beat, (uint8_t)(g[i].beat >> 8),
				(uint8_t)g[i].hold, (uint8_t)(g[i].hold >> 8),
				(uint8_t)(g[i].flags & ~REC_OPEN), 0xFF };
			ok = program(FLASH_RECORD_ADDR + off + REC_HEADER + (uint32_t)i * REC_GESTURE, q, REC_GESTURE);
		}
		uint8_t tail[2] = { slot, REC_MARKER };
		if(ok) ok = program(FLASH_RECORD_ADDR + off + 2, tail, 2);
	}
	flash_release(start);
	store_gen++;
	return ok;
}

/* -------------------------------------------------------------- recording */

static bool quiet(void){
	uint32_t pos;
	return !tempo_song_clock(&pos) && !sw_modulating();
}

static void show_count(const char *what, uint8_t n){
	char msg[13];
	snprintf(msg, sizeof(msg), "%s %u", what, (unsigned)n);
	display_show_message(msg);
}

// Writes the recording kept in RAM, now or once the clock has stopped
static void save(bool now){
	bool no_room;
	save_pending = false;
	if(append(rec_slot, rec_bank, rec, rec_count, now || quiet(), &no_room)) return;
	if(no_room) display_show_message("NO ROOM");
	else save_pending = true;
}

static void finish(void){
	rec_state = REC_OFF;
	// A press still down, the one that ended the recording above all, is left out
	uint8_t n = 0;
	for(uint8_t i=0; i<rec_count; i++){
		if(!(rec[i].flags & REC_OPEN)) rec[n++] = rec[i];
	}
	rec_count = n;
	if(n == 0){
		display_show_message("REC NONE");
		return;
	}
	show_count("SAVED", n);
	save(false);
}

static void begin(void){
	rec_state = REC_ON;
	rec_count = 0;
	rec_full_shown = false;
	memset(rec_open, 0xFF, sizeof(rec_open));
	memset(rec_last, 0xFF, sizeof(rec_last));
	display_show_message("REC");
}

void record_toggle(void){
	if(rec_state == REC_ON){
		finish();
		return;
	}
	if(rec_state == REC_ARMED){
		rec_state = REC_OFF;
		display_show_message("REC OFF");
		return;
	}
	if(save_pending) save(true);	// one recording kept in RAM at a time
	rec_bank = sw_get_current_page();
	rec_slot = flash_settings_active_slot();
	uint32_t pos;
	if(tempo_song_clock(&pos)){
		rec_pos = pos;
		begin();
	} else {
		rec_state = REC_ARMED;
		display_show_message("REC WAIT");
	}
}

void record_playback_toggle(void){
	play_on = !play_on;
	display_show_message(play_on ? "PLAY ON" : "PLAY OFF");
}

void record_erase(void){
	uint8_t bank = sw_get_current_page();
	uint8_t slot = flash_settings_active_slot();
	if(rec_state != REC_OFF && rec_bank == bank) rec_state = REC_OFF;
	if(save_pending && rec_bank == bank && rec_slot == slot) save_pending = false;
	if(find_recording(slot, bank) == NULL){
		display_show_message("NO REC");
		return;
	}
	bool no_room;
	append(slot, bank, NULL, 0, true, &no_room);
	display_show_message("ERASED");
}

bool record_active(void){
	return rec_state != REC_OFF;
}

void record_switch_down(uint8_t sw, bool second){
	if(rec_state != REC_ON || !rec_pos_valid || sw >= MIDI_NUM_SWITCHES) return;
	if(rec_bank != sw_get_current_page()) return;
	uint8_t g = rec_last[sw];
	if(second && g != 0xFF && rec_open[sw] == 0xFF){
		// The second press of a double press: the same gesture, held anew
		rec[g].flags |= REC_DOUBLE | REC_OPEN;
	} else {
		if(rec_count >= REC_MAX){
			if(!rec_full_shown) display_show_message("REC FULL");
			rec_full_shown = true;
			return;
		}
		g = rec_count++;
		uint32_t beat = (rec_pos + CLOCKS_PER_BEAT / 2) / CLOCKS_PER_BEAT;
		rec[g].beat = (uint16_t)(beat > 0xFFFF ? 0xFFFF : beat);
		rec[g].flags = (uint8_t)(sw | REC_OPEN);
	}
	rec[g].hold = 1;
	rec_open[sw] = g;
	rec_last[sw] = g;
	rec_down_pos[sw] = rec_pos;
}

void record_switch_up(uint8_t sw, uint8_t hold){
	if(rec_state != REC_ON || sw >= MIDI_NUM_SWITCHES) return;
	uint8_t g = rec_open[sw];
	if(g == 0xFF) return;
	rec_open[sw] = 0xFF;
	uint32_t clocks = rec_pos - rec_down_pos[sw];
	if(clocks < 1) clocks = 1;
	if(clocks > 0xFFFF) clocks = 0xFFFF;
	rec[g].hold = (uint16_t)clocks;
	rec[g].flags = (uint8_t)((rec[g].flags & ~(REC_OPEN | (3U << REC_HOLD_SHIFT))) | (hold << REC_HOLD_SHIFT));
}

/* --------------------------------------------------------------- playback */

static void voice_release(uint8_t sw){
	if(voice[sw].phase == V_TAP || voice[sw].phase == V_HOLD) sw_play_switch(sw, false);
	voice[sw].phase = V_IDLE;
}

static void play_stop(void){
	for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++) voice_release(i);
	playing = false;
}

static void voice_start(uint8_t sw, const gesture_t *g, uint32_t pos, uint32_t now){
	voice_t *v = &voice[sw];
	v->kind = (uint8_t)((g->flags >> REC_HOLD_SHIFT) & 3U);
	v->hold = g->hold;
	v->pos0 = pos;
	v->t0 = now;
	v->phase = (g->flags & REC_DOUBLE) ? V_TAP : V_HOLD;
	sw_play_switch(sw, true);
}

static void voice_task(uint8_t sw, uint32_t pos, uint32_t now){
	voice_t *v = &voice[sw];
	uint32_t ms = now - v->t0;
	uint32_t threshold = sw_long_press_ms();
	switch(v->phase){
	case V_TAP:	// a double press: a quick tap first
		if(ms >= TAP_GAP_MS){
			sw_play_switch(sw, false);
			v->phase = V_GAP;
		}
		break;
	case V_GAP:
		if(ms >= 2U * TAP_GAP_MS){
			sw_play_switch(sw, true);
			v->phase = V_HOLD;
			v->pos0 = pos;
			v->t0 = now;
		}
		break;
	case V_HOLD: {
		bool up = (pos - v->pos0) >= v->hold;
		if(v->kind == REC_HOLD_LONG && ms < threshold + THRESHOLD_MARGIN_MS) up = false;
		if(v->kind == REC_HOLD_SHORT && ms + THRESHOLD_MARGIN_MS >= threshold) up = true;
		if(up){
			sw_play_switch(sw, false);
			v->phase = V_IDLE;
		}
		break;
	}
	default:
		break;
	}
}

static void play_seek(uint32_t pos){
	play_next = 0;
	if(play_entry == NULL) return;
	gesture_t g;
	while(play_next < play_entry[0]){
		read_gesture(play_entry, play_next, &g);
		// A beat just gone still counts: the run may have begun a clock ago
		if((uint32_t)g.beat * CLOCKS_PER_BEAT + 2U >= pos) break;
		play_next++;
	}
}

static void play_task(uint32_t pos, uint8_t bank, uint8_t slot){
	uint32_t now = HAL_GetTick();
	if(!playing || bank != play_bank || slot != play_slot || pos < play_last_pos || play_gen != store_gen){
		play_stop();
		playing = true;
		play_bank = bank;
		play_slot = slot;
		play_gen = store_gen;
		play_entry = find_recording(slot, bank);
		play_seek(pos);
	}
	play_last_pos = pos;
	for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++) voice_task(i, pos, now);
	if(play_entry == NULL) return;
	gesture_t g;
	while(play_next < play_entry[0]){
		read_gesture(play_entry, play_next, &g);
		if((uint32_t)g.beat * CLOCKS_PER_BEAT > pos) break;
		uint8_t sw = g.flags & 0x07U;
		if(voice[sw].phase != V_IDLE){
			voice_release(sw);	// still held from before: let go, press next pass
			break;
		}
		voice_start(sw, &g, pos, now);
		play_next++;
	}
}

void record_task(void){
	uint32_t pos;
	bool valid = tempo_song_clock(&pos);
	uint8_t bank = sw_get_current_page();
	uint8_t slot = flash_settings_active_slot();

	if(save_pending && quiet()) save(false);

	if(rec_state != REC_OFF && (bank != rec_bank || slot != rec_slot)){
		if(rec_state == REC_ON) finish();
		else rec_state = REC_OFF;
	}
	if(rec_state == REC_ARMED && valid){
		rec_pos = pos;
		begin();
	}
	if(rec_state == REC_ON && (!valid || pos < rec_pos)){
		finish();	// the clock stopped, or the host went back
	}
	rec_pos_valid = valid;
	if(valid) rec_pos = pos;

	// The editor has the switches: a press played back would edit
	bool here = play_on && valid && !editor_is_open() && !(rec_state != REC_OFF && rec_bank == bank);
	if(here) play_task(pos, bank, slot);
	else if(playing) play_stop();
}
