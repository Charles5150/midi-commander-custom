/*
 * midi_cmds.h
 *
 *  Created on: Jul 6, 2021
 *      Author: D Harvie
 */

#ifndef INC_MIDI_CMDS_H_
#define INC_MIDI_CMDS_H_

#include <stdint.h>

#define ERROR_BUFFERS_FULL (-1)

//void sendMidiCC(uint8_t channel, uint8_t controller_number, uint8_t controller_value);

int8_t midiCmd_send_pc_command_from_rom(uint8_t *pRom);
int8_t midiCmd_send_cc_command_from_rom(uint8_t *pRom, uint8_t on_off);
int8_t midiCmd_send_cc(uint8_t channel, uint8_t cc_number, uint8_t value);
int8_t midiCmd_send_cc14(uint8_t channel, uint8_t cc_number, uint16_t value);
int8_t midiCmd_send_pb(uint8_t channel, uint16_t value);
int8_t midiCmd_send_note_command_from_rom(uint8_t *pRom, uint8_t on_off);
int8_t midiCmd_send_pb_command_from_rom(uint8_t *pRom, uint8_t on_off);
int8_t midiCmd_send_stop_command(void);
int8_t midiCmd_send_start_command(void);
int8_t midiCmd_send_clock_command(void);
int8_t midiCmd_send_song_select(uint8_t song);
int8_t midiCmd_send_song_position(uint16_t beats);
int8_t midiCmd_send_mmc(uint8_t command, uint16_t seconds);
int8_t midiCmd_send_panic(void);
void midiCmd_send_byte_serial(uint8_t byteMessage);
void midiCmd_send_bytes_serial(const uint8_t *data, uint8_t len);

void midiCmd_force_channel(uint8_t channel);	// 1-16 while a Chan command sends, 0 to stop forcing
uint8_t midiCmd_channel(uint8_t stored);	// the channel a command really goes out on
uint8_t midiCmd_get_cmd_toggle(uint8_t *pRom);
uint32_t midiCmd_get_delay(uint8_t *pRom);

#endif /* INC_MIDI_CMDS_H_ */
