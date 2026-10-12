/*
 * display.c
 *
 *  Created on: 8 Jul 2021
 *      Author: D Harvie
 *
 * Screen layout (128x64):
 *
 *   y  0..17  bank name: 4 chars in 11x18, then the 8 char info in 7x10
 *   y 23..36  labels of buttons 1 2 3 4   (top row of the pedal)
 *   y 45..58  labels of buttons A B C D   (bottom row of the pedal)
 *
 * Each label cell is 32 px wide and holds up to 4 chars in 7x10. Cells of
 * toggle buttons are drawn inverted while the toggle is on.
 *
 * With Bank_Switch_Mode at MIDI only the pedal is ten switches, and once Bank
 * Down or Bank Up has a label the grid is five cells to a row, as the switches
 * are laid out: 1 2 3 4 and Bank Up on top, A B C D and Bank Down below. A
 * cell is then 25 px wide and its 4 chars are in 6x8.
 *
 * The host can put its own text in the top line over SysEx (the patch or song
 * name): in place of the bank name, of the info line, or across the whole line.
 * A text wider than its place scrolls across it once, when it arrives or the
 * bank is entered, and then shows its beginning.
 *
 * At power on the configuration can have a banner instead: the pedal's own
 * text (banner_store.c) or the configuration's name, then the firmware
 * version, cross the screen in large letters, once. Any switch ends it, and
 * the bank screen waits for it underneath.
 *
 * A label, the bank's name or its info line can hold live values (1.20), $V
 * for a button's value, $N for a preset's name, and so on, see expand(). The
 * screen is drawn again whenever one of those it shows changes.
 *
 * In the gig view (1.32) the screen holds the song's name and its info line
 * only, the name twice the size of the large font when it fits:
 *
 *   y  2..37  the bank name, or the host's text for it or for the whole line
 *   y 44..61  the info line in 11x18
 *
 * A press of one of the eight buttons shows the labels for GIG_LABELS_MS.
 *
 * With Kemper_Mode on, the amp's tuner takes the whole screen while it is up:
 * the note twice the size of the large font, and a scale under it with a
 * needle, which is drawn solid and with the note boxed in once it is in tune.
 */
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "switch_router.h"
#include "display.h"
#include "banner_store.h"
#include <string.h>
#include <stdio.h>
#include "ssd1306.h"
#include "tempo.h"
#include "sleep.h"
#include "midi_cmds.h"

#define CELL_W		(32)
#define CELL_H		(14)
#define ROW_TOP_Y	(23)
#define ROW_BOT_Y	(45)
#define LABEL_FONT	Font_7x10
#define LABEL_CHAR_W	(7)
#define SCREEN_SHOWN_W	(128)	// the buffer is 130 wide, the glass shows 128
#define NAME_W		(44)	// 4 large chars
#define INFO_X		(50)
#define PEDAL_BAR_X	(60)	// an expression pedal's bar, after its number
#define CELL10_W	(25)	// five cells to a row
#define CELL10_X	(1)	// the 125 px they take, in the middle
#define LABEL10_FONT	Font_6x8
#define LABEL10_CHAR_W	(6)

static volatile uint8_t refresh_pending = 0;

// The gig view, and until when a press has the labels back (0: not)
#define GIG_LABELS_MS	(3000)
#define GIG_NAME_Y	(2)
#define GIG_NAME_SCALE	(2)
#define GIG_INFO_Y	(44)
static uint8_t gig_on = 0;
static uint32_t gig_labels_until = 0;
static uint8_t current_bank = 0;

// A transient overlay (the tempo readout) shown instead of the bank info
#define OVERLAY_MS	(1500)
#define SAFE_MODE_MS	(3000)
static uint8_t editor_on = 0;	// the on-pedal editor owns the screen
static uint8_t preview_bank = 0xFF;	// a bank shown before it is confirmed
static uint32_t overlay_until = 0;
// The readout shown over the info line until overlay_until; empty while a
// notice that is not over the bank screen has it
static char overlay_msg[13];
// An expression pedal's value as a bar after overlay_msg, 0xFF for none
static uint8_t overlay_bar = 0xFF;
// A pedal's value waiting for the screen to be free (1.29): pedal + 1, 0 none
static uint8_t pedal_pending = 0;
static uint8_t pedal_value;
static bool pedal_bar;
static uint32_t pedal_tick;

/*
 * Host text, one per place; an empty string means the bank's own text. Written
 * from the USB interrupt, drawn from the main loop: a torn string is redrawn
 * right away, since every write asks for a refresh.
 */
static char host_text[DISPLAY_TEXT_PLACES][DISPLAY_TEXT_MAX + 1];
static uint8_t host_keep[DISPLAY_TEXT_PLACES];
// A text shown for a moment only, waiting for the main loop to draw it
static char moment_text[DISPLAY_TEXT_MAX + 1];
static uint8_t moment_place = 0;
static volatile uint8_t moment_pending = 0;
static uint8_t moment_showing = 0;

/*
 * Following the clock (Beat_Counter): bar.beat and the tempo in place of the
 * bank's info while a clock runs, and a count-in's beats left in place of its
 * name. They stand in for the bank's own texts only, never for a host's.
 */
static char beat_text[12];
static char count_text[6];	// "IN 3", room for the compiler's worst case

// The place in the setlist and the next song, "3/12>INTR" (Setlist_Display)
static char setlist_text[14];

/*
 * Scrolling a text too wide for its place: still for a moment at the start,
 * then moved along until its end shows, still again, and back to the start
 * for good. Every long text on the line moves by the same scroll_px, each
 * stopping at its own end; scroll_need is the most any of them has to move,
 * worked out as the line is drawn.
 */
#define SCROLL_HOLD_MS	(800)
#define SCROLL_STEP_MS	(50)	// about what a whole screen takes to go out
#define SCROLL_STEP_PX	(2)
enum { SCROLL_IDLE, SCROLL_HOLD_START, SCROLL_MOVING, SCROLL_HOLD_END };
static uint8_t scroll_state = SCROLL_IDLE;
// Asked for from the USB interrupt too, so apart from what the main loop moves
static volatile uint8_t scroll_fresh = 0;
static uint16_t scroll_px = 0;
static uint16_t scroll_need = 0;
static uint32_t scroll_next = 0;
static void scroll_restart(void);
static void draw_big_char(uint8_t x, uint8_t y, char ch, uint8_t scale, SSD1306_COLOR color);

/*
 * The power on banner, drawn on the rows BANNER_Y..+18: only the pages that
 * hold them go out, so a step takes half a whole screen's time. It moves
 * banner_speed pixels a step, 1 to 3.
 */
#define BANNER_Y	(23)
#define BANNER_FIRST_PAGE	(BANNER_Y / 8)
#define BANNER_LAST_PAGE	((BANNER_Y + 18 - 1) / 8)
#define BANNER_STEP_MS	(25)
#define BANNER_MAX	(BANNER_TEXT_MAX + 4 + sizeof(FIRMWARE_VERSION))
static uint8_t banner_on = 0;
static volatile uint8_t banner_skip = 0;	// set by the switch scan
static char banner_text[BANNER_MAX];
static uint8_t banner_speed = 0;
static uint16_t banner_pos = 0;
static uint32_t banner_next = 0;

