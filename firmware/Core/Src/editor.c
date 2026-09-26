/*
 * editor.c
 *
 * Editing on the pedal, without a computer. Bank Down and Bank Up held
 * together for two seconds open an editor on the configuration the pedal is
 * running: the ten commands of every button of every bank, for the short and
 * the long press, the four character labels, and the settings that are a
 * number or a choice. The same two switches held together leave it.
 *
 * The screen is a list of named fields with the cursor on one of them:
 *
 *   1 and 2   walk the list
 *   3 and 4   change the value under the cursor; held, they repeat and speed up
 *   A and B   step to the previous or next command of the list
 *   C         sends the command as it stands, so it can be heard
 *   D         swaps the commands for the settings
 *
 * What is changed is written back to flash as soon as the cursor leaves the
 * command, the label or the setting, so walking away loses nothing. A star in
 * the title says there is something not written yet. Writing means rewriting
 * the 2 kB flash page those bytes live in (flash_settings_patch), after which
 * everything the firmware derives from the configuration is built again.
 *
 * The double press lists are not offered: they live in an area the tools
 * write as a block, and a configuration flashed by an older tool has none.
 */

#include <stdio.h>
#include <string.h>

#include "main.h"
#include "editor.h"
#include "display.h"
#include "leds.h"
#include "midi_cmds.h"
#include "midi_defines.h"
#include "flash_midi_settings.h"
#include "switch_router.h"
#include "sleep.h"

#define ED_REPEAT_FIRST		(500)	// held before a +/- starts repeating
#define ED_REPEAT_SLOW		(160)	// and how fast it repeats, to start with
#define ED_REPEAT_FAST		(40)
#define ED_TRY_MS			(400)	// how long a note tried out is held

// The switches, in the order of the switch table
#define SW_1	(0)
#define SW_2	(1)
#define SW_3	(2)
#define SW_4	(3)
#define SW_A	(4)
#define SW_B	(5)
#define SW_C	(6)
#define SW_D	(7)

enum { LIST_SHORT, LIST_LONG, LIST_COUNT };
static const char *const list_names[LIST_COUNT] = {"Short", "Long"};

// The command types the editor writes. Anything else is shown by name and
// left alone until the type is changed, which replaces it.
enum { T_NONE, T_PC, T_CC, T_NOTE, T_BANK, T_TAP, T_START, T_STOP, T_PANIC, T_WAIT, T_COUNT };
#define T_OTHER		(T_COUNT)
static const char *const type_names[T_COUNT] = {
	"---", "PC", "CC", "Note", "Bank", "Tap", "Start", "Stop", "Panic", "Wait"};

static const char *const bank_actions[] = {
	"Go to", "Up by", "Down by", "Config", "Next cfg", "Page", "Back"};
#define BANK_ACTIONS	(7)
static const char *const tap_actions[] = {"Tap", "Clock", "Set BPM", "Up by", "Down by"};
#define TAP_ACTIONS		(5)
static const char sw_ids[MIDI_NUM_SWITCHES] = {'1', '2', '3', '4', 'A', 'B', 'C', 'D'};

// The fields that are there whatever the command is
enum { F_BANK, F_BUTTON, F_LIST, F_SLOT, F_TYPE, F_FIRST_OWN };

static struct {
	bool open;
	bool settings;			// the settings screen instead of the commands one
	uint8_t bank, sw, list, slot;
	uint8_t field;			// the line the cursor is on
	uint8_t top;			// the first line shown
	uint8_t cmd[MIDI_ROM_CMD_SIZE];
	uint8_t label[BUTTON_LABEL_LEN];
	bool cmd_dirty, label_dirty, set_dirty;
	uint8_t setting;		// the setting the cursor is on
	uint8_t set_value;		// being edited
	int8_t held;			// -1 or +1 while 3 or 4 is down
	uint32_t held_tick;
	uint16_t held_interval;
	uint8_t try_note[MIDI_ROM_CMD_SIZE];
	uint32_t try_until;		// when the note tried out is let go, 0 for none
} ed;

/* ------------------------------------------------------------------ steps */

static uint8_t step_clamp(uint8_t v, int8_t d, uint8_t lo, uint8_t hi){
	int32_t n = (int32_t)v + d;
	if(n < (int32_t)lo) n = lo;
	if(n > (int32_t)hi) n = hi;
	return (uint8_t)n;
}

