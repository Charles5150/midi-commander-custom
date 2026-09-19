/*
 * display.h
 *
 *  Created on: 8 Jul 2021
 *      Author: D Harvie
 */

#ifndef INC_DISPLAY_H_
#define INC_DISPLAY_H_

#include <stdint.h>

void display_init(void);
void display_setConfigName(void);

// Draw the bank name and the 2x4 grid of button labels for a bank
void display_setBankName(uint8_t bankNumber);
// A page of the bank: redraw as another bank, keeping what the computer wrote
void display_showPage(uint8_t bankNumber);

// Show the current tempo (and whether the clock runs) for a moment, then
// fall back to the bank screen.
void display_show_tempo(void);
// Briefly show a relative CC and the value it was just sent, e.g. "CC7=69"
void display_show_cc(uint8_t cc, uint8_t value);
// Full screen notice after switching configuration: its number and name
void display_show_config(uint8_t slot);
// A short message in the bank's info line, for a moment (8 characters fit)
void display_show_message(const char *msg);

/*
 * Text sent by the host over SysEx, called from the USB interrupt. place is
 * one of the DISPLAY_TEXT_ values, how one of the TEXT_KEEP_ ones. An empty
 * text takes that place back to what the bank shows. Returns 0 for a place or
 * how it does not know.
 */
#define DISPLAY_TEXT_INFO	(0)	// the small line right of the bank name, 11 chars
#define DISPLAY_TEXT_NAME	(1)	// the large bank name, 4 chars
#define DISPLAY_TEXT_LINE_LARGE	(2)	// the whole top line, 11 large chars
#define DISPLAY_TEXT_LINE_SMALL	(3)	// the whole top line, 18 small chars
#define DISPLAY_TEXT_PLACES	(4)
#define TEXT_KEEP_BANK		(0)	// until the bank changes
#define TEXT_KEEP_ALWAYS	(1)	// until the host changes it
#define TEXT_KEEP_MOMENT	(2)	// for a moment, like the tempo readout
uint8_t display_host_text(uint8_t place, uint8_t how, const uint8_t *text, uint8_t len);

// Ask for the current bank screen to be redrawn from the main loop
// (e.g. after a toggle state changed), without blocking the caller.
void display_request_refresh(void);
void display_task(void);

#endif /* INC_DISPLAY_H_ */