// The large font has capitals only; the banner's "v" of the version is its
// own lowercase one, marked in the text by BANNER_V
#define BANNER_V	('\x01')
static const uint16_t banner_v[18] = {
	0, 0, 0, 0, 0, 0x60C0, 0x3180, 0x3180, 0x3180, 0x1B00, 0x1B00, 0x1B00, 0x0E00, 0x0E00, 0x0600, 0, 0, 0};

/*
 * The tuner. Written from the USB interrupt as the amp reports, drawn from the
 * main loop as often as the screen can go out.
 */
#define TUNER_NOTE_SCALE	(2)
#define TUNER_NOTE_Y		(2)
#define TUNER_SCALE_Y		(46)	// the scale's line; the needle stands on it
#define TUNER_HALF_W		(60)	// either side of the middle
#define TUNER_FULL		(3400)	// a deviance this far off reaches the end
#define TUNER_IN_TUNE		(350)	// and this close is in tune
#define TUNER_CENTRE		(8192)
#define TUNER_NO_NOTE		(0xFF)
static volatile uint8_t tuner_on = 0;
static volatile uint8_t tuner_dirty = 0;
static volatile uint8_t tuner_note = TUNER_NO_NOTE;
static volatile uint16_t tuner_deviance = TUNER_CENTRE;
static const char *const note_names[12] = {
	"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"
};

void display_init(void){
    ssd1306_Init();

    ssd1306_SetCursor(5, 22);
    ssd1306_WriteString(FIRMWARE_VERSION, Font_7x10, White);

    // A little animation
    for(int i=0; i < 11; i++){
    	ssd1306_SetCursor(i*11,0);
		ssd1306_WriteString("#", Font_11x18, White);
		ssd1306_SetCursor(i*11,46);
		ssd1306_WriteString("#", Font_11x18, White);

		ssd1306_UpdateScreen();
		HAL_Delay(50);
    }

    __NOP();
}

/*
 * Start the banner if the configuration asks for one: the pedal's own text or
 * the configuration's name, without trailing spaces, then the version. It clears what the boot drew.
 */
static uint8_t banner_start(void){
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_BANNER];
	uint8_t speed = (v == 0xFF) ? 0 : (v & BANNER_SPEED_MASK);
	if(speed == 0) return 0;

	// The pedal's own text when it has one, otherwise the configuration's name
	const char *own = 0;
	uint8_t len = banner_store_get(&own);
	if(len){
		memcpy(banner_text, own, len);
	}else{
		for(uint8_t i=0; i<16; i++){
			char ch = (char)pGlobalSettings[16+i];
			banner_text[len++] = (ch < 32 || ch > 126) ? ' ' : ch;
		}
	}
	while(len && banner_text[len-1] == ' ') len--;
	if(len){
		memcpy(banner_text + len, "   ", 3);
		len += 3;
	}
	banner_text[len++] = BANNER_V;
	strcpy(banner_text + len, FIRMWARE_VERSION);

	banner_speed = speed;
	banner_pos = 0;
	banner_skip = 0;
	banner_next = HAL_GetTick();
	banner_on = 1;
	ssd1306_Fill(Black);
	ssd1306_UpdateScreen();
	return 1;
}

void display_setConfigName(void){
	display_gig_from_settings();
	if(banner_start()) return;
    ssd1306_SetCursor(10, 34);
    for(int i=0; i<16; i++){
    	ssd1306_WriteChar(pGlobalSettings[16+i], Font_7x10, White);
    }
    ssd1306_UpdateScreen();
}

static void fill_rect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, SSD1306_COLOR color){
	ssd1306_FillRect(x, y, w, h, color);
}

// Over for good: the bank screen comes back, its long texts scrolling
static void banner_end(void){
	banner_on = 0;
	scroll_restart();
	refresh_pending = 1;
}

void display_skip_banner(void){
	banner_skip = 1;
}

// Still up? A switch pressed since the last look ends it here
static uint8_t banner_running(void){
	if(banner_on && banner_skip) banner_end();
	return banner_on;
}

/*
 * One step of the banner when it is due: the text comes in on the right and
 * goes out on the left, then the banner ends.
 */
void display_banner_task(void){
	if(!banner_running() || ssd1306_Busy()) return;
	if((int32_t)(HAL_GetTick() - banner_next) < 0) return;
	banner_next = HAL_GetTick() + BANNER_STEP_MS;

	uint16_t width = (uint16_t)strlen(banner_text) * Font_11x18.FontWidth;
	if(banner_pos > SCREEN_SHOWN_W + width){
		banner_end();
		return;
	}
	fill_rect(0, BANNER_Y, SSD1306_WIDTH, Font_11x18.FontHeight, Black);
	// The text's first column is at SCREEN_SHOWN_W - banner_pos; a character
	// is unpacked once, as its columns come one after the other
	const uint16_t *rows = NULL;
	int32_t unpacked = -1;
	for(uint16_t col=0; col<SCREEN_SHOWN_W; col++){
		int32_t px = (int32_t)col + banner_pos - SCREEN_SHOWN_W;
		if(px < 0 || px >= width) continue;
		int32_t at = px / Font_11x18.FontWidth;
		uint8_t j = px % Font_11x18.FontWidth;
		if(at != unpacked){
			char ch = banner_text[at];
			rows = (ch == BANNER_V) ? banner_v : ssd1306_Glyph(ch, Font_11x18);
			unpacked = at;
		}
		for(uint8_t i=0; i<Font_11x18.FontHeight; i++){
			if((uint16_t)(rows[i] << j) & 0x8000) ssd1306_DrawPixel(col, BANNER_Y + i, White);
		}
	}
	ssd1306_UpdateLines(BANNER_FIRST_PAGE, BANNER_LAST_PAGE);
	banner_pos += banner_speed;
}

// Copy the stored label of a button into buf (up to 4 chars, NUL terminated),
// dropping anything not printable. Erased flash (0xFF) yields an empty label,
// and the reset bit (LABEL_RESET_BIT) is no part of the character.
static void label_text(const uint8_t *src, char buf[BUTTON_LABEL_LEN + 1]){
	int n = 0;
	for(int i=0; i<BUTTON_LABEL_LEN; i++){
		char c = (src[i] == 0xFF) ? ' ' : (char)(src[i] & 0x7F);
		if(c < 0x20 || c > 0x7E) c = ' ';
		buf[n++] = c;
	}
	while(n > 0 && buf[n-1] == ' ') n--; // trim trailing spaces
	buf[n] = 0;
}

static void get_label(uint8_t bank, uint8_t sw, char buf[BUTTON_LABEL_LEN + 1]){
	label_text(sw_button_label(bank, sw), buf);
}

