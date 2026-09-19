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
 */
#include "main.h"
#include "flash_midi_settings.h"
#include "switch_router.h"
#include "display.h"
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

static volatile uint8_t refresh_pending = 0;
static uint8_t current_bank = 0;

// A transient overlay (the tempo readout) shown instead of the bank info
#define OVERLAY_MS	(1500)
static uint32_t overlay_until = 0;

/*
 * Host text, one per place; an empty string means the bank's own text. Written
 * from the USB interrupt, drawn from the main loop: a torn string is redrawn
 * right away, since every write asks for a refresh.
 */
#define HOST_TEXT_MAX	(18)
static const uint8_t host_text_max[DISPLAY_TEXT_PLACES] = {11, 4, 11, 18};
static char host_text[DISPLAY_TEXT_PLACES][HOST_TEXT_MAX + 1];
static uint8_t host_keep[DISPLAY_TEXT_PLACES];
// A text shown for a moment only, waiting for the main loop to draw it
static char moment_text[HOST_TEXT_MAX + 1];
static uint8_t moment_place = 0;
static volatile uint8_t moment_pending = 0;

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

void display_setConfigName(void){
    ssd1306_SetCursor(10, 34);
    for(int i=0; i<16; i++){
    	ssd1306_WriteChar(pGlobalSettings[16+i], Font_7x10, White);
    }
    ssd1306_UpdateScreen();
}

static void fill_rect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, SSD1306_COLOR color){
	for(uint8_t j=0; j<h; j++){
		for(uint8_t i=0; i<w; i++){
			ssd1306_DrawPixel(x+i, y+j, color);
		}
	}
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

	if(text[DISPLAY_TEXT_LINE_LARGE][0]){
		ssd1306_SetCursor(0, 0);
		ssd1306_WriteString((char *)text[DISPLAY_TEXT_LINE_LARGE], Font_11x18, White);
		return;
	}
	if(text[DISPLAY_TEXT_LINE_SMALL][0]){
		ssd1306_SetCursor(0, 6);
		ssd1306_WriteString((char *)text[DISPLAY_TEXT_LINE_SMALL], Font_7x10, White);
		return;
	}

	// Bank name, large 4 chars then small 8 chars on the same line
	ssd1306_SetCursor(0, 0);
	if(text[DISPLAY_TEXT_NAME][0]){
		ssd1306_WriteString((char *)text[DISPLAY_TEXT_NAME], Font_11x18, White);
	} else {
		for(int i=0; i<4; i++){
			ssd1306_WriteChar((char)pString[i], Font_11x18, White);
		}
	}
	ssd1306_SetCursor(50, 6);
	if(text[DISPLAY_TEXT_INFO][0]){
		ssd1306_WriteString((char *)text[DISPLAY_TEXT_INFO], Font_7x10, White);
	} else {
		for(int i=0; i<8; i++){
			ssd1306_WriteChar((char)pString[4 + i], Font_7x10, White);
		}
	}
}

void display_showPage(uint8_t bankNumber){
	current_bank = bankNumber;	// same bank for the song: nothing is dropped
	display_setBankName(bankNumber);
}

void display_setBankName(uint8_t bankNumber){
	// Cleared first, so a refresh asked for while drawing is not lost
	refresh_pending = 0;
	if(bankNumber != current_bank) drop_bank_text();
	current_bank = bankNumber;

	ssd1306_Fill(Black);
	draw_top(bankNumber, 0, NULL);

	for(uint8_t sw=0; sw<MIDI_NUM_SWITCHES; sw++){
		draw_cell(bankNumber, sw);
	}

	ssd1306_UpdateScreen();
}

uint8_t display_host_text(uint8_t place, uint8_t how, const uint8_t *text, uint8_t len){
	if(place >= DISPLAY_TEXT_PLACES || how > TEXT_KEEP_MOMENT) return 0;

	char *dst = (how == TEXT_KEEP_MOMENT) ? moment_text : host_text[place];
	if(len > host_text_max[place]) len = host_text_max[place];
	for(uint8_t i=0; i<len; i++){
		char c = (char)text[i];
		dst[i] = (c < 0x20 || c > 0x7E) ? ' ' : c;
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
 * Replace the bank's info line with "120 BPM" (and a * while the clock is
 * running) for a moment. Only that line is redrawn, so the bank name and the
 * button grid stay put.
 */
/*
 * Replace the bank's info line with a short message for OVERLAY_MS. Only that
 * line is redrawn, so the bank name and the button grid stay put.
 */
static void show_overlay(const char *msg){
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

// A host text for a moment, drawn over the top line like the tempo readout
static void show_moment_text(void){
	moment_pending = 0;
	draw_top(current_bank, moment_place, moment_text);
	ssd1306_UpdateScreen();
	overlay_until = HAL_GetTick() + OVERLAY_MS;
}

void display_task(void){
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
		if(HAL_GetTick() < overlay_until) return;
		overlay_until = 0;
		refresh_pending = 1;
	}
	if(refresh_pending){
		display_setBankName(current_bank);
	}
}
