/*
 * midi_cmds.c
 *
 *  Created on: Jul 6, 2021
 *      Author: D Harvie
 */
#include "midi_cmds.h"
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "usbd_midi_if.h"
#include "ssd1306.h"

extern UART_HandleTypeDef huart2;

/*
 * The DIN output.
 *
 * The serial port sends a byte every 0.32 ms, far slower than the pedal can
 * make them, so what goes out waits here: a ring of bytes handed to the DMA a
 * few at a time. A message goes in whole or not at all. Only a full ring, some
 * 600 messages waiting at once, drops anything, and then on DIN alone: USB
 * never waits for the slow port. Before 1.03 each message took a buffer of its
 * own, 32 of them, and a bank sending a few commands on sixteen channels lost
 * all but the first 32 messages, on USB too.
 *
 * The transfers are short so that the MIDI Clock, which may go out between any
 * two bytes, jumps the queue and never waits behind a long list for more than
 * a millisecond. Start, Continue and Stop keep their place, since a Song
 * Select sent before a Start must arrive first; while one of them waits, the
 * clocks queue behind it, or a device would count them before it starts.
 */
#define DIN_RING_SIZE	(2048)	// a power of two
#define DIN_CHUNK	(3)	// bytes per transfer: a clock waits one chunk at most
#define DIN_CLOCKS_MAX	(8)

static uint8_t din_ring[DIN_RING_SIZE];
static volatile uint32_t din_in = 0;	// bytes ever queued
static volatile uint32_t din_out = 0;	// bytes ever sent
static uint16_t din_busy = 0;		// ring bytes in the transfer running, 0 for a clock
static uint32_t din_transport_end = 0;	// din_in just after the last Start, Continue or Stop
static volatile uint8_t din_clocks = 0;	// clocks waiting to jump the queue
static uint8_t din_clock_byte = 0xF8;	// in RAM, where the DMA reads it

static bool din_transport_waiting(void){
	return (int32_t)(din_transport_end - din_out) > 0;
}

/*
 * Start the next transfer to the DIN output, if the UART is free. Called when
 * something is queued, from the main loop or the USB interrupt (MIDI passed
 * through to DIN), and from the end of the last transfer, so it decides and
 * starts with interrupts off: before 0.65 it spun until HAL_UART_Transmit_DMA
 * gave in, and an interrupt landing while the main loop was inside that call
 * spun for ever on the lock the main loop held, hanging the pedal. A busy
 * UART is simply left alone: its end of transfer starts the next one.
 */
static void din_start(void){
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	if(huart2.gState == HAL_UART_STATE_READY){
		if(din_clocks){
			if(HAL_UART_Transmit_DMA(&huart2, &din_clock_byte, 1) == HAL_OK){
				din_clocks--;
				din_busy = 0;
			}
		} else if(din_in != din_out){
			uint32_t at = din_out % DIN_RING_SIZE;
			uint32_t n = din_in - din_out;
			if(n > DIN_CHUNK) n = DIN_CHUNK;
			if(n > DIN_RING_SIZE - at) n = DIN_RING_SIZE - at;
			if(HAL_UART_Transmit_DMA(&huart2, &din_ring[at], (uint16_t)n) == HAL_OK){
				din_busy = (uint16_t)n;
			}
		}
	}
	if(!primask) __enable_irq();
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
	if(huart->Instance == huart2.Instance){
		din_out += din_busy;
		din_busy = 0;
		din_start();
	}
}

// A whole message into the queue, or nothing if it does not fit
static bool din_put(const uint8_t *data, uint32_t len){
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	bool fits = len <= DIN_RING_SIZE - (din_in - din_out);
	if(fits){
		for(uint32_t i = 0; i < len; i++){
			din_ring[(din_in + i) % DIN_RING_SIZE] = data[i];
			if(data[i] == 0xFA || data[i] == 0xFB || data[i] == 0xFC){
				din_transport_end = din_in + i + 1;
			}
		}
		din_in += len;
	}
	if(!primask) __enable_irq();
	din_start();
	return fits;
}

// A MIDI Clock: ahead of everything, unless a Start or a Stop is waiting
static void din_clock(void){
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	if(din_transport_waiting()){
		din_put(&din_clock_byte, 1);
	} else if(din_clocks < DIN_CLOCKS_MAX){
		din_clocks++;
	}
	if(!primask) __enable_irq();
	din_start();
}