// Bank Down and Bank Up's labels when the screen shows ten cells, else NULL
static const uint8_t *ten_cell_labels(void){
	if(pGlobalSettings[GLOBAL_SETTINGS_BANK_SWITCH_MODE] != BANK_SWITCH_MIDI_ONLY) return NULL;
	const uint8_t *labels = flash_settings_bank_switch_labels();
	if(labels == NULL) return NULL;
	for(uint8_t i=0; i<2 * BUTTON_LABEL_LEN; i++){
		if(labels[i] != 0xFF && labels[i] != ' ') return labels;
	}
	return NULL;
}

// One cell of the grid: column col of the top or bottom row
static void draw_label_cell(uint8_t col, bool top, bool ten, const char *label, bool active){
	// A live value one character longer than a label fits in the small letters
	bool small = ten || strlen(label) > BUTTON_LABEL_LEN;
	uint8_t w = ten ? CELL10_W : CELL_W;
	uint8_t x = ten ? (uint8_t)(CELL10_X + col * CELL10_W) : (uint8_t)(col * CELL_W);
	uint8_t y = top ? ROW_TOP_Y : ROW_BOT_Y;
	SSD1306_COLOR bg = active ? White : Black;
	SSD1306_COLOR fg = active ? Black : White;

	fill_rect(x, y, w, CELL_H, bg);

	uint8_t text_w = (uint8_t)(strlen(label) * (small ? LABEL10_CHAR_W : LABEL_CHAR_W));
	// The narrow cells leave a pixel or two between labels: centred on the
	// letters alone, not the blank column after the last, they get one more
	if(small && text_w) text_w--;
	uint8_t tx = (uint8_t)(x + (w - text_w + (small ? 1 : 0)) / 2);
	ssd1306_SetCursor(tx, (uint8_t)(y + (small ? 3 : 2)));
	ssd1306_WriteString((char *)label, small ? LABEL10_FONT : LABEL_FONT, fg);
}

// Bank Down (0) or Bank Up (1) in the fifth column
static void draw_bank_switch_cell(const uint8_t *labels, uint8_t which){
	char label[BUTTON_LABEL_LEN + 1];
	label_text(labels + which * BUTTON_LABEL_LEN, label);
	if(label[0] == 0) strcpy(label, which ? "UP" : "DN");
	draw_label_cell(4, which == 1, true, label, false);
}

/*
 * Live values (1.20), in a label, the bank's name or its info line:
 *   $V  the button's value, that of the first CCInc, PC, PCInc or Value
 *       command of its short list; in the bank's name and info, the program
 *       last selected on MIDI_Channel. "-" for none, or a program nothing
 *       has selected yet.
 *   $N  the same, a program shown by its name in the preset names when it
 *       has one
 *   $1 to $8  the eight values of the Value command
 *   $T  the tempo
 *   $$  a $
 * Anything else after a $ stays as it is. The text is cut at max chars. sw is
 * the button, or 0xFF for the bank's own texts. live_sum adds up the values
 * shown, so a change to any of them is seen, and live_any notes there was one.
 */
#define LIVE_LOOK_MS	(50)
static uint32_t live_sum;
static uint8_t live_any;
static uint8_t live_shown_any;	// as the screen was drawn
static uint32_t live_shown_sum;
static uint32_t live_next;

static void put(char *dst, uint8_t *n, uint8_t max, const char *text){
	while(*text && *n < max) dst[(*n)++] = *text++;
}

// A program's name in the preset names, without its trailing spaces; false
// when it has none
static bool preset_name(uint8_t program, char out[PRESET_NAME_LEN + 1]){
	const uint8_t *names = flash_settings_preset_names();
	if(!names || program >= PRESET_NAME_COUNT) return false;
	const uint8_t *src = names + program * PRESET_NAME_LEN;
	uint8_t k = 0;
	for(uint8_t i=0; i<PRESET_NAME_LEN; i++){
		char c = (char)src[i];
		out[i] = (c < 0x20 || c > 0x7E) ? ' ' : c;
		if(out[i] != ' ') k = (uint8_t)(i + 1);
	}
	out[k] = 0;
	return k != 0;
}

static void expand(const char *src, char *dst, uint8_t max, uint8_t bank, uint8_t sw){
	uint8_t n = 0;
	for(; *src && n < max; src++){
		char t = src[1];
		if(t >= 'a' && t <= 'z') t = (char)(t - 'a' + 'A');
		if(src[0] != '$' || !(t == 'V' || t == 'N' || t == 'T' || t == '$' || (t >= '1' && t <= '8'))){
			dst[n++] = *src;
			continue;
		}
		src++;
		if(t == '$'){
			dst[n++] = '$';
			continue;
		}
		uint8_t kind = LIVE_NUMBER;
		uint16_t v;
		if(t == 'T'){
			v = tempo_get_bpm();
		} else if(t != 'V' && t != 'N'){
			v = sw_get_value((uint8_t)(t - '1'));
		} else if(sw < MIDI_NUM_SWITCHES){
			uint8_t b = 0;
			kind = sw_button_value(bank, sw, &b);
			v = b;
		} else {
			uint8_t ch = pGlobalSettings[GLOBAL_SETTINGS_CHANNEL];
			kind = LIVE_PROGRAM;
			v = sw_get_program(midiCmd_channel(ch <= 15 ? ch : 0));
		}
		live_any = 1;
		live_sum = live_sum * 31U + v + ((uint32_t)kind << 16);
		if(kind == LIVE_NONE || (kind == LIVE_PROGRAM && v > 127)){
			put(dst, &n, max, "-");
			continue;
		}
		char name[PRESET_NAME_LEN + 1];
		if(t == 'N' && kind == LIVE_PROGRAM && preset_name((uint8_t)v, name)){
			put(dst, &n, max, name);
			continue;
		}
		char num[6];
		snprintf(num, sizeof(num), "%u", v);
		put(dst, &n, max, num);
	}
	dst[n] = 0;
}

// The label a button shows: its own, its live values filled in, or its name
static void button_text(uint8_t bank, uint8_t sw, char out[BUTTON_LABEL_LEN + 2]){
	static const char ids[MIDI_NUM_SWITCHES] = {'1','2','3','4','A','B','C','D'};
	char label[BUTTON_LABEL_LEN + 1];
	get_label(bank, sw, label);
	// The wide cells take one more character, in the small letters
	expand(label, out, ten_cell_labels() ? BUTTON_LABEL_LEN : BUTTON_LABEL_LEN + 1, bank, sw);
	if(out[0] == 0){
		out[0] = ids[sw];
		out[1] = 0;
	}
}

// The bank's name (4 chars) or its info line (8), live values filled in
static void bank_text(uint8_t bank, bool info, char out[9]){
	const uint8_t *src = pBankStrings + (12 * bank) + (info ? 4 : 0);
	uint8_t len = info ? 8 : 4;
	char raw[9];
	for(uint8_t i=0; i<len; i++){
		char c = (char)src[i];
		raw[i] = (c < 0x20 || c > 0x7E) ? ' ' : c;
	}
	raw[len] = 0;
	expand(raw, out, len, bank, 0xFF);
}