static uint8_t step_wrap(uint8_t v, int8_t d, uint8_t lo, uint8_t hi){
	int32_t n = (int32_t)v + d;
	if(n < (int32_t)lo) n = hi;
	if(n > (int32_t)hi) n = lo;
	return (uint8_t)n;
}

static uint16_t step_clamp16(uint16_t v, int8_t d, uint16_t lo, uint16_t hi){
	int32_t n = (int32_t)v + d;
	if(n < (int32_t)lo) n = lo;
	if(n > (int32_t)hi) n = hi;
	return (uint16_t)n;
}

/* --------------------------------------------------------------- commands */

static uint8_t *cmd_ptr(void){
	uint32_t at = (uint32_t)MIDI_ROM_KEY_STRIDE * MIDI_NUM_SWITCHES * ed.bank
			+ (uint32_t)MIDI_ROM_KEY_STRIDE * ed.sw
			+ (uint32_t)MIDI_ROM_CMD_SIZE * ed.slot;
	return (ed.list == LIST_LONG ? pLongPressCmds : pSwitchCmds) + at;
}

static uint8_t *label_ptr(void){
	return pButtonLabels + ((uint32_t)ed.bank * MIDI_NUM_SWITCHES + ed.sw) * BUTTON_LABEL_LEN;
}

static uint8_t cmd_type(const uint8_t *c){
	switch(c[0] & 0xF0){
	case CMD_NO_CMD_NIBBLE:
		if((c[0] & 0x0F) == 0) return T_NONE;
		if((c[0] & 0x0F) == CMD_WAIT_MODE) return T_WAIT;
		return T_OTHER;
	case CMD_PC_NIBBLE:		return PC_IS_RELATIVE(c[2]) ? T_OTHER : T_PC;
	case CMD_CC_NIBBLE:		return T_CC;
	case CMD_NOTE_NIBBLE:	return T_NOTE;
	case CMD_BANK_NIBBLE:	return ((c[0] & 0x0F) < BANK_ACTIONS) ? T_BANK : T_OTHER;
	case CMD_TAP_NIBBLE:	return ((c[0] & 0x0F) < TAP_ACTIONS) ? T_TAP : T_OTHER;
	case CMD_START_NIBBLE:	return T_START;
	case CMD_STOP_NIBBLE:	return T_STOP;
	case CMD_PANIC_NIBBLE:	return T_PANIC;
	default:				return T_OTHER;
	}
}

// What a command the editor does not write is called, so it can be recognised
static const char *other_name(const uint8_t *c){
	if((c[0] & 0xF0) == CMD_NO_CMD_NIBBLE){
		switch(c[0] & 0x0F){
		case CMD_RAMP_MODE:		return "Ramp";
		case CMD_CYCLE_MODE:	return "Cycle";
		case CMD_LEAVE_MODE:	return "Leave";
		case CMD_EXP_MODE:		return "Exp";
		case CMD_LFO_MODE:		return "LFO";
		case CMD_MMC_MODE:		return "MMC";
		case CMD_SONG_MODE:		return "Song";
		case CMD_CHAN_MODE:		return "Chan";
		case CMD_SEQ_MODE:		return "Seq";
		case CMD_VAR_MODE:		return "Value";
		case CMD_IF_MODE:		return "If";
		case CMD_MACRO_MODE:	return "Macro";
		default:				return "?";
		}
	}
	switch(c[0] & 0xF0){
	case CMD_MEDIA_NIBBLE:	return "Media";
	case CMD_CCINC_NIBBLE:	return "CC step";
	case CMD_SYSEX_NIBBLE:	return "SysEx";
	case CMD_SCENE_NIBBLE:	return "Scene";
	case CMD_PB_NIBBLE:		return "Bend";
	case CMD_KEY_NIBBLE:	return "Key";
	case CMD_BANK_NIBBLE:	return "Bank";
	case CMD_TAP_NIBBLE:	return "Tap";
	case CMD_PC_NIBBLE:		return "PC step";
	default:				return "?";
	}
}