/*
 * Which channel a message really goes out on.
 *
 * A command stores its own channel, but two things can move it. The global
 * channel setting takes every message in the configuration to one channel, so
 * a whole rig moves with one number. A Chan command names channels on purpose
 * for the command below it, and while it is sending, that channel wins over
 * everything: it is how one command reaches several devices, and how a command
 * stays where it is when the rest of the configuration moves.
 */
static uint8_t forced_channel = 0;	// 1-16 while a Chan command is sending

void midiCmd_force_channel(uint8_t channel){
	forced_channel = (channel <= 16) ? channel : 0;
}

uint8_t midiCmd_forced_channel(void){
	return forced_channel;
}

uint8_t midiCmd_channel(uint8_t stored){
	if(forced_channel) return (uint8_t)(forced_channel - 1) & 0x0F;
	uint8_t global = pGlobalSettings[GLOBAL_SETTINGS_GLOBAL_CHANNEL];
	if(global >= 1 && global <= 16) return (uint8_t)(global - 1) & 0x0F;
	return stored & 0x0F;
}

/*
 * Which outputs a message goes out on. Everything goes to USB and to the DIN
 * port alike, unless a Chan command above the command sending it turns one of
 * them off: CHAN_NO_USB or CHAN_NO_DIN, set only while that command sends. A
 * PC for the amp on DIN then does not also reach the computer, and a note for
 * the computer does not reach the amp. Messages coming in over USB and passed
 * through to DIN, and the MIDI clock, go out as ever.
 */
static uint8_t outputs_off = 0;

void midiCmd_limit_outputs(uint8_t off){
	outputs_off = off & (CHAN_NO_USB | CHAN_NO_DIN);
}

uint8_t midiCmd_outputs_off(void){
	return outputs_off;
}

static void usb_tx(uint8_t *msg, uint16_t len){
	if(!(outputs_off & CHAN_NO_USB)) MIDI_DataTx(msg, len);
}

static int8_t din_bytes(const uint8_t *data, uint8_t len){
	if(outputs_off & CHAN_NO_DIN) return 0;
	return din_put(data, len) ? 0 : ERROR_BUFFERS_FULL;
}

/*
 * USB events, four bytes each, to USB and their MIDI bytes to DIN, each output
 * if it is on. Returns ERROR_BUFFERS_FULL when DIN had no room for them; USB
 * has them all the same.
 */
static int8_t send_events(uint8_t *events, uint8_t len){
	uint8_t din[3 * 16], n = 0;
	usb_tx(events, len);
	for(uint8_t i = 0; i + 3 < len; i += 4){
		uint8_t cin = events[i] & 0x0F;
		uint8_t k = (cin == CIN_PROGRAM_CHANGE || cin == CIN_CHANNEL_PRESSURE) ? 2
				: (cin == CIN_SINGLE_BYTE) ? 1 : 3;
		memcpy(&din[n], &events[i + 1], k);
		n += k;
	}
	return din_bytes(din, n);
}

// A whole SysEx message, F0 to F7, to the outputs that are on
void midiCmd_send_sysex(uint8_t *msg, uint8_t len){
	if(!(outputs_off & CHAN_NO_USB)) sysex_send_message(msg, len);
	din_bytes(msg, len);
}

uint8_t midiCmd_get_cmd_toggle(uint8_t *pRom){
// Toggle state is always stored in the most significant bit of the second cmd byte
// EXCEPT for KEY commands where we use byte 4 (index 3)
	uint8_t t = *pRom & 0xF0;
	if(t == CMD_KEY_NIBBLE || t == CMD_MEDIA_NIBBLE) return *(pRom+3) & 0x80;
	return *(pRom+1) & 0x80;
}

/*
 * Returns the delay time to note or pitch bend off in ms
 */
uint32_t midiCmd_get_delay(uint8_t *pRom){
	return (uint32_t)*(pRom+3) * 10;
}

/*
 * Send raw bytes just through to the serial midi port, without touching USB,
 * whatever outputs a Chan command left on: messages received over USB and
 * forwarded to the DIN output, and the clock. Silently drops a message the
 * queue has no room for.
 */
void midiCmd_send_bytes_serial(const uint8_t *data, uint8_t len){
	if(len == 0) return;
	if(len == 1 && data[0] == 0xF8) din_clock();
	else din_put(data, len);
}

void midiCmd_send_byte_serial(uint8_t byteMessage){
	midiCmd_send_bytes_serial(&byteMessage, 1);
}

// A single byte message, Start or Stop, to both outputs
static int8_t send_realtime(uint8_t b){
	uint8_t usb[4] = { CIN_SINGLE_BYTE, b, 0, 0 };
	return send_events(usb, 4);
}