// What the live values on a bank's screen come to, in live_sum and live_any
static void live_scan(uint8_t bank){
	char text[BUTTON_LABEL_LEN + 2 > 9 ? BUTTON_LABEL_LEN + 2 : 9];
	live_sum = 0;
	live_any = 0;
	for(uint8_t sw=0; sw<MIDI_NUM_SWITCHES; sw++) button_text(bank, sw, text);
	bank_text(bank, false, text);
	bank_text(bank, true, text);
}

// Once in a while: true when a live value on the screen has changed
static bool live_changed(void){
	if(!live_shown_any || (int32_t)(HAL_GetTick() - live_next) < 0) return false;
	live_next = HAL_GetTick() + LIVE_LOOK_MS;
	live_scan(current_bank);
	return live_sum != live_shown_sum;
}

static void draw_cell(uint8_t bank, uint8_t sw){
	char label[BUTTON_LABEL_LEN + 2];
	button_text(bank, sw, label);

	uint8_t active;
	if(bank & PREVIEW_DIRECT){
		// Choosing a bank: the bank you are in shows inverted
		active = bank != PREVIEW_DIRECT &&
			((bank & 0x7F) - 1) * DIRECT_GROUP + sw == sw_get_home_bank();
	} else {
		active = sw_button_is_toggle(bank, sw) && sw_get_toggle_state(bank, sw);
	}
	draw_label_cell(sw % 4, sw < 4, ten_cell_labels() != NULL, label, active);
}

// Host text that only lasts while the bank stays put
static void drop_bank_text(void){
	for(uint8_t p=0; p<DISPLAY_TEXT_PLACES; p++){
		if(host_keep[p] == TEXT_KEEP_BANK) host_text[p][0] = 0;
	}
}

/*
 * Text in a place w pixels wide at x, y. A text that does not fit is drawn
 * scroll_px along, clipped to its place, and counted in scroll_need.
 */
static void draw_text(uint8_t x, uint8_t y, uint8_t w, const char *text, FontDef font){
	uint16_t width = (uint16_t)strlen(text) * font.FontWidth;
	if(width <= w){
		ssd1306_SetCursor(x, y);
		ssd1306_WriteString((char *)text, font, White);
		return;
	}
	uint16_t over = width - w;
	if(over > scroll_need) scroll_need = over;
	uint16_t off = (scroll_px < over) ? scroll_px : over;
	for(uint16_t col=0; col<w; col++){
		uint16_t px = col + off;
		char ch = text[px / font.FontWidth];
		if(ch < 32 || ch > 126) continue;
		uint8_t j = px % font.FontWidth;
		const uint16_t *rows = ssd1306_Glyph(ch, font);
		for(uint8_t i=0; i<font.FontHeight; i++){
			if((uint16_t)(rows[i] << j) & 0x8000) ssd1306_DrawPixel(x + col, y + i, White);
		}
	}
}

/*
 * The top line: the bank name and its info, or the host's text in their
 * place. A whole line text hides both. override, when not NULL, stands for
 * the host text of place over_place (a text shown for a moment).
 */
static void top_texts(uint8_t bank, uint8_t over_place, const char *override, const char *text[DISPLAY_TEXT_PLACES]){
	for(uint8_t p=0; p<DISPLAY_TEXT_PLACES; p++){
		text[p] = (override && p == over_place) ? override : host_text[p];
	}
	if(bank == current_bank && preview_bank == 0xFF){
		if(!text[DISPLAY_TEXT_NAME][0]) text[DISPLAY_TEXT_NAME] = count_text;
		if(!text[DISPLAY_TEXT_INFO][0]) text[DISPLAY_TEXT_INFO] = beat_text[0] ? beat_text : setlist_text;
		if(sw_locked()) text[DISPLAY_TEXT_INFO] = "LOCKED";	// over anything else there
	}
}

static void draw_top(uint8_t bank, uint8_t over_place, const char *override){
	const char *text[DISPLAY_TEXT_PLACES];
	top_texts(bank, over_place, override, text);
	// A moment's text in the bank name or info shows even over a whole line
	if(override && over_place <= DISPLAY_TEXT_NAME){
		text[DISPLAY_TEXT_LINE_LARGE] = text[DISPLAY_TEXT_LINE_SMALL] = "";
	}
	fill_rect(0, 0, SSD1306_WIDTH, ROW_TOP_Y - 1, Black);
	scroll_need = 0;

	if(text[DISPLAY_TEXT_LINE_LARGE][0]){
		draw_text(0, 0, SCREEN_SHOWN_W, text[DISPLAY_TEXT_LINE_LARGE], Font_11x18);
		return;
	}
	if(text[DISPLAY_TEXT_LINE_SMALL][0]){
		draw_text(0, 6, SCREEN_SHOWN_W, text[DISPLAY_TEXT_LINE_SMALL], Font_7x10);
		return;
	}

	// Bank name, large 4 chars then small 8 chars on the same line
	char own[9];
	ssd1306_SetCursor(0, 0);
	if(text[DISPLAY_TEXT_NAME][0]){
		draw_text(0, 0, NAME_W, text[DISPLAY_TEXT_NAME], Font_11x18);
	} else {
		bank_text(bank, false, own);
		ssd1306_WriteString(own, Font_11x18, White);
	}
	ssd1306_SetCursor(INFO_X, 6);
	if(text[DISPLAY_TEXT_INFO][0]){
		draw_text(INFO_X, 6, SCREEN_SHOWN_W - INFO_X, text[DISPLAY_TEXT_INFO], Font_7x10);
	} else {
		bank_text(bank, true, own);
		ssd1306_WriteString(own, Font_7x10, White);
	}
}

// The gig view shows, rather than the labels
static bool gig_showing(void){
	return gig_on && !gig_labels_until && preview_bank == 0xFF;
}

// A text without the spaces around it, in out
static const char *trimmed(const char *src, char *out, uint8_t max){
	while(*src == ' ') src++;
	uint8_t n = 0;
	while(src[n] && n < max){
		out[n] = src[n];
		n++;
	}
	while(n && out[n-1] == ' ') n--;
	out[n] = 0;
	return out;
}

// In the large font across the screen, in the middle when it fits
static void draw_gig_line(uint8_t y, const char *text){
	uint16_t w = (uint16_t)strlen(text) * Font_11x18.FontWidth;
	draw_text(w < SCREEN_SHOWN_W ? (uint8_t)((SCREEN_SHOWN_W - w) / 2) : 0, y, SCREEN_SHOWN_W, text, Font_11x18);
}

/*
 * The gig view's screen: the song's name, the host's whole line text before
 * its text for the name, and the info line under it. As draw_top, override
 * stands for the host text of over_place.
 */
