/*
 * midi_map.c
 *
 * Turns a message a host sends into what the device on the DIN output wants:
 * another type, number, channel or value range, or a button's list, as the
 * active slot's MIDI map says (see MIDI_MAP_ in flash_midi_settings.h). It
 * runs in the USB interrupt, alongside the thru; a list is only asked for
 * here and runs in the main loop, like a bank change a host asks for.
 */

#include "midi_map.h"
#include "flash_midi_settings.h"
#include "switch_router.h"

// The value range [3]..[4] of an entry onto its [8]..[9], rounded
static uint8_t map_value(const uint8_t *e, uint8_t value){
	if(e[8] == MIDI_MAP_ANY && e[9] == MIDI_MAP_ANY) return value;
	int32_t span = (int32_t)e[4] - e[3];
	if(span <= 0) return e[8] & 0x7F;
	int32_t d = ((int32_t)value - e[3]) * ((int32_t)e[9] - e[8]);
	d += (d >= 0) ? span / 2 : -span / 2;
	return (uint8_t)((e[8] + d / span) & 0x7F);
}

bool midi_map_message(const uint8_t *data, void (*din)(const uint8_t *data, uint8_t len)){
	const uint8_t *map = flash_settings_midi_map();
	if(map == NULL || flash_settings_uploading()) return false;

	// What the entries compare: a Note Off is a Note On of velocity 0, and a
	// message with a single data byte has it as its number and its value
	uint8_t type = data[0] & 0xF0;
	uint8_t channel = (uint8_t)((data[0] & 0x0F) + 1);
	uint8_t number = data[1] & 0x7F;
	uint8_t value = data[2] & 0x7F;
	// A note's release reaches every entry for its note whatever their range,
	// so the entry its Note On matched lets go of the note it played
	bool release = false;
	switch(type){
	case 0x80: type = 0x90; value = 0; release = true; break;
	case 0x90: release = (value == 0); break;
	case 0xB0: break;
	case 0xC0: value = number; break;
	case 0xD0: value = number; number = 0; break;
	case 0xE0: number = 0; break;
	default: return false;
	}

	bool matched = false, keep = false;
	for(uint8_t n=0; n<MIDI_MAP_COUNT; n++){
		const uint8_t *e = map + n * MIDI_MAP_STRIDE;
		if(e[0] != type) continue;
		if(e[1] != 0 && e[1] != channel) continue;
		if(e[2] != MIDI_MAP_ANY && e[2] != number) continue;
		if(!release && (value < e[3] || value > e[4])) continue;
		matched = true;
		if(e[10] == MIDI_MAP_KEEP) keep = true;

		uint8_t out = map_value(e, value);
		// A release sends the bottom of the output range, not a scaled 0
		if(release && !(e[8] == MIDI_MAP_ANY && e[9] == MIDI_MAP_ANY)) out = e[8] & 0x7F;
		if(e[5] == MIDI_MAP_RUN){
			// Off for a release: a Note Off, or a CC or pedal below the middle
			sw_request_list(e[6], e[7], type == 0xC0 || value >= 64);
			continue;
		}
		uint8_t msg[3];
		msg[0] = (uint8_t)(e[5] | (((e[6] >= 1 && e[6] <= 16) ? e[6] : channel) - 1));
		msg[1] = (e[7] == MIDI_MAP_ANY) ? number : (e[7] & 0x7F);
		msg[2] = out;
		switch(e[5]){
		case 0x90:
			// A release comes out as a Note Off, whatever the output range
			if(release){ msg[0] = (uint8_t)(0x80 | (msg[0] & 0x0F)); msg[2] = 0x40; }
			din(msg, 3);
			break;
		case 0xB0:
			din(msg, 3);
			break;
		case 0xC0:
			// A program is chosen on the press, and the release sends nothing
			if(release) break;
			if(e[7] == MIDI_MAP_ANY) msg[1] = out;
			din(msg, 2);
			break;
		case 0xD0:
			msg[1] = out;
			din(msg, 2);
			break;
		case 0xE0:
			// A pitch bend kept as it came keeps its lower 7 bits too
			msg[1] = (type == 0xE0 && e[8] == MIDI_MAP_ANY && e[9] == MIDI_MAP_ANY) ? (data[1] & 0x7F) : 0;
			din(msg, 3);
			break;
		default:	// MIDI_MAP_NOTHING: only stops the message
			break;
		}
	}
	return matched && !keep;
}
