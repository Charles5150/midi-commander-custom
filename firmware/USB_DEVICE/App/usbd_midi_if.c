/*
 *
 * EEPROM Routines taken in part form Github - nimaltd/ee24
 */

#include "usbd_midi_if.h"
#include "tempo.h"
#include "stm32f1xx_hal.h"
#include "midi_defines.h"
#include "flash_midi_settings.h"
#include "midi_cmds.h"
#include "expression.h"
#include "switch_router.h"
#include "leds.h"
#include "sleep.h"
#include "ssd1306.h"
#include "display.h"
#include "kemper.h"
#include <string.h>

extern I2C_HandleTypeDef hi2c1;


#define SYSEX_MAX_LENGTH 80	// the longest is the GET_STATE answer, 65 bytes
uint8_t sysex_rx_buffer[SYSEX_MAX_LENGTH];
uint8_t sysex_rx_counter = 0;
uint8_t sysex_tx_assembly_buffer[160];	// room for an 80 byte GET_SCREEN answer as USB MIDI events

uint8_t midi_msg_tx_buffer[SYSEX_MAX_LENGTH];

typedef struct {
	uint8_t start;
	uint8_t manuf_id;
	uint8_t msg_cmd;
	uint8_t start_parameters;

} MIDI_sysex_head_TypeDef;

USBD_MIDI_ItfTypeDef USBD_Interface_fops_FS =
{
  MIDI_DataRx,
  MIDI_DataTx
};

void abort_sysex_message(void){
	sysex_rx_counter = 0;
}

void sysex_send_message(uint8_t* buffer, uint8_t length){
	uint8_t *buff_ptr = buffer;
	uint8_t *assembly_ptr = sysex_tx_assembly_buffer;

	while(buff_ptr < length + buffer){
		uint8_t data_to_go = length + buffer - buff_ptr;

		if(data_to_go > 3){
			assembly_ptr[0] = CIN_SYSEX_STARTS_OR_CONTINUES;
			memcpy(assembly_ptr+1, buff_ptr, 3);
			buff_ptr += 3;
			assembly_ptr += 4;
		} else if (data_to_go == 3) {
			assembly_ptr[0] = CIN_SYSEX_ENDS_WITH_FOLLOWING_THREE_BYTES;
			memcpy(assembly_ptr+1, buff_ptr, 3);
			buff_ptr += 3;
			assembly_ptr += 4;
		} else if (data_to_go == 2) {
			assembly_ptr[0] = CIN_SYSEX_ENDS_WITH_FOLLOWING_TWO_BYTES;
			memcpy(assembly_ptr+1, buff_ptr, 2);
			buff_ptr += 2;
			assembly_ptr += 3;
			*assembly_ptr++ = 0xFF;
		} else if (data_to_go == 1) {
			assembly_ptr[0] = CIN_SYSEX_ENDS_WITH_FOLLOWING_SINGLE_BYTE;
			memcpy(assembly_ptr+1, buff_ptr, 1);
			buff_ptr += 1;
			assembly_ptr += 2;
			*assembly_ptr++ = 0xFF;
			*assembly_ptr++ = 0xFF;
		}
	}

	MIDI_DataTx(sysex_tx_assembly_buffer, assembly_ptr - sysex_tx_assembly_buffer);
}


void sysex_erase_settings(uint8_t* data_packet_start){
	if(data_packet_start[0] != 0x42 || data_packet_start[1] != 0x24){
		return;
	}

	flash_settings_erase();

	midi_msg_tx_buffer[0] = SYSEX_START;
	midi_msg_tx_buffer[1] = MIDI_MANUF_ID;
	midi_msg_tx_buffer[2] = SYSEX_RSP_ERASE_FLASH;
	midi_msg_tx_buffer[3] = SYSEX_END;
	sysex_send_message(midi_msg_tx_buffer, 4);
}

