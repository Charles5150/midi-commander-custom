/*
 * gt1000.c
 *
 * Two way talk with a Boss GT-1000 or GT-1000CORE. Roland units are read and
 * written as one big address space, in System Exclusive messages of their own:
 *
 *	F0 41 <device> 00 00 00 4F <command> <address, four bytes> ... <sum> F7
 *
 * RQ1 (11) asks for a stretch of it, an address and a size, and the unit
 * answers with DT1 (12), the address and the bytes found there. Every byte of
 * an address and of a size carries seven bits only. The sum makes what follows
 * the command, data and all, a multiple of 128.
 *
 * The pedal asks for three things. The patch number, every second, which is
 * how it notices a patch change however it was made. The patch name, which
 * goes on the display. And the patch's sixteen ASSIGNs, which are where the
 * unit is told what a Control Change coming in does: an ASSIGN whose source is
 * a CC and whose target switches an effect on and off says which CC switches
 * which effect, and that is what lights the buttons. The switches of those
 * effects are then asked for, and each one is handed to the LED feedback as
 * that CC, on or off, so any button sending it ends up lit or dark like the
 * unit. Nothing is sent to the unit because of what it reports.
 *
 * The pedal also writes 1 to 7F 00 00 01, which no Roland document mentions
 * but which makes the unit report what is changed on it the moment it is
 * changed, as its editor needs; without it the pedal still catches up within
 * a second.
 *
 * The answers come in over USB, so the unit's USB and the pedal's have to meet
 * on something that is a host to both: a computer, or a USB MIDI host box.
 * What the pedal asks goes out on DIN as well.
 */

#include "gt1000.h"
#include "midi_defines.h"
#include "flash_midi_settings.h"
#include "switch_router.h"
#include "display.h"
#include "midi_cmds.h"
#include "usbd_midi_if.h"
#include "stm32f1xx_hal.h"
#include <string.h>

// --- the unit's own dialect --------------------------------------------------
#define GT_MANUF		(0x41)	// Roland
#define GT_DEVICE		(0x7F)	// whoever is listening; the unit answers with its own
#define GT_MODEL_1		(0x00)
#define GT_MODEL_2		(0x00)
#define GT_MODEL_3		(0x00)
#define GT_MODEL_4		(0x4F)	// GT-1000 and GT-1000CORE alike
#define GT_HEAD_LEN		(8)	// F0, the maker, the device, the model and the command
#define GT_CMD_RQ1		(0x11)	// ask for a stretch of the address space
#define GT_CMD_DT1		(0x12)	// a stretch of it, asked for or reported

/*
 * Addresses written as their four bytes, as Roland's tables do. The pedal
 * counts in them as one number of 28 bits, seven to a byte (gt_linear), so a
 * stretch of the space can be added to and compared like any other number.
 */
#define GT_ADDR_NOTIFY		(0x7F000001UL)	// 1: report what changes, when it changes
#define GT_ADDR_PATCH_NUMBER	(0x00000000UL)	// four bytes of four bits, 0 - 499
#define GT_PATCH_NUMBER_SIZE	(4)
#define GT_ADDR_PATCH_NAME	(0x10000000UL)	// the patch in use, its first sixteen bytes
#define GT_PATCH_NAME_SIZE	(16)
#define GT_ADDR_ASSIGN		(0x10000300UL)	// the first of the patch's ASSIGNs
#define GT_ASSIGN_STRIDE	(0x40)	// from one to the next
#define GT_ASSIGN_COUNT		(16)
#define GT_ASSIGN_SIZE		(0x2C)	// all of one
#define GT_ASSIGN_READ		(0x0E)	// what is asked of one: SW to SOURCE
#define GT_ASSIGN_SW		(0x00)	// 1 when it is on
#define GT_ASSIGN_TARGET	(0x01)	// four bytes of four bits
#define GT_ASSIGN_SOURCE	(0x0D)

// An ASSIGN's source: CC 1 to 31 and CC 64 to 95 are these
#define GT_SOURCE_CC1		(22)
#define GT_SOURCE_CC31		(52)
#define GT_SOURCE_CC64		(53)
#define GT_SOURCE_CC95		(84)

#define GT_ASK_MS		(1000)	// how often the patch number and the switches are asked for
#define GT_NOTIFY_MS		(5000)	// and the reports asked for again, for a unit come back

#define GT_RX_MAX		(48)	// the longest answer asked for is the name, 30 bytes

/*
 * The effects an ASSIGN can switch on and off: the number of its ON OFF
 * target in the ASSIGN TARGET TABLE, and where the effect's switch is, the
 * first byte of the effect's own block. From the GT-1000's MIDI
 * Implementation.
 */
typedef struct {
	uint16_t target;
	uint32_t address;
} gt_effect_t;