// How many fields of its own a command has, after the type
static uint8_t own_fields(const uint8_t *c){
	switch(cmd_type(c)){
	case T_PC:		return 2;	// channel, program
	case T_CC:		return 5;	// channel, CC, on, off, toggle
	case T_NOTE:	return 4;	// channel, note, velocity, toggle
	case T_WAIT:	return 1;	// the pause
	case T_BANK:
		switch(c[0] & 0x0F){
		case BANK_MODE_NEXT_CONFIG:
		case BANK_MODE_BACK:	return 1;	// the action alone
		default:				return 2;	// and what it acts on
		}
	case T_TAP:
		switch(c[0] & 0x0F){
		case TAP_MODE_TAP:
		case TAP_MODE_CLOCK:	return 1;
		case TAP_MODE_SET:		return 2;	// the tempo
		default:				return 3;	// the step and whether it repeats
		}
	default:		return 0;
	}
}

// A fresh command of a type, keeping the channel where both have one
static void set_type(uint8_t t){
	uint8_t old = cmd_type(ed.cmd);
	bool had_channel = (old == T_PC || old == T_CC || old == T_NOTE);
	uint8_t ch = had_channel ? (ed.cmd[0] & 0x0F) : 0;

	memset(ed.cmd, 0, MIDI_ROM_CMD_SIZE);
	switch(t){
	case T_PC:		ed.cmd[0] = CMD_PC_NIBBLE | ch; ed.cmd[2] = 0xFF; ed.cmd[3] = 0xFF; break;
	case T_CC:		ed.cmd[0] = CMD_CC_NIBBLE | ch; ed.cmd[2] = 127; break;
	case T_NOTE:	ed.cmd[0] = CMD_NOTE_NIBBLE | ch; ed.cmd[1] = 60; ed.cmd[2] = 100; break;
	case T_BANK:	ed.cmd[0] = CMD_BANK_NIBBLE; break;
	case T_TAP:		ed.cmd[0] = CMD_TAP_NIBBLE | TAP_MODE_TAP; break;
	case T_START:	ed.cmd[0] = CMD_START_NIBBLE; break;
	case T_STOP:	ed.cmd[0] = CMD_STOP_NIBBLE; break;
	case T_PANIC:	ed.cmd[0] = CMD_PANIC_NIBBLE; break;
	case T_WAIT:	ed.cmd[0] = CMD_NO_CMD_NIBBLE | CMD_WAIT_MODE; ed.cmd[2] = 10; break;
	default:		break;	// T_NONE: four zeroes
	}
}

static void toggle_set(bool on){
	if(on)	ed.cmd[1] |= 0x80;
	else	ed.cmd[1] &= 0x7F;
}

// One of a command's own fields: its name, and its value as text
static void own_field(uint8_t i, const char **name, char *value, uint8_t size){
	uint8_t *c = ed.cmd;
	*name = "";
	value[0] = 0;

	switch(cmd_type(c)){
	case T_PC:
		if(i == 0){ *name = "CHANNEL"; snprintf(value, size, "%u", (c[0] & 0x0F) + 1); }
		else      { *name = "PROGRAM"; snprintf(value, size, "%u", c[1] & 0x7F); }
		break;
	case T_CC:
		switch(i){
		case 0: *name = "CHANNEL"; snprintf(value, size, "%u", (c[0] & 0x0F) + 1); break;
		case 1: *name = "CC";      snprintf(value, size, "%u", c[1] & 0x7F); break;
		case 2: *name = "ON";      snprintf(value, size, "%u", c[2] & 0x7F); break;
		case 3: *name = "OFF";
			if(c[3] > 0x7F) snprintf(value, size, "none");
			else            snprintf(value, size, "%u", c[3]);
			break;
		default: *name = "TOGGLE"; snprintf(value, size, "%s", (c[1] & 0x80) ? "Yes" : "No"); break;
		}
		break;
	case T_NOTE:
		switch(i){
		case 0: *name = "CHANNEL";  snprintf(value, size, "%u", (c[0] & 0x0F) + 1); break;
		case 1: *name = "NOTE";     snprintf(value, size, "%u", c[1] & 0x7F); break;
		case 2: *name = "VELOCITY"; snprintf(value, size, "%u", c[2] & 0x7F); break;
		default: *name = "TOGGLE";  snprintf(value, size, "%s", (c[1] & 0x80) ? "Yes" : "No"); break;
		}
		break;
	case T_BANK:
		if(i == 0){ *name = "ACTION"; snprintf(value, size, "%s", bank_actions[c[0] & 0x0F]); }
		else {
			switch(c[0] & 0x0F){
			case BANK_MODE_CONFIG: *name = "CONFIG"; snprintf(value, size, "%u", c[1] + 1); break;
			case 1: case 2:        *name = "BANKS";  snprintf(value, size, "%u", c[1]); break;
			default:               *name = "BANK";   snprintf(value, size, "%u", c[1] + 1); break;
			}
		}
		break;
	case T_TAP:
		if(i == 0){ *name = "ACTION"; snprintf(value, size, "%s", tap_actions[c[0] & 0x0F]); }
		else if((c[0] & 0x0F) == TAP_MODE_SET){
			*name = "BPM";
			snprintf(value, size, "%u", (unsigned)((c[2] & 0x7F) | (c[3] << 7)));
		} else if(i == 1){
			*name = "BPM STEP"; snprintf(value, size, "%u", c[2] & 0x7F);
		} else {
			*name = "REPEAT"; snprintf(value, size, "%s", (c[2] & TAP_REPEAT_BIT) ? "Yes" : "No");
		}
		break;
	case T_WAIT:
		*name = "PAUSE";
		snprintf(value, size, "%u ms", (unsigned)c[2] * 10);
		break;
	default:
		break;
	}
}