void sysex_write_flash(uint8_t* data_packet_start){
	uint32_t flash_byte_offset = ( (data_packet_start[0] << 7) | data_packet_start[1]) * 16;

	uint8_t reassembled_array[16];
	data_packet_start += 2;
	for (int i=0; i<16; i++){
		reassembled_array[i] = data_packet_start[2*i] << 4 | data_packet_start[2*i + 1];
	}

	flash_settings_write(reassembled_array, flash_byte_offset);

	midi_msg_tx_buffer[0] = SYSEX_START;
	midi_msg_tx_buffer[1] = MIDI_MANUF_ID;
	midi_msg_tx_buffer[2] = SYSEX_RSP_WRITE_FLASH;
	midi_msg_tx_buffer[3] = SYSEX_END;
	sysex_send_message(midi_msg_tx_buffer, 4);

}

/*
 * Read back one 16 byte chunk of the settings area. The request carries the
 * chunk address as two 7-bit bytes (high, low). The response echoes the
 * address and returns the 16 bytes as 32 nibbles so every byte stays 7-bit
 * clean, mirroring the WRITE_FLASH encoding.
 */
void sysex_read_flash(uint8_t* data_packet_start){
	uint32_t flash_byte_offset = ( (data_packet_start[0] << 7) | data_packet_start[1]) * 16;

	// The slot's pages, then its extension area (double press commands)
	const uint8_t *src = flash_settings_target_ptr(flash_byte_offset);
	if(src == NULL){
		return; // Out of range, ignore silently
	}
	uint8_t *p = midi_msg_tx_buffer;

	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_READ_FLASH;
	*(p++) = data_packet_start[0];
	*(p++) = data_packet_start[1];
	for (int i=0; i<16; i++){
		*(p++) = src[i] >> 4;
		*(p++) = src[i] & 0x0F;
	}
	*(p++) = SYSEX_END;

	sysex_send_message(midi_msg_tx_buffer, p - midi_msg_tx_buffer);
}

/*
 * Choose which configuration slot the following erase, write and read act on.
 * 0x7F (or any out of range value) changes nothing and only reports. The
 * answer carries the target slot, the active one and which slots hold a
 * configuration, so the tools can check before erasing anything.
 */
void sysex_select_slot(uint8_t* data_packet_start){
	uint8_t slot = data_packet_start[0];
	if(slot < CONFIG_SLOTS){
		flash_settings_set_target(slot);
	}
	uint8_t *p = midi_msg_tx_buffer;
	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_SELECT_SLOT;
	*(p++) = flash_settings_target_slot();
	*(p++) = flash_settings_active_slot();
	*(p++) = flash_settings_valid_mask() & 0x7F;
	// Since 0.26: flash size the chip reports (kB, two 7-bit bytes) and bit 0
	// set: this firmware stores double press commands
	uint16_t flash_kb = *(uint16_t*)FLASHSIZE_BASE;
	*(p++) = (flash_kb >> 7) & 0x7F;
	*(p++) = flash_kb & 0x7F;
	*(p++) = 1;
	*(p++) = SYSEX_END;
	sysex_send_message(midi_msg_tx_buffer, p - midi_msg_tx_buffer);
}

// Virtual pedal: press or release a switch as if by foot
void sysex_press_button(uint8_t* data_packet_start){
	uint8_t id = data_packet_start[0];
	uint8_t down = data_packet_start[1] ? 1 : 0;
	sw_virtual_press(id, down);

	uint8_t *p = midi_msg_tx_buffer;
	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_PRESS_BUTTON;
	*(p++) = id & 0x7F;
	*(p++) = down;
	*(p++) = SYSEX_END;
	sysex_send_message(midi_msg_tx_buffer, p - midi_msg_tx_buffer);
}

/*
 * What the pedal shows, for the configurator's virtual pedal: current bank and
 * slot, which toggle buttons are on, the bank's large name, the eight button
 * labels and the level of all ten LEDs (0-16), so blinking and dimmed LEDs show
 * as they really are, and last the eight stored values. 62 bytes in all.
 */