static const gt_effect_t effects[] = {
	{    0, 0x10001200UL },	// COMP
	{    8, 0x10001300UL },	// OD/DS 1
	{   17, 0x10001400UL },	// OD/DS 2
	{   26, 0x10001500UL },	// PREAMP 1
	{   40, 0x10001600UL },	// PREAMP 2
	{   54, 0x10001700UL },	// NS 1
	{   58, 0x10001800UL },	// NS 2
	{   62, 0x10001900UL },	// EQ 1
	{   86, 0x10001A00UL },	// EQ 2
	{  110, 0x10001B00UL },	// EQ 3
	{  134, 0x10001C00UL },	// EQ 4
	{  158, 0x10001D00UL },	// DELAY 1
	{  164, 0x10001E00UL },	// DELAY 2
	{  170, 0x10001F00UL },	// DELAY 3
	{  176, 0x10002000UL },	// DELAY 4
	{  182, 0x10002100UL },	// MASTER DELAY
	{  213, 0x10002200UL },	// CHORUS
	{  237, 0x10002300UL },	// FX1
	{  449, 0x10003E00UL },	// FX2
	{  661, 0x10005900UL },	// FX3
	{  873, 0x10007400UL },	// REVERB
	{  915, 0x10007500UL },	// PEDAL FX
	{ 1175, 0x10020100UL },	// FX4, on the GT-1000 only
};
#define GT_EFFECT_COUNT		(sizeof(effects) / sizeof(effects[0]))
#define GT_NO_EFFECT		(0xFF)

// --- what has come in --------------------------------------------------------
static uint8_t rx[GT_RX_MAX];
static uint8_t rx_len = 0;
static bool rx_over = false;		// and it did not fit, so it is dropped

// What each of the sixteen ASSIGNs says: the CC that switches an effect, and
// the effect, or GT_NO_EFFECT
static uint8_t assign_cc[GT_ASSIGN_COUNT];
static uint8_t assign_effect[GT_ASSIGN_COUNT];

static char patch_name[GT_PATCH_NAME_SIZE + 1];	// as the unit has it, padded with spaces
static char name_shown[GT_PATCH_NAME_SIZE + 1];	// the last one shown, so it is written once
static int16_t patch_number = -1;	// not heard yet

static bool started = false;
static volatile bool ask_patch = false;		// set from the USB interrupt: all of it again
static volatile bool show_name = false;
static volatile uint16_t ask_assigns = 0;	// one bit for each ASSIGN to ask for again
static volatile bool ask_switches = false;
static uint32_t ask_at = 0;
static uint32_t notify_at = 0;

bool gt1000_is_on(void){
	return pGlobalSettings[GLOBAL_SETTINGS_KEMPER_MODE] == TWO_WAY_GT1000 && !sw_safe_mode();
}

static void forget_assigns(void){
	memset(assign_cc, 0, sizeof(assign_cc));
	memset(assign_effect, GT_NO_EFFECT, sizeof(assign_effect));
}

void gt1000_reset(void){
	rx_len = 0;
	rx_over = false;
	forget_assigns();
	memset(patch_name, ' ', GT_PATCH_NAME_SIZE);
	patch_name[GT_PATCH_NAME_SIZE] = 0;
	name_shown[0] = 0;
	patch_number = -1;
	started = false;
	ask_patch = false;
	show_name = false;
	ask_assigns = 0;
	ask_switches = false;
	ask_at = 0;
	notify_at = 0;
}

// An address as one number, seven bits from each of its four bytes
static uint32_t gt_linear(uint32_t address){
	return ((address >> 3) & 0x0FE00000UL) | ((address >> 2) & 0x001FC000UL)
			| ((address >> 1) & 0x00003F80UL) | (address & 0x7FUL);
}

static void gt_put_address(uint8_t *p, uint32_t linear){
	p[0] = (uint8_t)((linear >> 21) & 0x7F);
	p[1] = (uint8_t)((linear >> 14) & 0x7F);
	p[2] = (uint8_t)((linear >> 7) & 0x7F);
	p[3] = (uint8_t)(linear & 0x7F);
}

static uint8_t gt_sum(const uint8_t *p, uint8_t len){
	uint8_t sum = 0;
	for(uint8_t i=0; i<len; i++) sum = (uint8_t)(sum + p[i]);
	return (uint8_t)((128 - (sum & 0x7F)) & 0x7F);
}