int8_t midiCmd_send_start_command(void){
	return send_realtime(0xFA);
}

int8_t midiCmd_send_stop_command(void){
	return send_realtime(0xFC);
}

/*
 * A MIDI Clock byte (0xF8) to both USB and the DIN output, whatever else is
 * waiting for the DIN output.
 */
int8_t midiCmd_send_clock_command(void){
	uint8_t usb[4] = { CIN_SINGLE_BYTE, 0xF8, 0, 0 };
	MIDI_DataTx(usb, 4);
	din_clock();
	return 0;
}

/*
 * Panic: All Sound Off (CC 120) and All Notes Off (CC 123) on all sixteen
 * channels, to USB and the DIN output, as two full USB packets.
 */
int8_t midiCmd_send_panic(void){
	static const uint8_t ccs[2] = { 120, 123 };
	for(uint8_t half = 0; half < 2; half++){
		uint8_t usb[64];
		for(uint8_t ch = 0; ch < 16; ch++){
			uint8_t *u = &usb[ch * 4];
			u[0] = CIN_CONTROL_CHANGE;
			u[1] = 0xB0 | ch;
			u[2] = ccs[half];
			u[3] = 0;
		}
		send_events(usb, sizeof(usb));
	}
	return 0;
}

/*
 * Song Select (F3) and Song Position Pointer (F2), to USB and the DIN output.
 * Neither belongs to a channel: they tell a sequencer or a recorder which song
 * to play and where in it to start.
 */
int8_t midiCmd_send_song_select(uint8_t song){
	uint8_t usb[4] = { CIN_TWO_BYTE_SYSTEM_COMMON, 0xF3, song & 0x7F, 0 };
	usb_tx(usb, 4);
	return din_bytes(&usb[1], 2);
}

int8_t midiCmd_send_song_position(uint16_t beats){
	uint8_t usb[4] = { CIN_THREE_BYTE_SYSTEM_COMMON, 0xF2,
			beats & 0x7F, (beats >> 7) & 0x7F };
	return send_events(usb, 4);
}

/*
 * MIDI Machine Control, addressed to every device: F0 7F 7F 06 <command> F7.
 * Locate also carries where to go, as a timecode of hours, minutes, seconds
 * and frames: F0 7F 7F 06 44 06 01 hh mm ss ff sf F7. The position arrives
 * here in seconds, so the frames are always 0 and the timecode type 24 fps,
 * which is the two top bits of the hours byte left at zero.
 */
int8_t midiCmd_send_mmc(uint8_t command, uint16_t seconds){
	uint8_t msg[13];
	uint8_t len = 0;

	msg[len++] = SYSEX_START;
	msg[len++] = 0x7F;	// real time
	msg[len++] = 0x7F;	// every device
	msg[len++] = 0x06;	// MMC command
	msg[len++] = command & 0x7F;
	if(command == MMC_LOCATE){
		msg[len++] = 0x06;	// the locate sub-command carries six bytes
		msg[len++] = 0x01;	// and goes to a timecode
		msg[len++] = (seconds / 3600) & 0x1F;
		msg[len++] = (seconds / 60) % 60;
		msg[len++] = seconds % 60;
		msg[len++] = 0;		// frames
		msg[len++] = 0;		// subframes
	}
	msg[len++] = SYSEX_END;

	midiCmd_send_sysex(msg, len);
	return 0;
}

// One channel message: its USB code, status, and the one or two data bytes
static int8_t send_message(uint8_t cin, uint8_t status, uint8_t d1, uint8_t d2){
	uint8_t usb[4] = { cin, status, d1 & 0x7F, d2 & 0x7F };
	return send_events(usb, 4);
}

int8_t midiCmd_send_pb_command_from_rom(uint8_t *pRom, uint8_t on_off){
	return send_message(CIN_PITCHBEND_CHANGE, 0xE0 | midiCmd_channel(pRom[0]),
			on_off ? pRom[1] : 0, on_off ? pRom[2] : (0x2000 >> 7));
}

int8_t midiCmd_send_note_command_from_rom(uint8_t *pRom, uint8_t on_off){
	return send_message(on_off ? CIN_NOTE_ON : CIN_NOTE_OFF,
			(on_off ? 0x90 : 0x80) | midiCmd_channel(pRom[0]),
			pRom[1], on_off ? pRom[2] : 0);
}