void sysex_get_state(void){
	uint8_t bank = sw_get_current_page();
	uint8_t toggles = 0;
	for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++){
		if(sw_button_is_toggle(bank, i) && sw_get_toggle_state(bank, i)){
			toggles |= (uint8_t)(1U << i);
		}
	}

	uint8_t *p = midi_msg_tx_buffer;
	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_GET_STATE;
	*(p++) = bank & 0x7F;
	*(p++) = flash_settings_active_slot() & 0x7F;
	*(p++) = toggles & 0x7F;
	*(p++) = (toggles >> 7) & 0x01;
	for(uint8_t k=0; k<4; k++){
		*(p++) = pBankStrings[bank * CFG_BANK_STRING_SIZE + k] & 0x7F;
	}
	for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++){
		const uint8_t *label = sw_button_label(bank, i);	// a cycle button's current state
		for(uint8_t k=0; k<BUTTON_LABEL_LEN; k++){
			*(p++) = label[k] & 0x7F;
		}
	}
	for(uint8_t led=0; led<LEDS_COUNT; led++){
		*(p++) = leds_get(led) & 0x7F;
	}
	uint16_t frame = ssd1306_GetFrameCount();
	*(p++) = frame & 0x7F;
	*(p++) = (frame >> 7) & 0x7F;
	*(p++) = sleep_is_asleep() ? 1 : 0;
	for(uint8_t v=0; v<VAR_COUNT; v++){
		*(p++) = sw_get_value(v) & 0x7F;	// the eight stored values
	}
	*(p++) = SYSEX_END;
	sysex_send_message(midi_msg_tx_buffer, p - midi_msg_tx_buffer);
}

/*
 * One sixteenth of the screen buffer, for the configurator's virtual pedal,
 * which shows the display exactly as the pedal draws it. The buffer holds one
 * byte per column for every 8 rows (SSD1306_WIDTH columns x 8 pages); part n
 * is the left (even n) or right (odd n) half of page n/2. The bytes are packed
 * 7 in 8: a byte carrying the high bits of up to 7 bytes, then their low 7 bits.
 */
#define SCREEN_PARTS		((SSD1306_HEIGHT / 8) * 2)
#define SCREEN_PART_BYTES	(SSD1306_WIDTH / 2)

void sysex_get_screen(uint8_t* data_packet_start){
	uint8_t part = data_packet_start[0];
	if(part >= SCREEN_PARTS){
		return;
	}
	const uint8_t *src = ssd1306_GetBuffer() + (part / 2) * SSD1306_WIDTH + (part % 2) * SCREEN_PART_BYTES;

	static uint8_t out[3 + 1 + (SCREEN_PART_BYTES * 8 + 6) / 7 + 1];
	uint8_t *p = out;
	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_GET_SCREEN;
	*(p++) = part;
	for(uint8_t i=0; i<SCREEN_PART_BYTES; i+=7){
		uint8_t n = (SCREEN_PART_BYTES - i < 7) ? (SCREEN_PART_BYTES - i) : 7;
		uint8_t *high = p++;
		*high = 0;
		for(uint8_t k=0; k<n; k++){
			if(src[i + k] & 0x80) *high |= (uint8_t)(1U << k);
			*(p++) = src[i + k] & 0x7F;
		}
	}
	*(p++) = SYSEX_END;
	sysex_send_message(out, p - out);
}

/*
 * Text from the host for the top line of the display: F0 7D 72 place how
 * text... F7. The text is everything between how and the end byte.
 */
void sysex_set_text(uint8_t* data_packet_start, uint8_t text_len){
	uint8_t place = data_packet_start[0];
	uint8_t how = data_packet_start[1];
	if(!display_host_text(place, how, data_packet_start + 2, text_len)){
		return;
	}

	uint8_t *p = midi_msg_tx_buffer;
	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_SET_TEXT;
	*(p++) = place;
	*(p++) = how;
	*(p++) = SYSEX_END;
	sysex_send_message(midi_msg_tx_buffer, p - midi_msg_tx_buffer);
}

void sysex_get_version(void){
	const char *version = FIRMWARE_VERSION;
	uint8_t *p = midi_msg_tx_buffer;

	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_GET_VERSION;
	while(*version && (p - midi_msg_tx_buffer) < (SYSEX_MAX_LENGTH - 1)){
		*(p++) = (uint8_t)(*version++) & 0x7F;
	}
	*(p++) = SYSEX_END;

	sysex_send_message(midi_msg_tx_buffer, p - midi_msg_tx_buffer);
}