static void draw_gig(uint8_t bank, uint8_t over_place, const char *override){
	const char *text[DISPLAY_TEXT_PLACES];
	top_texts(bank, over_place, override, text);
	ssd1306_Fill(Black);
	scroll_need = 0;

	char own[9], name[DISPLAY_TEXT_MAX + 1], info[DISPLAY_TEXT_MAX + 1];
	const char *src = text[DISPLAY_TEXT_LINE_LARGE][0] ? text[DISPLAY_TEXT_LINE_LARGE]
			: text[DISPLAY_TEXT_LINE_SMALL][0] ? text[DISPLAY_TEXT_LINE_SMALL] : text[DISPLAY_TEXT_NAME];
	if(!src[0]){
		bank_text(bank, false, own);
		src = own;
	}
	trimmed(src, name, DISPLAY_TEXT_MAX);
	uint8_t big = Font_11x18.FontWidth * GIG_NAME_SCALE;
	uint8_t len = (uint8_t)strlen(name);
	if(len * big <= SCREEN_SHOWN_W){
		uint8_t x = (uint8_t)((SCREEN_SHOWN_W - len * big) / 2);
		for(uint8_t i=0; i<len; i++){
			draw_big_char((uint8_t)(x + i * big), GIG_NAME_Y, name[i], GIG_NAME_SCALE, White);
		}
	} else {
		draw_gig_line(GIG_NAME_Y + 9, name);
	}

	src = text[DISPLAY_TEXT_INFO];
	if(!src[0]){
		bank_text(bank, true, own);
		src = own;
	}
	draw_gig_line(GIG_INFO_Y, trimmed(src, info, DISPLAY_TEXT_MAX));
}

// The top line, or in the gig view the whole screen, as it stands
static void draw_head(uint8_t bank, uint8_t over_place, const char *override){
	if(gig_showing()) draw_gig(bank, over_place, override);
	else draw_top(bank, over_place, override);
}

// A long text starts scrolling from the beginning the next time it is drawn
static void scroll_restart(void){
	scroll_fresh = 1;
}

// Before drawing the line: back to the start if a fresh scroll was asked for
static uint8_t scroll_take_fresh(void){
	uint8_t fresh = scroll_fresh;
	scroll_fresh = 0;
	if(fresh) scroll_px = 0;
	return fresh;
}

// After drawing it: a fresh scroll starts only if something is long
static void scroll_start(uint8_t fresh){
	if(!fresh) return;
	scroll_state = scroll_need ? SCROLL_HOLD_START : SCROLL_IDLE;
	scroll_next = HAL_GetTick() + SCROLL_HOLD_MS;
}

/*
 * Move the scroll on when it is due. Returns 1 when the top line has to be
 * drawn again; not while the last screen is still going out, so the main loop
 * never waits for it.
 */
static uint8_t scroll_step(void){
	if(scroll_state == SCROLL_IDLE || scroll_fresh) return 0;
	if((int32_t)(HAL_GetTick() - scroll_next) < 0 || ssd1306_Busy()) return 0;
	if(scroll_state == SCROLL_HOLD_END){
		scroll_state = SCROLL_IDLE;
		scroll_px = 0;
		return 1;
	}
	scroll_state = SCROLL_MOVING;
	scroll_px += SCROLL_STEP_PX;
	if(scroll_px >= scroll_need){
		scroll_px = scroll_need;
		scroll_state = SCROLL_HOLD_END;
		scroll_next = HAL_GetTick() + SCROLL_HOLD_MS;
	} else {
		scroll_next = HAL_GetTick() + SCROLL_STEP_MS;
	}
	return 1;
}

// The bank screen comes back with its long texts still, at their start
static void moment_done(void){
	moment_showing = 0;
	scroll_state = SCROLL_IDLE;
	scroll_px = 0;
}

// The place in the setlist, and the next song's name without its spaces
static void setlist_update(void){
	uint8_t n, next;
	uint8_t at = sw_setlist_place(&n, &next);
	if(!at){
		setlist_text[0] = 0;
		return;
	}
	char name[5] = "END";
	if(next != 0xFF){
		const uint8_t *src = pBankStrings + (12 * next);
		uint8_t k = 0;
		for(uint8_t i=0; i<4; i++){
			if(src[i] > ' ' && src[i] < 0x7F) name[k++] = (char)src[i];
		}
		name[k] = 0;
	}
	snprintf(setlist_text, sizeof(setlist_text), "%u/%u%c%s", at, n, next != 0xFF ? '>' : ' ', name);
}

// The bank screen as it stands: a long text keeps its place in its scroll
// The bank screen into the buffer, without sending it
static void render_bank(uint8_t bankNumber){
	// Cleared first, so a refresh asked for while drawing is not lost
	refresh_pending = 0;
	if(bankNumber != current_bank) drop_bank_text();
	current_bank = bankNumber;
	uint8_t fresh = scroll_take_fresh();
	setlist_update();

	ssd1306_Fill(Black);
	draw_head(bankNumber, 0, NULL);
	scroll_start(fresh);

	for(uint8_t sw=0; !gig_showing() && sw<MIDI_NUM_SWITCHES; sw++){
		draw_cell(bankNumber, sw);
	}
	const uint8_t *bank_switch = ten_cell_labels();
	if(bank_switch && !gig_showing()){
		draw_bank_switch_cell(bank_switch, 0);
		draw_bank_switch_cell(bank_switch, 1);
	}
	live_scan(bankNumber);
	live_shown_any = live_any;
	live_shown_sum = live_sum;
	live_next = HAL_GetTick() + LIVE_LOOK_MS;
}

static void draw_bank(uint8_t bankNumber){
	render_bank(bankNumber);
	ssd1306_UpdateScreen();
}

/*
 * Entering a bank scrolls its long texts. The screen is only asked for here
 * and drawn by display_task, on the same pass of the main loop, so the
 * bank's enter commands and whatever else the change sends are not held up
 * behind it. A readout those commands show (a tempo, a value) is drawn over
 * the new bank, see show_overlay.
 */
void display_setBankName(uint8_t bankNumber){
	if(moment_showing) moment_done();
	scroll_restart();
	if(bankNumber != current_bank) drop_bank_text();
	current_bank = bankNumber;
	overlay_until = 0;	// the new bank takes the place of a readout
	gig_labels_until = 0;	// and of the labels a press brought back
	refresh_pending = 1;
}

/*
 * A bank the bank switches stepped to but that is not confirmed yet: its own
 * name, inverted, and its buttons, in place of the bank you are in. Host
 * texts, readouts and scrolls wait until it is over. 0xFF ends it.
 */
void display_preview(uint8_t bankNumber){
	preview_bank = bankNumber;
	if(bankNumber == 0xFF){
		overlay_until = 0;	// back to the bank screen, not a stale readout
		if(moment_showing) moment_done();
	}
	refresh_pending = 1;
}