// A command, its address and up to four bytes after it: a size or the data
static void gt_send(uint8_t command, uint32_t linear, const uint8_t *body, uint8_t body_len){
	uint8_t msg[GT_HEAD_LEN + 4 + 4 + 2];
	uint8_t len = 0;

	msg[len++] = SYSEX_START;
	msg[len++] = GT_MANUF;
	msg[len++] = GT_DEVICE;
	msg[len++] = GT_MODEL_1;
	msg[len++] = GT_MODEL_2;
	msg[len++] = GT_MODEL_3;
	msg[len++] = GT_MODEL_4;
	msg[len++] = command;
	gt_put_address(msg + len, linear);
	len += 4;
	for(uint8_t i=0; i<body_len && i<4; i++){
		msg[len++] = body[i] & 0x7F;
	}
	msg[len] = gt_sum(msg + GT_HEAD_LEN, (uint8_t)(len - GT_HEAD_LEN));
	len++;
	msg[len++] = SYSEX_END;

	sysex_send_message(msg, len);
	midiCmd_send_bytes_serial(msg, len);
}

static void gt_ask(uint32_t linear, uint8_t size){
	const uint8_t body[] = { 0x00, 0x00, 0x00, size };
	gt_send(GT_CMD_RQ1, linear, body, sizeof(body));
}

static void gt_notify(void){
	const uint8_t on = 1;
	gt_send(GT_CMD_DT1, gt_linear(GT_ADDR_NOTIFY), &on, 1);
}

static uint32_t assign_address(uint8_t i){
	return gt_linear(GT_ADDR_ASSIGN) + (uint32_t)i * GT_ASSIGN_STRIDE;
}

// The switch of every effect some ASSIGN switches, each one once
static void gt_ask_switches(void){
	uint32_t asked = 0;
	for(uint8_t i=0; i<GT_ASSIGN_COUNT; i++){
		uint8_t e = assign_effect[i];
		if(e == GT_NO_EFFECT || (asked & (1UL << e))) continue;
		asked |= 1UL << e;
		gt_ask(gt_linear(effects[e].address), 1);
	}
}

void gt1000_task(void){
	if(!gt1000_is_on()) return;

	uint32_t now = HAL_GetTick();
	if(!started){
		gt1000_reset();		// the tables start empty, not as zeroes
		started = true;
		notify_at = now + GT_NOTIFY_MS;
		ask_at = now + GT_ASK_MS;
		gt_notify();
		gt_ask(gt_linear(GT_ADDR_PATCH_NUMBER), GT_PATCH_NUMBER_SIZE);
		return;
	}
	if((int32_t)(now - notify_at) >= 0){
		notify_at = now + GT_NOTIFY_MS;
		gt_notify();
	}
	if((int32_t)(now - ask_at) >= 0){
		ask_at = now + GT_ASK_MS;
		gt_ask(gt_linear(GT_ADDR_PATCH_NUMBER), GT_PATCH_NUMBER_SIZE);
		gt_ask_switches();
	}
	if(ask_patch){
		// Another patch: its name, and its ASSIGNs, which bring the
		// switches after them
		ask_patch = false;
		gt_ask(gt_linear(GT_ADDR_PATCH_NAME), GT_PATCH_NAME_SIZE);
		ask_assigns = 0xFFFF;
	}
	if(ask_assigns){
		uint32_t primask = __get_PRIMASK();
		__disable_irq();
		uint16_t which = ask_assigns;	// the interrupt may add to it meanwhile
		ask_assigns = 0;
		__set_PRIMASK(primask);
		for(uint8_t i=0; i<GT_ASSIGN_COUNT; i++){
			if(which & (1U << i)) gt_ask(assign_address(i), GT_ASSIGN_READ);
		}
	}
	if(ask_switches){
		ask_switches = false;
		gt_ask_switches();
	}
	if(show_name){
		show_name = false;
		uint8_t len = GT_PATCH_NAME_SIZE;
		while(len && patch_name[len - 1] == ' ') len--;	// the padding
		if(len != strlen(name_shown) || memcmp(name_shown, patch_name, len) != 0){
			memcpy(name_shown, patch_name, len);
			name_shown[len] = 0;
			// The info line, beside the bank name, so the bank is still readable
			display_host_text(DISPLAY_TEXT_INFO, TEXT_KEEP_ALWAYS, (const uint8_t *)patch_name, len);
		}
	}
}

// --- reading what the unit says ----------------------------------------------
static uint16_t gt_nibbles(const uint8_t *p){
	return (uint16_t)(((p[0] & 0x0F) << 12) | ((p[1] & 0x0F) << 8) | ((p[2] & 0x0F) << 4) | (p[3] & 0x0F));
}