static void own_field_step(uint8_t i, int8_t d){
	uint8_t *c = ed.cmd;

	switch(cmd_type(c)){
	case T_PC:
		if(i == 0) c[0] = (uint8_t)(CMD_PC_NIBBLE | step_wrap(c[0] & 0x0F, d, 0, 15));
		else       c[1] = (uint8_t)((c[1] & 0x80) | step_clamp(c[1] & 0x7F, d, 0, 127));
		break;
	case T_CC:
		switch(i){
		case 0: c[0] = (uint8_t)(CMD_CC_NIBBLE | step_wrap(c[0] & 0x0F, d, 0, 15)); break;
		case 1: c[1] = (uint8_t)((c[1] & 0x80) | step_clamp(c[1] & 0x7F, d, 0, 127)); break;
		case 2: c[2] = step_clamp(c[2] & 0x7F, d, 0, 127); break;
		case 3: {	// 0-127, and one past the end is "send nothing"
			uint8_t v = (c[3] > 0x7F) ? 128 : c[3];
			v = step_clamp(v, d, 0, 128);
			c[3] = (v == 128) ? 0x80 : v;
			break;
		}
		default: toggle_set(!(c[1] & 0x80)); break;
		}
		break;
	case T_NOTE:
		switch(i){
		case 0: c[0] = (uint8_t)(CMD_NOTE_NIBBLE | step_wrap(c[0] & 0x0F, d, 0, 15)); break;
		case 1: c[1] = (uint8_t)((c[1] & 0x80) | step_clamp(c[1] & 0x7F, d, 0, 127)); break;
		case 2: c[2] = step_clamp(c[2] & 0x7F, d, 0, 127); break;
		default: toggle_set(!(c[1] & 0x80)); break;
		}
		break;
	case T_BANK:
		if(i == 0){
			c[0] = (uint8_t)(CMD_BANK_NIBBLE | step_wrap(c[0] & 0x0F, d, 0, BANK_ACTIONS - 1));
			c[1] = 0;
		} else {
			switch(c[0] & 0x0F){
			case BANK_MODE_CONFIG: c[1] = step_wrap(c[1], d, 0, CONFIG_SLOTS - 1); break;
			case 1: case 2:        c[1] = step_clamp(c[1], d, 1, MIDI_NUM_BANKS - 1); break;
			default:               c[1] = step_clamp(c[1], d, 0, MIDI_NUM_BANKS - 1); break;
			}
		}
		break;
	case T_TAP:
		if(i == 0){
			c[0] = (uint8_t)(CMD_TAP_NIBBLE | step_wrap(c[0] & 0x0F, d, 0, TAP_ACTIONS - 1));
			c[2] = 0; c[3] = 0;
			if((c[0] & 0x0F) == TAP_MODE_SET){ c[2] = 120 & 0x7F; c[3] = 120 >> 7; }
			if((c[0] & 0x0F) == TAP_MODE_UP || (c[0] & 0x0F) == TAP_MODE_DOWN) c[2] = 1;
		} else if((c[0] & 0x0F) == TAP_MODE_SET){
			uint16_t bpm = (uint16_t)((c[2] & 0x7F) | (c[3] << 7));
			bpm = step_clamp16(bpm, d, 20, 300);
			c[2] = (uint8_t)(bpm & 0x7F);
			c[3] = (uint8_t)(bpm >> 7);
		} else if(i == 1){
			c[2] = (uint8_t)((c[2] & TAP_REPEAT_BIT) | step_clamp(c[2] & 0x7F, d, 1, 20));
		} else {
			c[2] ^= TAP_REPEAT_BIT;
		}
		break;
	case T_WAIT:
		c[2] = step_clamp(c[2], d, 1, 255);
		break;
	default:
		break;
	}
}