static void draw_preview(void){
	refresh_pending = 0;
	const uint8_t *pString;
	char direct[20];	// 4 large, 8 small
	if(preview_bank & PREVIEW_DIRECT){
		uint8_t first = (uint8_t)(((preview_bank & 0x7F) - 1) * DIRECT_GROUP);
		if(preview_bank == PREVIEW_DIRECT) snprintf(direct, sizeof(direct), "BANK0-31    ");
		else snprintf(direct, sizeof(direct), "BANK%u-%u     ", first, first + DIRECT_GROUP - 1);
		pString = (const uint8_t *)direct;
	} else {
		// Its own texts, live values filled in and padded to their places
		char text[9];
		bank_text(preview_bank, false, text);
		snprintf(direct, sizeof(direct), "%-4s", text);
		bank_text(preview_bank, true, text);
		snprintf(direct + 4, sizeof(direct) - 4, "%-8s", text);
		pString = (const uint8_t *)direct;
	}
	ssd1306_Fill(Black);
	fill_rect(0, 0, SSD1306_WIDTH, ROW_TOP_Y - 3, White);
	ssd1306_SetCursor(1, 1);
	for(int i=0; i<4; i++){
		ssd1306_WriteChar((char)pString[i], Font_11x18, Black);
	}
	ssd1306_SetCursor(INFO_X, 6);
	for(int i=0; i<8; i++){
		ssd1306_WriteChar((char)pString[4 + i], Font_7x10, Black);
	}
	for(uint8_t sw=0; sw<MIDI_NUM_SWITCHES; sw++){
		draw_cell(preview_bank, sw);
	}
	ssd1306_UpdateScreen();
}

void display_showPage(uint8_t bankNumber){
	current_bank = bankNumber;	// same bank for the song: nothing is dropped
	display_setBankName(bankNumber);
}

uint8_t display_host_text(uint8_t place, uint8_t how, const uint8_t *text, uint8_t len){
	if(place >= DISPLAY_TEXT_PLACES || how > TEXT_KEEP_MOMENT) return 0;

	char *dst = (how == TEXT_KEEP_MOMENT) ? moment_text : host_text[place];
	if(len > DISPLAY_TEXT_MAX) len = DISPLAY_TEXT_MAX;
	// The same text sent again is left scrolling, or still, as it was
	uint8_t same = (dst[len] == 0);
	for(uint8_t i=0; i<len; i++){
		char c = (char)text[i];
		c = (c < 0x20 || c > 0x7E) ? ' ' : c;
		if(dst[i] != c) same = 0;
		dst[i] = c;
	}
	dst[len] = 0;

	if(how == TEXT_KEEP_MOMENT){
		if(len){
			moment_place = place;
			moment_pending = 1;
		}
	} else {
		host_keep[place] = how;
		// The two whole line sizes take each other's place
		if(len && place == DISPLAY_TEXT_LINE_LARGE) host_text[DISPLAY_TEXT_LINE_SMALL][0] = 0;
		if(len && place == DISPLAY_TEXT_LINE_SMALL) host_text[DISPLAY_TEXT_LINE_LARGE][0] = 0;
		if(!same) scroll_restart();
		refresh_pending = 1;
	}
	// A new song name is worth looking at: wake the screen
	sleep_note_activity();
	return 1;
}

void display_request_refresh(void){
	refresh_pending = 1;
}

void display_gig_from_settings(void){
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_BANNER];
	gig_on = v != 0xFF && (v & GIG_VIEW_ON);
	gig_labels_until = 0;
	refresh_pending = 1;
}

void display_gig_toggle(void){
	gig_on = !gig_on;
	gig_labels_until = 0;	// the press that turned it on does not hide it
	scroll_restart();
	refresh_pending = 1;
}

void display_gig_press(void){
	if(!gig_on) return;
	if(!gig_labels_until){
		scroll_restart();
		refresh_pending = 1;
	}
	gig_labels_until = HAL_GetTick() + GIG_LABELS_MS;
	if(!gig_labels_until) gig_labels_until = 1;
}

/*
 * The editor's screen. Six rows of Font_7x10 fit in the 64 pixels: the title,
 * then the lines, with the cursor row drawn the other way round so it stands
 * out like a toggle button does on the bank screen.
 */
void display_editor(const char *title, const char lines[][DISPLAY_EDIT_COLS + 1],
		uint8_t count, uint8_t cursor){
	banner_on = 0;
	editor_on = 1;
	overlay_until = 0;
	refresh_pending = 0;

	ssd1306_Fill(Black);
	ssd1306_SetCursor(0, 0);
	ssd1306_WriteString((char *)title, Font_7x10, White);

	if(count > DISPLAY_EDIT_ROWS) count = DISPLAY_EDIT_ROWS;
	for(uint8_t i=0; i<count; i++){
		uint8_t y = (uint8_t)(12 + i * 10);
		SSD1306_COLOR fg = White;
		if(i == cursor){
			fill_rect(0, y, SSD1306_WIDTH, 10, White);	// exactly the row, so the one above keeps its pixels
			fg = Black;
		}
		ssd1306_SetCursor(0, y);
		ssd1306_WriteString((char *)lines[i], Font_7x10, fg);
	}

	ssd1306_UpdateScreen();
}

void display_editor_end(void){
	editor_on = 0;
	refresh_pending = 1;
}

/*
 * Replace the bank's info line with "120 BPM" (and a * while the clock is
 * running) for a moment. Only that line is redrawn, so the bank name and the
 * button grid stay put.
 */
/*
 * Replace the bank's info line with a short message for OVERLAY_MS. Only that
 * line is redrawn, so the bank name and the button grid stay put.
 */
// The readout over the info line, the bank screen under it as it is now
static void draw_overlay(void){
	if(refresh_pending) render_bank(current_bank);	// a bank just entered, under the readout
	if(gig_showing()){
		// In the info line's place, as large as it is
		fill_rect(0, GIG_INFO_Y, SSD1306_WIDTH, SSD1306_HEIGHT - GIG_INFO_Y, Black);
		uint8_t w = (uint8_t)(strlen(overlay_msg) * Font_11x18.FontWidth);
		if(overlay_bar == 0xFF){
			ssd1306_SetCursor((uint8_t)((SCREEN_SHOWN_W - w) / 2), GIG_INFO_Y);
		} else {
			ssd1306_SetCursor(0, GIG_INFO_Y);
			uint8_t x = (uint8_t)(w + 4);
			ssd1306_DrawRectangle(x, GIG_INFO_Y + 1, SCREEN_SHOWN_W - 1, GIG_INFO_Y + 16, White);
			fill_rect((uint8_t)(x + 2), GIG_INFO_Y + 3, (uint8_t)(overlay_bar * (SCREEN_SHOWN_W - x - 4) / 127U), 12, White);
		}
		ssd1306_WriteString(overlay_msg, Font_11x18, White);
		ssd1306_UpdateScreen();
		refresh_pending = 0;
		return;
	}
	fill_rect(50, 6, SSD1306_WIDTH - 50, 10, Black);
	ssd1306_SetCursor(50, 6);
	ssd1306_WriteString(overlay_msg, Font_7x10, White);
	if(overlay_bar != 0xFF){
		// A frame from the pedal's number to the edge, filled up to the value
		ssd1306_DrawRectangle(PEDAL_BAR_X, 7, SCREEN_SHOWN_W - 1, 15, White);
		fill_rect(PEDAL_BAR_X + 2, 9, (uint8_t)(overlay_bar * (SCREEN_SHOWN_W - PEDAL_BAR_X - 4) / 127U), 5, White);
	}
	ssd1306_UpdateScreen();
	refresh_pending = 0;
}