// One ASSIGN read whole, from its switch to its source
static void gt_assign(uint8_t i, const uint8_t *data){
	assign_effect[i] = GT_NO_EFFECT;
	if(data[GT_ASSIGN_SW] != 1) return;
	uint8_t source = data[GT_ASSIGN_SOURCE];
	uint8_t cc;
	if(source >= GT_SOURCE_CC1 && source <= GT_SOURCE_CC31){
		cc = (uint8_t)(source - GT_SOURCE_CC1 + 1);
	} else if(source >= GT_SOURCE_CC64 && source <= GT_SOURCE_CC95){
		cc = (uint8_t)(source - GT_SOURCE_CC64 + 64);
	} else {
		return;		// a switch or a pedal of the unit's own
	}
	uint16_t target = gt_nibbles(data + GT_ASSIGN_TARGET);
	for(uint8_t e=0; e<GT_EFFECT_COUNT; e++){
		if(effects[e].target == target){
			assign_cc[i] = cc;
			assign_effect[i] = e;
			ask_switches = true;
			return;
		}
	}
}

// An effect's switch: every CC that switches it, on or off, to the LEDs
static void gt_effect_state(uint8_t e, uint8_t on){
	for(uint8_t i=0; i<GT_ASSIGN_COUNT; i++){
		if(assign_effect[i] != e) continue;
		uint8_t msg[3] = { 0xB0, assign_cc[i], on ? 127 : 0 };	// the channel does not count here
		sw_feedback_any_channel(msg);
	}
}

// A stretch of the address space, [start, start + len)
static void gt_data(uint32_t start, const uint8_t *data, uint8_t len){
	uint32_t end = start + len;

	uint32_t number = gt_linear(GT_ADDR_PATCH_NUMBER);
	if(start == number && len >= GT_PATCH_NUMBER_SIZE){
		int16_t n = (int16_t)gt_nibbles(data);
		if(n != patch_number){
			patch_number = n;
			forget_assigns();	// another patch's, until they come
			ask_patch = true;
		}
	}

	uint32_t name = gt_linear(GT_ADDR_PATCH_NAME);
	if(start < name + GT_PATCH_NAME_SIZE && end > name){
		// The whole name asked for, or a letter of it changed on the unit
		for(uint32_t a = (start > name ? start : name); a < end && a < name + GT_PATCH_NAME_SIZE; a++){
			patch_name[a - name] = (char)data[a - start];
		}
		show_name = true;
	}

	for(uint8_t i=0; i<GT_ASSIGN_COUNT; i++){
		uint32_t at = assign_address(i);
		if(start >= at + GT_ASSIGN_SIZE || end <= at) continue;
		if(start == at && len >= GT_ASSIGN_READ){
			gt_assign(i, data);
		} else {
			ask_assigns |= (uint16_t)(1U << i);	// a part of it changed: read it again
		}
	}

	for(uint8_t e=0; e<GT_EFFECT_COUNT; e++){
		uint32_t sw = gt_linear(effects[e].address);
		if(sw >= start && sw < end){
			gt_effect_state(e, data[sw - start]);
		}
	}
}

static void gt_message(const uint8_t *msg, uint8_t len){
	// The header, an address and at least one byte, the sum and the end
	if(len < GT_HEAD_LEN + 4 + 1 + 2) return;
	if(msg[7] != GT_CMD_DT1) return;
	const uint8_t *body = msg + GT_HEAD_LEN;
	uint8_t body_len = (uint8_t)(len - GT_HEAD_LEN - 2);	// address and data
	if(gt_sum(body, body_len) != msg[len - 2]) return;	// garbled

	uint32_t start = ((uint32_t)(body[0] & 0x7F) << 21) | ((uint32_t)(body[1] & 0x7F) << 14)
			| ((uint32_t)(body[2] & 0x7F) << 7) | (body[3] & 0x7F);
	gt_data(start, body + 4, (uint8_t)(body_len - 4));
}

/*
 * A System Exclusive message that is not ours, in the three byte pieces the USB
 * interrupt hands over. They are too small to tell whose the message is by the
 * first one, so it is put together first and looked at when it ends.
 */
void gt1000_sysex_chunk(const uint8_t *data, uint8_t len, bool is_end){
	if(!gt1000_is_on()){
		rx_len = 0;
		rx_over = false;
		return;
	}
	if(rx_len && len && data[0] == SYSEX_START){
		rx_len = 0;		// the message before it never ended
		rx_over = false;
	}

	if(rx_len + len > GT_RX_MAX){
		rx_over = true;		// longer than anything the pedal asks for
	} else {
		memcpy(rx + rx_len, data, len);
		rx_len = (uint8_t)(rx_len + len);
	}

	if(is_end){
		// The device byte is whatever the unit is set to, so it is not
		// looked at; the maker and the model are
		if(!rx_over && rx_len > GT_HEAD_LEN && rx[0] == SYSEX_START
				&& rx[1] == GT_MANUF && rx[3] == GT_MODEL_1 && rx[4] == GT_MODEL_2
				&& rx[5] == GT_MODEL_3 && rx[6] == GT_MODEL_4
				&& rx[rx_len - 1] == SYSEX_END){
			gt_message(rx, rx_len);
		}
		rx_len = 0;
		rx_over = false;
	}
}
