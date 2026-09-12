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

// Ask for the current bank screen to be redrawn from the main loop
// (e.g. after a toggle state changed), without blocking the caller.
void display_request_refresh(void);
void display_task(void);

#endif /* INC_DISPLAY_H_ */