// Live expression pedal readings, for the calibration tool in the GUI
void sysex_get_pedals(void){
	uint8_t *p = midi_msg_tx_buffer;
	*(p++) = SYSEX_START;
	*(p++) = MIDI_MANUF_ID;
	*(p++) = SYSEX_RSP_GET_PEDALS;
	for(uint8_t i=0; i<2; i++){
		uint16_t raw = expression_get_raw(i);
		*(p++) = (raw >> 7) & 0x7F;
		*(p++) = raw & 0x7F;
		*(p++) = expression_get_midi(i) & 0x7F;
	}
	*(p++) = SYSEX_END;
	sysex_send_message(midi_msg_tx_buffer, p - midi_msg_tx_buffer);
}

void process_sysex_message(void){
	// Check start and end bytes
	if(sysex_rx_buffer[0] != SYSEX_START ||
			sysex_rx_buffer[sysex_rx_counter -1] != SYSEX_END){
		abort_sysex_message();
		return;
	}

	MIDI_sysex_head_TypeDef *pSysexHead = (MIDI_sysex_head_TypeDef*)sysex_rx_buffer;

	if(pSysexHead->manuf_id != MIDI_MANUF_ID){
		abort_sysex_message();
		return;
	}

	switch(pSysexHead->msg_cmd){
	case SYSEX_CMD_ERASE_FLASH:
		sysex_erase_settings(&(pSysexHead->start_parameters));
		break;
	case SYSEX_CMD_WRITE_FLASH:
		// TODO: check data length
		sysex_write_flash(&(pSysexHead->start_parameters));
		break;
	case SYSEX_CMD_READ_FLASH:
		// F0 7D 56 hi lo F7 = 6 bytes minimum
		if(sysex_rx_counter >= 6){
			sysex_read_flash(&(pSysexHead->start_parameters));
		}
		break;
	case SYSEX_CMD_SELECT_SLOT:
		// F0 7D 64 slot F7 = 5 bytes
		if(sysex_rx_counter >= 5){
			sysex_select_slot(&(pSysexHead->start_parameters));
		}
		break;
	case SYSEX_CMD_PRESS_BUTTON:
		// F0 7D 66 id down F7 = 6 bytes
		if(sysex_rx_counter >= 6){
			sysex_press_button(&(pSysexHead->start_parameters));
		}
		break;
	case SYSEX_CMD_GET_STATE:
		sysex_get_state();
		break;
	case SYSEX_CMD_GET_SCREEN:
		// F0 7D 70 part F7 = 5 bytes
		if(sysex_rx_counter >= 5){
			sysex_get_screen(&(pSysexHead->start_parameters));
		}
		break;
	case SYSEX_CMD_SET_TEXT:
		// F0 7D 72 place how F7 = 6 bytes, then the text
		if(sysex_rx_counter >= 6){
			sysex_set_text(&(pSysexHead->start_parameters), sysex_rx_counter - 6);
		}
		break;
	case SYSEX_CMD_GET_VERSION:
		sysex_get_version();
		break;
	case SYSEX_CMD_GET_PEDALS:
		sysex_get_pedals();
		break;
	case SYSEX_CMD_RESET:
		NVIC_SystemReset();
		break;
	default:
		break;
	}

	sysex_rx_counter = 0;
}

/*
 * Number of MIDI bytes carried by a USB MIDI event, indexed by its Code
 * Index Number. Every event is 4 bytes on the wire (CIN/cable + up to 3
 * MIDI bytes, zero padded); this table says how many of those 3 are valid.
 */
static const uint8_t cin_data_length[16] = {
	0, 0, // 0x0, 0x1: reserved / cable events
	2,    // 0x2: two byte system common
	3,    // 0x3: three byte system common
	3,    // 0x4: SysEx starts or continues
	1,    // 0x5: single byte system common or SysEx end with one byte
	2,    // 0x6: SysEx end with two bytes
	3,    // 0x7: SysEx end with three bytes
	3, 3, 3, 3, // 0x8-0xB: note off, note on, poly pressure, control change
	2, 2, // 0xC, 0xD: program change, channel pressure
	3,    // 0xE: pitch bend
	1     // 0xF: single byte (realtime)
};

// Set while a SysEx from another manufacturer is passing through, so the
// remaining chunks are forwarded to DIN instead of accumulated.
static uint8_t sysex_foreign = 0;
// Set alongside sysex_foreign when the message must be dropped, not forwarded
// (our own SysEx that overflowed the receive buffer).
static uint8_t sysex_discard = 0;