int8_t midiCmd_send_cc(uint8_t channel, uint8_t cc_number, uint8_t value)
{
	return send_message(CIN_CONTROL_CHANGE, 0xB0 | midiCmd_channel(channel), cc_number, value);
}

/*
 * Several Control Changes on one channel in one go, so the run is never
 * split: `pairs` holds each one's number and value, up to six of them.
 */
static int8_t send_cc_run(uint8_t channel, const uint8_t *pairs, uint8_t n)
{
	uint8_t usb[4 * 6];
	for(uint8_t k = 0; k < n; k++){
		usb[4 * k] = CIN_CONTROL_CHANGE;
		usb[4 * k + 1] = 0xB0 | midiCmd_channel(channel);
		usb[4 * k + 2] = pairs[2 * k] & 0x7F;
		usb[4 * k + 3] = pairs[2 * k + 1] & 0x7F;
	}
	return send_events(usb, (uint8_t)(4 * n));
}

/*
 * A 14-bit CC: the MSB on cc_number and the LSB on cc_number + 32, in one
 * go so the pair is never split. cc_number must be below 32.
 */
int8_t midiCmd_send_cc14(uint8_t channel, uint8_t cc_number, uint16_t value)
{
	uint8_t pairs[4] = {cc_number & 0x1F, (value >> 7) & 0x7F, (cc_number & 0x1F) + 32, value & 0x7F};
	return send_cc_run(channel, pairs, 2);
}

/*
 * An NRPN or RPN, as the Param command `param` names it (see CMD_PARAM_MODE):
 * the parameter, the value on Data Entry, its low half too when fine, and the
 * null RPN after it.
 */
int8_t midiCmd_send_param(uint8_t channel, const uint8_t *param, uint8_t value)
{
	uint8_t kind = PARAM_KIND(param);
	uint8_t lsb = (kind & PARAM_RPN) ? 100 : 98;	// the MSB's number is one above
	uint8_t pairs[12], *p = pairs;
	*p++ = lsb + 1; *p++ = param[3];
	*p++ = lsb;     *p++ = param[2];
	*p++ = 6;       *p++ = value;
	if(kind & PARAM_FINE){
		*p++ = 38;  *p++ = value;
	}
	*p++ = 101;     *p++ = 127;
	*p++ = 100;     *p++ = 127;
	return send_cc_run(channel, pairs, (uint8_t)((p - pairs) / 2));
}

// Channel Pressure (aftertouch for the whole channel)
int8_t midiCmd_send_pressure(uint8_t channel, uint8_t value)
{
	return send_message(CIN_CHANNEL_PRESSURE, 0xD0 | midiCmd_channel(channel), value, 0);
}

// Pitch Bend, value 0-16383 with 8192 in the middle
int8_t midiCmd_send_pb(uint8_t channel, uint16_t value)
{
	uint8_t rom[3] = {channel & 0xF, value & 0x7F, (value >> 7) & 0x7F};
	return midiCmd_send_pb_command_from_rom(rom, 1);
}

int8_t midiCmd_send_cc_command_from_rom(uint8_t *pRom, uint8_t on_off){
	// Check switch off value is valid, else no off value will be sent
	if(!on_off){
		if(pRom[3] > 0x7F)
			return 0;
	}
	return send_message(CIN_CONTROL_CHANGE, 0xB0 | midiCmd_channel(pRom[0]),
			pRom[1], on_off ? pRom[2] : pRom[3]);
}

int8_t midiCmd_send_pc_command_from_rom(uint8_t *pRom){
	uint8_t usb[12], *u = usb;
	uint8_t channel = midiCmd_channel(pRom[0]);

	/*
	 * Bank select messages must be transmitted first, as
	 * the actual program change is only executed on the PC
	 * message.
	 */
	if(pRom[2] < 0x80){ // Bank Select MSB
		*u++ = CIN_CONTROL_CHANGE;
		*u++ = 0xB0 | channel;
		*u++ = MIDI_PC_BANK_SELECT_MSB;
		*u++ = pRom[2];
	}

	if(pRom[3] < 0x80){ // Bank Select LSB
		*u++ = CIN_CONTROL_CHANGE;
		*u++ = 0xB0 | channel;
		*u++ = MIDI_PC_BANK_SELECT_LSB;
		*u++ = pRom[3];
	}

	// The program change message
	*u++ = CIN_PROGRAM_CHANGE;
	*u++ = 0xC0 | channel;
	*u++ = pRom[1] & 0x7F;
	*u++ = 0; // must pad USB packets to 32b

	return send_events(usb, (uint8_t)(u - usb));
}
