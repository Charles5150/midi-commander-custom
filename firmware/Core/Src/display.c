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
 * The host can put its own text in the top line over SysEx (the patch or song
 * name): in place of the bank name, of the info line, or across the whole line.
 * A text wider than its place scrolls across it once, when it arrives or the
 * bank is entered, and then shows its beginning.
 *
 * At power on the configuration can have a banner instead: the pedal's own
 * text (banner_store.c) or the configuration's name, then the firmware
 * version, cross the screen in large letters, once. Any switch ends it, and
 * the bank screen waits for it underneath.
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

#define CELL_W		(32)
#define CELL_H		(14)
#define ROW_TOP_Y	(23)
#define ROW_BOT_Y	(45)
#define LABEL_FONT	Font_7x10
#define LABEL_CHAR_W	(7)
#define SCREEN_SHOWN_W	(128)	// the buffer is 130 wide, the glass shows 128
#define NAME_W		(44)	// 4 large chars
#define INFO_X		(50)

static volatile uint8_t refresh_pending = 0;
static uint8_t current_bank = 0;

// A transient overlay (the tempo readout) shown instead of the bank info
#define OVERLAY_MS	(1500)
#define SAFE_MODE_MS	(3000)
static uint8_t editor_on = 0;	// the on-pedal editor owns the screen
static uint8_t preview_bank = 0xFF;	// a bank shown before it is confirmed
static uint32_t overlay_until = 0;

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
	uint8_t speed = pGlobalSettings[GLOBAL_SETTINGS_BANNER];
	if(speed == 0 || speed > 3) return 0;

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
	banner_text[len++] = 'v';
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
	// The text's first column is at SCREEN_SHOWN_W - banner_pos
	for(uint16_t col=0; col<SCREEN_SHOWN_W; col++){
		int32_t px = (int32_t)col + banner_pos - SCREEN_SHOWN_W;
		if(px < 0 || px >= width) continue;
		char ch = banner_text[px / Font_11x18.FontWidth];
		uint8_t j = px % Font_11x18.FontWidth;
		const uint16_t *rows = Font_11x18.data + (ch - 32) * Font_11x18.FontHeight;
		for(uint8_t i=0; i<Font_11x18.FontHeight; i++){
			if((uint16_t)(rows[i] << j) & 0x8000) ssd1306_DrawPixel(col, BANNER_Y + i, White);
		}
	}
	ssd1306_UpdateLines(BANNER_FIRST_PAGE, BANNER_LAST_PAGE);
	banner_pos += banner_speed;
}

// Copy the stored label of a button into buf (up to 4 chars, NUL terminated),
// dropping anything not printable. Erased flash (0xFF) yields an empty label.
static void get_label(uint8_t bank, uint8_t sw, char buf[BUTTON_LABEL_LEN + 1]){
	const uint8_t *src = sw_button_label(bank, sw);
	int n = 0;
	for(int i=0; i<BUTTON_LABEL_LEN; i++){
		char c = (char)src[i];
		if(c < 0x20 || c > 0x7E) c = ' ';
		buf[n++] = c;
	}
	while(n > 0 && buf[n-1] == ' ') n--; // trim trailing spaces
	buf[n] = 0;
}