static inline uint8_t usb_thru_enabled(void){
	return pGlobalSettings[GLOBAL_SETTINGS_USB_THRU] == 1;
}

/*
 * Bytes forwarded to DIN are collected per USB packet and handed to the
 * serial driver in one go, so a packet costs one transmit buffer instead of
 * one per event. A 64 byte packet carries at most 16 events x 3 bytes.
 */
static uint8_t thru_buf[48];
static uint8_t thru_len = 0;

static void thru_push(const uint8_t *data, uint8_t len){
	if(!usb_thru_enabled() || thru_len + len > sizeof(thru_buf)){
		return;
	}
	memcpy(thru_buf + thru_len, data, len);
	thru_len += len;
}

static void thru_flush(void){
	if(thru_len){
		midiCmd_send_bytes_serial(thru_buf, thru_len);
		thru_len = 0;
	}
}

/*
 * Optionally let an incoming Program Change or Control Change select a bank,
 * so a DAW or another pedal can drive this one. The bank switch itself is
 * deferred to the main loop; this runs in the USB interrupt.
 */
static void handle_bank_change_message(uint8_t cin, const uint8_t *data){
	uint8_t mode = pGlobalSettings[GLOBAL_SETTINGS_BANK_CHANGE_MODE];
	if(mode != BANK_CHANGE_PC && mode != BANK_CHANGE_CC) return;

	uint8_t want_channel = pGlobalSettings[GLOBAL_SETTINGS_BANK_CHANGE_CHANNEL];
	uint8_t channel = (data[0] & 0x0F) + 1;
	if(want_channel >= 1 && want_channel <= 16 && channel != want_channel) return;

	if(mode == BANK_CHANGE_PC && cin == CIN_PROGRAM_CHANGE){
		sw_request_bank(data[1] & 0x7F);
	} else if(mode == BANK_CHANGE_CC && cin == CIN_CONTROL_CHANGE){
		if((data[1] & 0x7F) == (pGlobalSettings[GLOBAL_SETTINGS_BANK_CHANGE_CC] & 0x7F)){
			sw_request_bank(data[2] & 0x7F);
		}
	}
}

/*
 * Remote press: a CC or a note in the range set by Remote_First presses one of
 * the ten switches, 1 2 3 4 A B C D, Bank Down, Bank Up, through the virtual
 * pedal, so the host drives the pedal's own logic, LEDs and display. A CC of
 * 64 or more, or a Note On, holds the switch down; a CC below 64, a Note Off
 * or a Note On with velocity 0 lets it go. A message used this way goes no
 * further: not to the DIN output, not to LED_Feedback nor bank selection.
 */
static bool handle_remote_message(uint8_t cin, const uint8_t *data){
	uint8_t mode = pGlobalSettings[GLOBAL_SETTINGS_REMOTE_MODE];
	bool down;
	if(mode == REMOTE_CC && cin == CIN_CONTROL_CHANGE){
		down = (data[2] & 0x7F) >= 64;
	} else if(mode == REMOTE_NOTE && cin == CIN_NOTE_ON){
		down = (data[2] & 0x7F) > 0;
	} else if(mode == REMOTE_NOTE && cin == CIN_NOTE_OFF){
		down = false;
	} else {
		return false;
	}

	uint8_t want_channel = pGlobalSettings[GLOBAL_SETTINGS_REMOTE_CHANNEL];
	uint8_t channel = (data[0] & 0x0F) + 1;
	if(want_channel >= 1 && want_channel <= 16 && channel != want_channel) return false;

	uint8_t first = pGlobalSettings[GLOBAL_SETTINGS_REMOTE_FIRST] & 0x7F;
	uint8_t number = data[1] & 0x7F;
	if(number < first || number - first >= SW_VIRTUAL_COUNT) return false;

	sw_virtual_press(number - first, down);
	return true;
}