// bar: an expression pedal's value drawn as a bar after msg, 0xFF for none
static void show_readout(const char *msg, uint8_t bar){
	if(banner_running()) return;	// the banner is not cut short for a readout
	if(preview_bank != 0xFF) return;	// nor the bank being chosen
	if(tuner_on) return;			// nor the tuner
	if(moment_showing) moment_done();
	snprintf(overlay_msg, sizeof(overlay_msg), "%s", msg);
	overlay_bar = bar;
	draw_overlay();
	overlay_until = HAL_GetTick() + OVERLAY_MS;
}

static void show_overlay(const char *msg){
	show_readout(msg, 0xFF);
}

void display_show_tempo(void){
	char msg[13];
	if(tempo_external_present()){
		// Following the host: fits the 8 character info line
		snprintf(msg, sizeof(msg), "%sEXT %u", tempo_clock_running() ? "*" : "", tempo_get_bpm());
	} else {
		snprintf(msg, sizeof(msg), "%s%u BPM", tempo_clock_running() ? "*" : "", tempo_get_bpm());
	}

	show_overlay(msg);
}

/*
 * A relative CC button changes a value nobody could see. Show it in the info
 * line for a moment. Eight characters fit, so "CC120=127" loses one C.
 */
void display_show_cc(uint8_t cc, uint8_t value){
	char msg[13];
	if(cc < 100){
		snprintf(msg, sizeof(msg), "CC%u=%u", cc, value);
	} else {
		snprintf(msg, sizeof(msg), "C%u=%u", cc, value);
	}
	show_overlay(msg);
}

/*
 * Where an expression pedal is, while it moves: "EXP1 64", or a 1 and a bar.
 * The value is only noted here; display_task draws the latest one once the
 * last screen has gone out, so a sweep never waits on the display.
 */
void display_show_pedal(uint8_t pedal, uint8_t value, bool bar){
	pedal_value = value;
	pedal_bar = bar;
	pedal_tick = HAL_GetTick();
	pedal_pending = (uint8_t)(pedal + 1U);
}

static void draw_pedal(void){
	char msg[13];
	uint8_t pedal = (uint8_t)(pedal_pending - 1U);
	pedal_pending = 0;
	// Kept waiting by the tuner or the banner: gone by now
	if(HAL_GetTick() - pedal_tick > OVERLAY_MS) return;
	if(pedal_bar){
		snprintf(msg, sizeof(msg), "%u", (unsigned)(pedal + 1U));
	} else {
		snprintf(msg, sizeof(msg), "EXP%u %u", (unsigned)(pedal + 1U), (unsigned)pedal_value);
	}
	show_readout(msg, pedal_bar ? pedal_value : 0xFF);
}

// A relative PC's program: by its preset name when it has one (1.20)
void display_show_program(uint8_t program){
	char msg[PRESET_NAME_LEN + 1];
	if(!preset_name(program, msg)) snprintf(msg, sizeof(msg), "PC %u", program);
	show_overlay(msg);
}

void display_show_message(const char *msg){
	show_overlay(msg);
}

void display_show_config(uint8_t slot){
	banner_on = 0;
	drop_bank_text();
	char title[12];
	snprintf(title, sizeof(title), "CONFIG %u", (unsigned)(slot + 1));

	ssd1306_Fill(Black);
	ssd1306_SetCursor(0, 8);
	ssd1306_WriteString(title, Font_11x18, White);
	ssd1306_SetCursor(0, 38);
	for(int i=0; i<16; i++){
		ssd1306_WriteChar((char)pGlobalSettings[16+i], Font_7x10, White);
	}
	ssd1306_UpdateScreen();

	// The bank screen comes back once the notice has been read
	overlay_msg[0] = 0;
	overlay_until = HAL_GetTick() + OVERLAY_MS;
	refresh_pending = 0;
}

void display_show_setlist(uint8_t which, const uint8_t *name){
	banner_on = 0;
	char title[12];
	snprintf(title, sizeof(title), "SETLIST %u", (unsigned)(which + 1));

	ssd1306_Fill(Black);
	ssd1306_SetCursor(0, 8);
	ssd1306_WriteString(title, Font_11x18, White);
	if(name){
		ssd1306_SetCursor(0, 38);
		for(int i=0; i<SETLIST_NAME_LEN; i++){
			char c = (char)name[i];
			ssd1306_WriteChar((c >= ' ' && c <= '~') ? c : ' ', Font_11x18, White);
		}
	}
	ssd1306_UpdateScreen();

	overlay_msg[0] = 0;
	overlay_until = HAL_GetTick() + OVERLAY_MS;
	refresh_pending = 0;
}

// Safe mode at power on, over the bank screen until it has been read
// A word in large type and a line under it, for a few seconds after boot
static void show_notice(const char *big, const char *small){
	banner_on = 0;
	drop_bank_text();
	ssd1306_Fill(Black);
	ssd1306_SetCursor((uint8_t)((128 - 11 * strlen(big)) / 2), 8);
	ssd1306_WriteString((char *)big, Font_11x18, White);
	ssd1306_SetCursor((uint8_t)((128 - 7 * strlen(small)) / 2), 38);
	ssd1306_WriteString((char *)small, Font_7x10, White);
	ssd1306_UpdateScreen();

	overlay_msg[0] = 0;
	overlay_until = HAL_GetTick() + SAFE_MODE_MS;
	refresh_pending = 0;
}

void display_show_safe_mode(void){
	show_notice("SAFE MODE", "NOTHING SENT");
}

void display_show_restarted(void){
	show_notice("RESTARTED", "AFTER A LOCK-UP");
}

void display_show_saved(void){
	show_notice("SAVED", "SCENE");
}

// Tap Save, with the tempo kept, or 0 when the enter list had no room for it
void display_show_tempo_saved(uint16_t bpm){
	char line[16];
	if(bpm == 0){
		show_notice("NOT SAVED", "ENTER LIST FULL");
		return;
	}
	snprintf(line, sizeof line, "TEMPO %u BPM", (unsigned)bpm);
	show_notice("SAVED", line);
}

// Stays up: the pedal pauses until the tool restarts it
void display_show_upload(void){
	show_notice("RECEIVING", "CONFIGURATION");
}

/*
 * A host text for a moment, drawn over the top line like the tempo readout.
 * A long one stays up until it has scrolled to its end.
 */
static void draw_moment_text(void){
	draw_head(current_bank, moment_place, moment_text);
	ssd1306_UpdateScreen();
}

static void show_moment_text(void){
	moment_pending = 0;
	if(refresh_pending) render_bank(current_bank);	// a bank just entered, under the text
	moment_showing = 1;
	scroll_restart();
	uint8_t fresh = scroll_take_fresh();
	draw_moment_text();
	scroll_start(fresh);
	overlay_until = HAL_GetTick() + OVERLAY_MS;
}