/* --------------------------------------------------------------- settings */

enum { S_NUM, S_ONOFF, S_CHOICE, S_MS, S_PCT, S_MIN, S_CHAN, S_SEC };

typedef struct {
	const char *name;
	uint8_t byte;			// where it lives in the global settings
	uint8_t kind;
	uint8_t lo, hi;
	uint8_t def;			// what an unset byte means
	bool zero_def;			// and whether a zero means it too
	const char *const *choices;
} setting_t;

static const char *const bank_switch_names[] = {"Bank", "Bank+MIDI", "MIDI only"};

static const setting_t settings[] = {
	{"LONGPRES", GLOBAL_SETTINGS_LONG_PRESS,          S_MS,     5,   200, 50,  true,  NULL},
	{"DBLPRESS", GLOBAL_SETTINGS_DOUBLE_PRESS,        S_MS,     5,   200, 30,  true,  NULL},
	{"COMBO",    GLOBAL_SETTINGS_COMBO,               S_MS,     2,    25, 8,   true,  NULL},
	{"BRIGHT",   GLOBAL_SETTINGS_LED_BRIGHTNESS,      S_PCT,    1,   100, 100, false, NULL},
	{"RESTBRIG", GLOBAL_SETTINGS_LED_REST_BRIGHTNESS, S_PCT,    0,   100, 100, false, NULL},
	{"BANKJUMP", GLOBAL_SETTINGS_BANK_JUMP_STEP,      S_NUM,    1,    31, 8,   true,  NULL},
	{"SLEEP",    GLOBAL_SETTINGS_SLEEP_AFTER_MIN,     S_MIN,    0,    60, 0,   false, NULL},
	{"GLOBCHAN", GLOBAL_SETTINGS_GLOBAL_CHANNEL,      S_CHAN,   0,    16, 0,   false, NULL},
	{"GLOBBANK", GLOBAL_SETTINGS_GLOBAL_BANK,         S_NUM,    0,    32, 0,   false, NULL},
	{"BANK SW",  GLOBAL_SETTINGS_BANK_SWITCH_MODE,    S_CHOICE, 0,     2, 0,   false, bank_switch_names},
	{"PREVIEW",  GLOBAL_SETTINGS_BANK_PREVIEW,        S_SEC,    0,    60, 0,   false, NULL},
	{"SETLIST",  GLOBAL_SETTINGS_SETLIST_MODE,        S_ONOFF,  0,     1, 0,   false, NULL},
	{"REMEMBER", GLOBAL_SETTINGS_REMEMBER_STATE,      S_ONOFF,  0,     1, 0,   false, NULL},
	{"CLOCKFLW", GLOBAL_SETTINGS_CLOCK_FOLLOW,        S_ONOFF,  0,     1, 0,   false, NULL},
	{"LEDFEEDB", GLOBAL_SETTINGS_LED_FEEDBACK,        S_ONOFF,  0,     1, 0,   false, NULL},
	{"USB THRU", GLOBAL_SETTINGS_USB_THRU,            S_ONOFF,  0,     1, 0,   false, NULL},
	{"RT THRU",  GLOBAL_SETTINGS_REALTIME_PASS,       S_ONOFF,  0,     1, 0,   false, NULL},
	{"KEMPER",   GLOBAL_SETTINGS_KEMPER_MODE,         S_ONOFF,  0,     1, 0,   false, NULL},
	{"EXP1 CC",  GLOBAL_SETTINGS_EXP1_CC,             S_NUM,    0,   127, 0,   false, NULL},
	{"EXP2 CC",  GLOBAL_SETTINGS_EXP2_CC,             S_NUM,    0,   127, 0,   false, NULL},
};
#define SETTING_COUNT	((uint8_t)(sizeof(settings)/sizeof(settings[0])))