static void handle_sysex_event(uint8_t cin, const uint8_t *data, uint8_t len){
	uint8_t is_end = (cin != CIN_SYSEX_STARTS_OR_CONTINUES);

	if(sysex_rx_counter == 0 && !sysex_foreign){
		// First chunk of a new message: F0 <manufacturer> ...
		// Anything not addressed to us is forwarded (if enabled) or dropped.
		if(len < 2 || data[0] != SYSEX_START || data[1] != MIDI_MANUF_ID){
			sysex_foreign = !is_end;
			kemper_sysex_chunk(data, len, is_end);	// the amp reporting itself
			thru_push(data, len);
			return;
		}
	}

	if(sysex_foreign){
		if(!sysex_discard){
			kemper_sysex_chunk(data, len, is_end);
			thru_push(data, len);
		}
		if(is_end){
			sysex_foreign = 0;
			sysex_discard = 0;
		}
		return;
	}

	// Our own message: accumulate, guarding the buffer
	if(sysex_rx_counter + len > SYSEX_MAX_LENGTH){
		abort_sysex_message();
		// Swallow the rest of this message without forwarding it
		sysex_foreign = !is_end;
		sysex_discard = !is_end;
		return;
	}
	memcpy(sysex_rx_buffer + sysex_rx_counter, data, len);
	sysex_rx_counter += len;

	if(is_end){
		process_sysex_message();
	}
}

uint16_t MIDI_DataRx(uint8_t *msg, uint16_t length)
{
	// Walk the packet one 4 byte USB MIDI event at a time
	for(uint16_t i = 0; i + 4 <= length; i += 4){
		uint8_t cin = msg[i] & 0x0F;
		const uint8_t *data = msg + i + 1;
		uint8_t len = cin_data_length[cin];

		switch(cin){
		case CIN_SYSEX_STARTS_OR_CONTINUES:
		case CIN_SYSEX_ENDS_WITH_FOLLOWING_TWO_BYTES:
		case CIN_SYSEX_ENDS_WITH_FOLLOWING_THREE_BYTES:
			handle_sysex_event(cin, data, len);
			break;

		case CIN_SYSEX_ENDS_WITH_FOLLOWING_SINGLE_BYTE:
			// Also used for single byte system common (e.g. F6 tune request)
			if(sysex_rx_counter != 0 || sysex_foreign || data[0] == SYSEX_END){
				handle_sysex_event(cin, data, len);
			} else {
				thru_push(data, len);
			}
			break;

		case CIN_SINGLE_BYTE:
			// Measure the host's clock when following it (Clock_Follow)
			if(data[0] == 0xF8){
				tempo_external_clock();
			} else if(data[0] == 0xFA || data[0] == 0xFB){
				tempo_external_transport(data[0]);
			}
			// Realtime messages. Clock/Start/Continue/Stop pass when enabled.
			if(pGlobalSettings[GLOBAL_SETTINGS_REALTIME_PASS]){
				uint8_t b = data[0];
				if(b == 0xF8 || b == 0xFA || b == 0xFB || b == 0xFC){
					midiCmd_send_byte_serial(b);
				}
			}
			break;

		case CIN_PROGRAM_CHANGE:
		case CIN_CONTROL_CHANGE:
			if(handle_remote_message(cin, data)) break;
			// May select a bank before being forwarded to the DIN output
			handle_bank_change_message(cin, data);
			if(cin == CIN_CONTROL_CHANGE){
				sw_feedback_message(data);
			} else {
				sw_note_program(data[0], data[1]);	// next / previous preset follow the host
			}
			thru_push(data, len);
			break;

		case CIN_NOTE_OFF:
		case CIN_NOTE_ON:
			if(handle_remote_message(cin, data)) break;
			// May set the LED of a toggle button that sends this note
			sw_feedback_message(data);
			thru_push(data, len);
			break;

		case CIN_TWO_BYTE_SYSTEM_COMMON:
		case CIN_THREE_BYTE_SYSTEM_COMMON:
		case CIN_POLY_KEYPRESS:
		case CIN_CHANNEL_PRESSURE:
		case CIN_PITCHBEND_CHANGE:
			thru_push(data, len);
			break;

		default:
			// Reserved CINs or padding
			break;
		}
	}

	thru_flush();
	return 0;
}

uint16_t MIDI_DataTx(uint8_t *msg, uint16_t length)
{
  USBD_MIDI_SendPacket(msg, length);
  return USBD_OK;
}