// Work the clock's texts out again; true when they changed
static bool beat_update(void){
	char beat[sizeof(beat_text)] = "", count[sizeof(count_text)] = "";
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_LED_FEEDBACK];
	uint8_t per_bar = (v == 0xFF) ? 0 : (uint8_t)((v & BEAT_COUNTER_MASK) >> BEAT_COUNTER_SHIFT);
	uint32_t bar;
	uint8_t b;
	if(tempo_bar_beat(per_bar, &bar, &b)){
		snprintf(beat, sizeof(beat), "%u.%u %u", (unsigned)bar, b, tempo_get_bpm());
	}
	uint8_t left = sw_count_in();
	if(left) snprintf(count, sizeof(count), "IN%2u", left);
	if(!strcmp(beat, beat_text) && !strcmp(count, count_text)) return false;
	strcpy(beat_text, beat);
	strcpy(count_text, count);
	return true;
}

void display_tuner(bool on){
	tuner_on = on;
	tuner_note = TUNER_NO_NOTE;	// until the amp hears one
	tuner_deviance = TUNER_CENTRE;
	tuner_dirty = 1;
	if(!on) refresh_pending = 1;	// the bank screen, as it was
}

void display_tuner_note(uint8_t note){
	if(note == tuner_note) return;
	tuner_note = note;
	tuner_dirty = 1;
}

void display_tuner_deviance(uint16_t value){
	if(value == tuner_deviance) return;
	tuner_deviance = value;
	tuner_dirty = 1;
}

// A character of the large font, each of its pixels a square of scale
static void draw_big_char(uint8_t x, uint8_t y, char ch, uint8_t scale, SSD1306_COLOR color){
	const uint16_t *rows = ssd1306_Glyph(ch, Font_11x18);
	for(uint8_t i=0; i<Font_11x18.FontHeight; i++){
		for(uint8_t j=0; j<Font_11x18.FontWidth; j++){
			if((uint16_t)(rows[i] << j) & 0x8000){
				fill_rect((uint8_t)(x + j * scale), (uint8_t)(y + i * scale), scale, scale, color);
			}
		}
	}
}

static void draw_tuner(void){
	tuner_dirty = 0;
	uint8_t note = tuner_note;
	int32_t off = (int32_t)tuner_deviance - TUNER_CENTRE;
	bool in_tune = note != TUNER_NO_NOTE && off <= TUNER_IN_TUNE && off >= -TUNER_IN_TUNE;

	ssd1306_Fill(Black);

	// The note, in the middle; boxed in, the other way round, when in tune
	const char *name = (note == TUNER_NO_NOTE) ? "-" : note_names[note % 12];
	uint8_t w = (uint8_t)(strlen(name) * Font_11x18.FontWidth * TUNER_NOTE_SCALE);
	uint8_t x = (uint8_t)((SCREEN_SHOWN_W - w) / 2);
	SSD1306_COLOR fg = White;
	if(in_tune){
		fill_rect((uint8_t)(x - 6), 0, (uint8_t)(w + 12), TUNER_SCALE_Y - 6, White);
		fg = Black;
	}
	for(uint8_t i=0; name[i]; i++){
		draw_big_char((uint8_t)(x + i * Font_11x18.FontWidth * TUNER_NOTE_SCALE),
				TUNER_NOTE_Y, name[i], TUNER_NOTE_SCALE, fg);
	}

	// The scale: a line, a mark every quarter and a tall one in the middle
	uint8_t mid = SCREEN_SHOWN_W / 2;
	ssd1306_Line(mid - TUNER_HALF_W, TUNER_SCALE_Y, mid + TUNER_HALF_W, TUNER_SCALE_Y, White);
	for(int8_t q=-4; q<=4; q++){
		uint8_t mx = (uint8_t)(mid + q * TUNER_HALF_W / 4);
		uint8_t tall = (q == 0) ? 6 : 3;
		ssd1306_Line(mx, TUNER_SCALE_Y - tall, mx, TUNER_SCALE_Y + tall, White);
	}
	if(note == TUNER_NO_NOTE){
		ssd1306_UpdateScreen();
		return;
	}

	// The needle under the line, filled in when in tune
	if(off > TUNER_FULL) off = TUNER_FULL;
	if(off < -TUNER_FULL) off = -TUNER_FULL;
	uint8_t nx = (uint8_t)(mid + off * TUNER_HALF_W / TUNER_FULL);
	if(in_tune){
		fill_rect((uint8_t)(nx - 2), TUNER_SCALE_Y + 2, 5, 16, White);
	} else {
		ssd1306_DrawRectangle((uint8_t)(nx - 2), TUNER_SCALE_Y + 2, (uint8_t)(nx + 2), TUNER_SCALE_Y + 17, White);
		// Which way to turn: the arrows point to the middle
		draw_big_char(off < 0 ? 2 : SCREEN_SHOWN_W - 2 - Font_11x18.FontWidth, 12,
				off < 0 ? '>' : '<', 1, White);
	}
	ssd1306_UpdateScreen();
}

void display_task(void){
	if(editor_on) return;	// the editor draws its own screen
	if(tuner_on){
		// The tuner has the screen; the rest waits under it, the banner
		// too, and comes back when it closes
		if(ssd1306_Busy()) return;
		banner_on = 0;
		if(tuner_dirty) draw_tuner();
		return;
	}
	// The last screen is still going out: come back rather than wait for it,
	// so a press is never held up behind a scroll step
	if(ssd1306_Busy()) return;
	if(banner_running()){
		display_banner_task();
		return;
	}
	if(preview_bank != 0xFF){
		if(refresh_pending) draw_preview();
		return;
	}
	if(moment_pending){
		show_moment_text();
		return;
	}
	if(pedal_pending){
		draw_pedal();
		return;
	}
	// An external clock appeared or changed tempo
	if(tempo_take_display_update()){
		display_show_tempo();
		return;
	}
	// Let the tempo readout sit for its moment before the bank screen returns
	if(overlay_until){
		if(moment_showing){
			// A moment's text ends at its end, not back at its start
			uint8_t ending = (scroll_state == SCROLL_HOLD_END);
			if(scroll_step() && !ending) draw_moment_text();
		}
		if((int32_t)(HAL_GetTick() - overlay_until) < 0 || (moment_showing && scroll_state != SCROLL_IDLE)){
			// A value a label shows changed under the readout: at once, not after it
			if(!moment_showing && overlay_msg[0] && live_changed()){
				refresh_pending = 1;
				draw_overlay();
			}
			return;
		}
		overlay_until = 0;
		if(moment_showing) moment_done();
		refresh_pending = 1;
	}
	// The labels a press brought back give way to the gig view again
	if(gig_labels_until && (int32_t)(HAL_GetTick() - gig_labels_until) >= 0){
		gig_labels_until = 0;
		scroll_restart();
		refresh_pending = 1;
	}
	bool beat_changed = beat_update();
	if(!refresh_pending && live_changed()) refresh_pending = 1;
	if(refresh_pending){
		draw_bank(current_bank);
	} else if(beat_changed || scroll_step()){
		draw_head(current_bank, 0, NULL);
		ssd1306_UpdateScreen();
	}
}