// What a stored byte really means, an unset one standing for its default
static uint8_t setting_value(const setting_t *s){
	uint8_t v = pGlobalSettings[s->byte];
	if(v == 0xFF) return s->def;
	if(v == 0 && s->zero_def) return s->def;
	if(v < s->lo) return s->lo;
	if(v > s->hi) return s->hi;
	return v;
}

static void setting_text(const setting_t *s, uint8_t v, char *out, uint8_t size){
	switch(s->kind){
	case S_MS:     snprintf(out, size, "%u ms", (unsigned)v * 10); break;
	case S_PCT:    snprintf(out, size, "%u %%", v); break;
	case S_MIN:    if(v == 0) snprintf(out, size, "never");
	               else snprintf(out, size, "%u min", v); break;
	case S_SEC:    if(v == 0) snprintf(out, size, "off");
	               else snprintf(out, size, "%u s", v); break;
	case S_CHAN:   if(v == 0) snprintf(out, size, "off");
	               else snprintf(out, size, "%u", v); break;
	case S_ONOFF:  snprintf(out, size, "%s", v ? "Yes" : "No"); break;
	case S_CHOICE: snprintf(out, size, "%s", s->choices[v <= s->hi ? v : 0]); break;
	default:       snprintf(out, size, "%u", v); break;
	}
}

/* ------------------------------------------------------------------ saving */

static void save(void){
	bool wrote = false;

	if(ed.cmd_dirty){
		wrote |= flash_settings_patch(cmd_ptr(), ed.cmd, MIDI_ROM_CMD_SIZE);
		ed.cmd_dirty = false;
	}
	if(ed.label_dirty){
		wrote |= flash_settings_patch(label_ptr(), ed.label, BUTTON_LABEL_LEN);
		ed.label_dirty = false;
	}
	if(ed.set_dirty){
		wrote |= flash_settings_patch(&pGlobalSettings[settings[ed.setting].byte], &ed.set_value, 1);
		ed.set_dirty = false;
	}

	if(wrote){
		// Everything the firmware works out from the configuration, again
		leds_init();
		sw_led_init();
		set_all_leds(1);	// the editor lights them all while it is open
	}
}

static void load_cmd(void){
	memcpy(ed.cmd, cmd_ptr(), MIDI_ROM_CMD_SIZE);
	ed.cmd_dirty = false;
}

static void load_label(void){
	const uint8_t *l = label_ptr();
	for(uint8_t i=0; i<BUTTON_LABEL_LEN; i++){
		char c = (char)l[i];
		ed.label[i] = (uint8_t)((c < 0x20 || c > 0x7E) ? ' ' : c);
	}
	ed.label_dirty = false;
}

static void load_setting(void){
	ed.set_value = setting_value(&settings[ed.setting]);
	ed.set_dirty = false;
}

/* ------------------------------------------------------------------ fields */

static uint8_t field_count(void){
	if(ed.settings) return SETTING_COUNT;
	return (uint8_t)(F_FIRST_OWN + own_fields(ed.cmd) + BUTTON_LABEL_LEN);
}

