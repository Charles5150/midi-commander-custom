/* usbd_midi.h for the simulator: the class's interface type, nothing else */
#ifndef SIM_USBD_MIDI_H
#define SIM_USBD_MIDI_H

#include "usbd_ioreq.h"

typedef struct _USBD_MIDI_ItfTypeDef{
  uint16_t (*pIf_MidiRx)    (uint8_t *msg, uint16_t length);
  uint16_t (*pIf_MidiTx)    (uint8_t *msg, uint16_t length);
}USBD_MIDI_ItfTypeDef;

#endif
