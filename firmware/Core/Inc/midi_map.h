/*
 * midi_map.h
 *
 * The MIDI map: messages arriving over USB turned into other messages on the
 * DIN output, or into a button's list (see MIDI_MAP_ in flash_midi_settings.h).
 */

#ifndef INC_MIDI_MAP_H_
#define INC_MIDI_MAP_H_

#include <stdbool.h>
#include <stdint.h>

// A channel message from the USB interrupt: every entry that matches it acts,
// sending what it makes through din(). True when the message itself must not
// go on through the USB thru.
bool midi_map_message(const uint8_t *data, void (*din)(const uint8_t *data, uint8_t len));

#endif /* INC_MIDI_MAP_H_ */