// The line for a field: its name, then its value from column 9
static void field_line(uint8_t f, char *out, uint8_t size){
	char value[12];
	const char *name = "";
	value[0] = 0;

	if(ed.settings){
		const setting_t *s = &settings[f];
		name = s->name;
		setting_text(s, (f == ed.setting) ? ed.set_value : setting_value(s), value, sizeof(value));
	} else if(f == F_BANK){
		name = "BANK";   snprintf(value, sizeof(value), "%u", ed.bank + 1);
	} else if(f == F_BUTTON){
		name = "BUTTON"; snprintf(value, sizeof(value), "%c", sw_ids[ed.sw]);
	} else if(f == F_LIST){
		name = "PRESS";  snprintf(value, sizeof(value), "%s", list_names[ed.list]);
	} else if(f == F_SLOT){
		name = "COMMAND"; snprintf(value, sizeof(value), "%u", ed.slot + 1);
	} else if(f == F_TYPE){
		name = "TYPE";
		uint8_t t = cmd_type(ed.cmd);
		snprintf(value, sizeof(value), "%s", (t == T_OTHER) ? other_name(ed.cmd) : type_names[t]);
	} else if(f < F_FIRST_OWN + own_fields(ed.cmd)){
		own_field((uint8_t)(f - F_FIRST_OWN), &name, value, sizeof(value));
	} else {
		static char label_name[] = "NAME n";
		uint8_t i = (uint8_t)(f - F_FIRST_OWN - own_fields(ed.cmd));
		label_name[5] = (char)('1' + i);
		name = label_name;
		snprintf(value, sizeof(value), "%c", (char)ed.label[i]);
	}

	snprintf(out, size, "%-8s %s", name, value);
}

static void field_step(uint8_t f, int8_t d){
	if(ed.settings){
		const setting_t *s = &settings[ed.setting];
		if(s->kind == S_ONOFF)			ed.set_value = ed.set_value ? 0 : 1;
		else if(s->kind == S_CHOICE)	ed.set_value = step_wrap(ed.set_value, d, s->lo, s->hi);
		else							ed.set_value = step_clamp(ed.set_value, d, s->lo, s->hi);
		ed.set_dirty = true;
		return;
	}

	switch(f){
	case F_BANK:
		save();
		ed.bank = step_wrap(ed.bank, d, 0, MIDI_NUM_BANKS - 1);
		load_cmd(); load_label();
		break;
	case F_BUTTON:
		save();
		ed.sw = step_wrap(ed.sw, d, 0, MIDI_NUM_SWITCHES - 1);
		load_cmd(); load_label();
		break;
	case F_LIST:
		save();
		ed.list = step_wrap(ed.list, d, 0, LIST_COUNT - 1);
		load_cmd();
		break;
	case F_SLOT:
		save();
		ed.slot = step_wrap(ed.slot, d, 0, MIDI_NUM_COMMANDS_PER_SWITCH - 1);
		load_cmd();
		break;
	case F_TYPE: {
		uint8_t t = cmd_type(ed.cmd);
		if(t == T_OTHER)	t = (d > 0) ? T_NONE : (uint8_t)(T_COUNT - 1);
		else				t = step_wrap(t, d, 0, T_COUNT - 1);
		set_type(t);
		ed.cmd_dirty = true;
		break;
	}
	default:
		if(f < F_FIRST_OWN + own_fields(ed.cmd)){
			own_field_step((uint8_t)(f - F_FIRST_OWN), d);
			ed.cmd_dirty = true;
		} else {
			uint8_t i = (uint8_t)(f - F_FIRST_OWN - own_fields(ed.cmd));
			ed.label[i] = step_wrap(ed.label[i], d, 0x20, 0x7E);
			ed.label_dirty = true;
		}
		break;
	}
}

/* ------------------------------------------------------------------ screen */

static void redraw(void){
	char lines[DISPLAY_EDIT_ROWS][DISPLAY_EDIT_COLS + 1];
	char title[DISPLAY_EDIT_COLS + 1];
	uint8_t count = field_count();

	if(ed.field >= count) ed.field = (uint8_t)(count - 1);
	if(ed.field < ed.top) ed.top = ed.field;
	if(ed.field >= ed.top + DISPLAY_EDIT_ROWS) ed.top = (uint8_t)(ed.field - DISPLAY_EDIT_ROWS + 1);
	if(count > DISPLAY_EDIT_ROWS && ed.top > count - DISPLAY_EDIT_ROWS){
		ed.top = (uint8_t)(count - DISPLAY_EDIT_ROWS);
	}

	uint8_t shown = (uint8_t)((count - ed.top > DISPLAY_EDIT_ROWS) ? DISPLAY_EDIT_ROWS : count - ed.top);
	for(uint8_t i=0; i<shown; i++){
		field_line((uint8_t)(ed.top + i), lines[i], sizeof(lines[i]));
	}

	bool dirty = ed.cmd_dirty || ed.label_dirty || ed.set_dirty;
	snprintf(title, sizeof(title), "EDIT %-8s %s",
			ed.settings ? "SETTINGS" : "COMMANDS", dirty ? "*" : " ");

	display_editor(title, (const char (*)[DISPLAY_EDIT_COLS + 1])lines, shown,
			(uint8_t)(ed.field - ed.top));
}

