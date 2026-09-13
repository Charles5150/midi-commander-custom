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
 */
#include "main.h"
#include "flash_midi_settings.h"
#include "switch_router.h"
#include "display.h"
#include <string.h>
#include <stdio.h>
#include "ssd1306.h"
#include "tempo.h"

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
	const uint8_t *src = pButtonLabels + (bank * MIDI_NUM_SWITCHES + sw) * BUTTON_LABEL_LEN;
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

void display_setBankName(uint8_t bankNumber){
	current_bank = bankNumber;
	uint8_t *pString = pBankStrings + (12 * bankNumber);

	ssd1306_Fill(Black);

	// Bank name, large 4 chars then small 8 chars on the same line
	ssd1306_SetCursor(0, 0);
	for(int i=0; i<4; i++){
		ssd1306_WriteChar((char)*pString++, Font_11x18, White);
	}
	ssd1306_SetCursor(50, 6);
	for(int i=0; i<8; i++){
		ssd1306_WriteChar((char)*pString++, Font_7x10, White);
	}

	for(uint8_t sw=0; sw<MIDI_NUM_SWITCHES; sw++){
		draw_cell(bankNumber, sw);
	}

	ssd1306_UpdateScreen();
	refresh_pending = 0;
}

void display_request_refresh(void){
	refresh_pending = 1;
}

/*
 * Replace the bank's info line with "120 BPM" (and a * while the clock is
 * running) for a moment. Only that line is redrawn, so the bank name and the
 * button grid stay put.
 */
void display_show_tempo(void){
	char msg[13];
	if(tempo_external_present()){
		// Following the host: fits the 8 character info line
		snprintf(msg, sizeof(msg), "%sEXT %u", tempo_clock_running() ? "*" : "", tempo_get_bpm());
	} else {
		snprintf(msg, sizeof(msg), "%s%u BPM", tempo_clock_running() ? "*" : "", tempo_get_bpm());
	}

	fill_rect(50, 6, SSD1306_WIDTH - 50, 10, Black);
	ssd1306_SetCursor(50, 6);
	ssd1306_WriteString(msg, Font_7x10, White);
	ssd1306_UpdateScreen();

	overlay_until = HAL_GetTick() + OVERLAY_MS;
	refresh_pending = 0;
}

void display_task(void){
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
