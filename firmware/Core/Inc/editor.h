/*
 * editor.h
 *
 * Editing on the pedal: see editor.c.
 */

#ifndef INC_EDITOR_H_
#define INC_EDITOR_H_

#include <stdint.h>
#include <stdbool.h>

// How long both bank switches must be held to open or close the editor
#define EDITOR_HOLD_MS		(2000)

bool editor_is_open(void);
void editor_open(void);
void editor_close(void);
// A switch while the editor is open: 0-7 are the command switches, and
// SW_VIRTUAL_BANK_DOWN / SW_VIRTUAL_BANK_UP the bank ones
void editor_press(uint8_t sw, bool down);
// Repeats of a held +/- and the note let go after trying a command out
void editor_task(void);

#endif /* INC_EDITOR_H_ */