static void draw_cell(uint8_t bank, uint8_t sw){
	static const char ids[MIDI_NUM_SWITCHES] = {'1','2','3','4','A','B','C','D'};
	uint8_t col = sw % 4;
	uint8_t x = col * CELL_W;
	uint8_t y = (sw < 4) ? ROW_TOP_Y : ROW_BOT_Y;

	char label[BUTTON_LABEL_LEN + 1];
	get_label(bank, sw, label);
	if(label[0] == 0){
		label[0] = ids[sw];
		label[1] = 0;
	}

	uint8_t active = sw_button_is_toggle(bank, sw) && sw_get_toggle_state(bank, sw);
	SSD1306_COLOR bg = active ? White : Black;
	SSD1306_COLOR fg = active ? Black : White;

	fill_rect(x, y, CELL_W, CELL_H, bg);

	uint8_t text_w = strlen(label) * LABEL_CHAR_W;
	uint8_t tx = x + (CELL_W - text_w) / 2;
	ssd1306_SetCursor(tx, y + 2);
	ssd1306_WriteString(label, LABEL_FONT, fg);
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
		const uint16_t *rows = font.data + (ch - 32) * font.FontHeight;
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
static void draw_top(uint8_t bank, uint8_t over_place, const char *override){
	const char *text[DISPLAY_TEXT_PLACES];
	for(uint8_t p=0; p<DISPLAY_TEXT_PLACES; p++){
		text[p] = (override && p == over_place) ? override : host_text[p];
	}
	// A moment's text in the bank name or info shows even over a whole line
	if(override && over_place <= DISPLAY_TEXT_NAME){
		text[DISPLAY_TEXT_LINE_LARGE] = text[DISPLAY_TEXT_LINE_SMALL] = "";
	}
	const uint8_t *pString = pBankStrings + (12 * bank);

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
	ssd1306_SetCursor(0, 0);
	if(text[DISPLAY_TEXT_NAME][0]){
		draw_text(0, 0, NAME_W, text[DISPLAY_TEXT_NAME], Font_11x18);
	} else {
		for(int i=0; i<4; i++){
			ssd1306_WriteChar((char)pString[i], Font_11x18, White);
		}
	}
	ssd1306_SetCursor(INFO_X, 6);
	if(text[DISPLAY_TEXT_INFO][0]){
		draw_text(INFO_X, 6, SCREEN_SHOWN_W - INFO_X, text[DISPLAY_TEXT_INFO], Font_7x10);
	} else {
		for(int i=0; i<8; i++){
			ssd1306_WriteChar((char)pString[4 + i], Font_7x10, White);
		}
	}
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

// The bank screen as it stands: a long text keeps its place in its scroll
// The bank screen into the buffer, without sending it
static void render_bank(uint8_t bankNumber){
	// Cleared first, so a refresh asked for while drawing is not lost
	refresh_pending = 0;
	if(bankNumber != current_bank) drop_bank_text();
	current_bank = bankNumber;
	uint8_t fresh = scroll_take_fresh();

	ssd1306_Fill(Black);
	draw_top(bankNumber, 0, NULL);
	scroll_start(fresh);

	for(uint8_t sw=0; sw<MIDI_NUM_SWITCHES; sw++){
		draw_cell(bankNumber, sw);
	}
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
	const uint8_t *pString = pBankStrings + (12 * preview_bank);
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
static void show_overlay(const char *msg){
	if(banner_running()) return;	// the banner is not cut short for a readout
	if(preview_bank != 0xFF) return;	// nor the bank being chosen
	if(moment_showing) moment_done();
	if(refresh_pending) render_bank(current_bank);	// a bank just entered, under the readout
	fill_rect(50, 6, SSD1306_WIDTH - 50, 10, Black);
	ssd1306_SetCursor(50, 6);
	ssd1306_WriteString((char *)msg, Font_7x10, White);
	ssd1306_UpdateScreen();

	overlay_until = HAL_GetTick() + OVERLAY_MS;
	refresh_pending = 0;
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
	overlay_until = HAL_GetTick() + OVERLAY_MS;
	refresh_pending = 0;
}

// Safe mode at power on, over the bank screen until it has been read
void display_show_safe_mode(void){
	banner_on = 0;
	drop_bank_text();
	ssd1306_Fill(Black);
	ssd1306_SetCursor(14, 8);
	ssd1306_WriteString("SAFE MODE", Font_11x18, White);
	ssd1306_SetCursor(22, 38);
	ssd1306_WriteString("NOTHING SENT", Font_7x10, White);
	ssd1306_UpdateScreen();

	overlay_until = HAL_GetTick() + SAFE_MODE_MS;
	refresh_pending = 0;
}

/*
 * A host text for a moment, drawn over the top line like the tempo readout.
 * A long one stays up until it has scrolled to its end.
 */
static void draw_moment_text(void){
	draw_top(current_bank, moment_place, moment_text);
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

void display_task(void){
	if(editor_on) return;	// the editor draws its own screen
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
		if(HAL_GetTick() < overlay_until || (moment_showing && scroll_state != SCROLL_IDLE)) return;
		overlay_until = 0;
		if(moment_showing) moment_done();
		refresh_pending = 1;
	}
	if(refresh_pending){
		draw_bank(current_bank);
	} else if(scroll_step()){
		draw_top(current_bank, 0, NULL);
		ssd1306_UpdateScreen();
	}
}