/* ------------------------------------------------------------- trying out */

static void try_cmd(void){
	if(ed.settings) return;
	switch(cmd_type(ed.cmd)){
	case T_PC:
		midiCmd_send_pc_command_from_rom(ed.cmd);
		break;
	case T_CC:
		midiCmd_send_cc_command_from_rom(ed.cmd, MIDI_CONTROL_ON);
		break;
	case T_NOTE:
		midiCmd_send_note_command_from_rom(ed.cmd, 1);
		memcpy(ed.try_note, ed.cmd, MIDI_ROM_CMD_SIZE);
		ed.try_until = HAL_GetTick() + ED_TRY_MS;
		break;
	case T_START:	midiCmd_send_start_command(); break;
	case T_STOP:	midiCmd_send_stop_command(); break;
	case T_PANIC:	midiCmd_send_panic(); break;
	default:		break;	// the rest do something to the pedal, not a sound
	}
}

/* ------------------------------------------------------------------ public */

bool editor_is_open(void){
	return ed.open;
}

void editor_open(void){
	if(ed.open) return;
	memset(&ed, 0, sizeof(ed));
	ed.open = true;
	ed.bank = sw_get_home_bank();
	load_cmd();
	load_label();
	set_all_leds(1);
	redraw();
}

void editor_close(void){
	if(!ed.open) return;
	save();
	ed.open = false;
	ed.try_until = 0;
	display_editor_end();
	update_leds_on_bank_change();
}

void editor_press(uint8_t sw, bool down){
	if(!ed.open) return;

	if(!down){
		if(sw == SW_3 || sw == SW_4) ed.held = 0;
		return;
	}

	switch(sw){
	case SW_1:
		ed.field = step_wrap(ed.field, -1, 0, (uint8_t)(field_count() - 1));
		if(ed.settings){ save(); ed.setting = ed.field; load_setting(); }
		break;
	case SW_2:
		ed.field = step_wrap(ed.field, +1, 0, (uint8_t)(field_count() - 1));
		if(ed.settings){ save(); ed.setting = ed.field; load_setting(); }
		break;
	case SW_3:
	case SW_4:
		ed.held = (sw == SW_3) ? -1 : +1;
		ed.held_tick = HAL_GetTick() + ED_REPEAT_FIRST;
		ed.held_interval = ED_REPEAT_SLOW;
		field_step(ed.field, ed.held);
		break;
	case SW_A:
	case SW_B:
		if(!ed.settings){
			save();
			ed.slot = step_wrap(ed.slot, (sw == SW_A) ? -1 : +1, 0,
					MIDI_NUM_COMMANDS_PER_SWITCH - 1);
			load_cmd();
		}
		break;
	case SW_C:
		try_cmd();
		break;
	case SW_VIRTUAL_BANK_DOWN:
	case SW_VIRTUAL_BANK_UP:
		if(!ed.settings){
			save();
			ed.bank = step_wrap(ed.bank, (sw == SW_VIRTUAL_BANK_DOWN) ? -1 : +1,
					0, MIDI_NUM_BANKS - 1);
			load_cmd(); load_label();
		}
		break;
	case SW_D:
		save();
		ed.settings = !ed.settings;
		ed.field = 0;
		ed.top = 0;
		if(ed.settings){ ed.setting = 0; load_setting(); }
		else { load_cmd(); load_label(); }
		break;
	default:
		break;
	}

	redraw();
}

void editor_task(void){
	if(!ed.open) return;
	uint32_t now = HAL_GetTick();

	sleep_note_activity();	// the screen is the editor: it must not go out

	if(ed.try_until && (int32_t)(now - ed.try_until) >= 0){
		ed.try_until = 0;
		midiCmd_send_note_command_from_rom(ed.try_note, 0);
	}

	if(ed.held && (int32_t)(now - ed.held_tick) >= 0){
		field_step(ed.field, ed.held);
		if(ed.held_interval > ED_REPEAT_FAST) ed.held_interval -= 10;
		ed.held_tick = now + ed.held_interval;
		redraw();
	}
}
