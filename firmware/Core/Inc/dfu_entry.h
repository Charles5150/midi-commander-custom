/*
 * dfu_entry.h
 *
 * Restarting in the stock bootloader's DFU mode on request from the computer,
 * so a firmware update needs no switches held at power on.
 */

#ifndef INC_DFU_ENTRY_H_
#define INC_DFU_ENTRY_H_

#include <stdbool.h>

// The firmware runs behind the stock bootloader, so there is one to go to
bool dfu_entry_possible(void);

// From the SysEx handler: restart in DFU once the answer has had time to leave
void dfu_entry_request(void);

// From the main loop: does the restart when one was asked for
void dfu_entry_task(void);

#endif /* INC_DFU_ENTRY_H_ */
