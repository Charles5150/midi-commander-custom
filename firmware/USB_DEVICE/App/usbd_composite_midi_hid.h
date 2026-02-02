/*
 * usbd_composite_midi_hid.h
 *
 *  Created on: Feb 3, 2026
 *      Author: Agent
 */

#ifndef __USBD_COMPOSITE_MIDI_HID_H
#define __USBD_COMPOSITE_MIDI_HID_H

#ifdef __cplusplus
 extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include  "usbd_ioreq.h"
#include  "usbd_midi.h"
#include  "usbd_hid_custom.h"

extern USBD_ClassTypeDef  USBD_COMPOSITE_MIDI_HID;
#define USBD_COMPOSITE_MIDI_HID_CLASS    &USBD_COMPOSITE_MIDI_HID

#ifdef __cplusplus
}
#endif

#endif /* __USBD_COMPOSITE_MIDI_HID_H */
