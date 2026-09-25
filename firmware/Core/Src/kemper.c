/*
 * kemper.c
 *
 * Two way talk with a Kemper Profiler. The Kemper answers questions, and
 * reports what is changed on it, in System Exclusive messages of its own:
 *
 *	F0 00 20 33 02 7F <function> <instance> <page> <parameter> ... F7
 *
 * The pedal sends the beacon that asks the amp to keep reporting itself, and
 * asks for the rig name; what comes back it turns into the two things worth
 * seeing from the floor. The rig name goes on the display. A module switching
 * on or off is turned into the Control Change that switches that module, and
 * handed to the LED feedback, so any button that sends that CC ends up lit or
 * dark like the amp, however the module was switched. Nothing is sent to the
 * amp because of what it reports, so the two cannot chase each other.
 *
 * The answers come in over USB, which on a Profiler Player is the socket the
 * pedal is plugged into, the Player being the host that also powers it.
 */

#include "kemper.h"
#include "midi_defines.h"
#include "flash_midi_settings.h"
#include "switch_router.h"
#include "display.h"
#include "midi_cmds.h"
#include "usbd_midi_if.h"
#include "stm32f1xx_hal.h"
#include <string.h>

// --- the amp's own dialect ---------------------------------------------------
#define KEMPER_MANUF_1		(0x00)
#define KEMPER_MANUF_2		(0x20)
#define KEMPER_MANUF_3		(0x33)
#define KEMPER_PRODUCT		(0x02)	// Profiler Player, the model that answers over USB
#define KEMPER_DEVICE		(0x7F)	// whoever is listening
#define KEMPER_HEAD_LEN		(6)	// F0 and the five bytes above

#define KEMPER_FN_PARAM		(0x01)	// one parameter, value in two bytes
#define KEMPER_FN_STRING	(0x03)	// one parameter that is text
#define KEMPER_FN_REQ_PARAM	(0x41)	// ask for one parameter
#define KEMPER_FN_REQ_STRING	(0x43)	// ask for one that is text
#define KEMPER_FN_BEACON	(0x7E)	// ask to be told of changes from now on

#define KEMPER_PAGE_RIG		(0x00)	// the rig itself
#define KEMPER_PARAM_RIG_NAME	(0x01)
#define KEMPER_PARAM_ON_OFF	(0x03)	// in an effect module's page

/*
 * The beacon: 7E, the instance, 40, the set of parameters asked for, the flags
 * and how long the amp should keep reporting, in units of two seconds. Of the
 * flags, bit 0 says this is the first one, bit 1 that the answers should come
 * back as System Exclusive and bit 5 that the tuner is only worth reporting
 * while the tuner is up, which keeps a stream the pedal has no use for off the
 * wire. The beacon is sent again every half of the lease, and that is what
 * tells the amp the pedal is still on the other end.
 */
#define KEMPER_BEACON_SET	(0x02)
#define KEMPER_BEACON_FIRST	(0x23)	// first one, and the tuner only in tuner mode
#define KEMPER_BEACON_AGAIN	(0x22)	// the ones that keep it alive
#define KEMPER_BEACON_LEASE	(0x05)	// ten seconds
#define KEMPER_BEACON_MS	(5000)	// so it goes out every five
#define KEMPER_ASK_MS		(1000)	// how often the rig name is asked for

#define KEMPER_RX_MAX		(48)	// a rig name is 20 characters at most

/*
 * The effect modules, each with the page it answers on and the Control Change
 * that switches it, which is the one a button of the configuration sends. Some
 * have a second CC that switches them keeping their tails, and a button using
 * either one follows the amp. The numbers come from the Profiler's MIDI map,
 * the same one the Kemper Player template uses.
 */
typedef struct {
	uint8_t page;
	uint8_t cc;
	uint8_t cc_tails;	// 0 when the module has no such thing
} kemper_module_t;

static const kemper_module_t modules[] = {
	{ 0x32, 17, 0 },	// Stomp A
	{ 0x33, 18, 0 },	// Stomp B
	{ 0x34, 19, 0 },	// Stomp C
	{ 0x35, 20, 0 },	// Stomp D
	{ 0x38, 22, 0 },	// Stomp X
	{ 0x3A, 24, 25 },	// Mod
	{ 0x3C, 26, 27 },	// Delay, which the amp does not report by itself
	{ 0x3D, 28, 29 },	// Reverb, nor this one
};
#define KEMPER_FIRST_ASKED	(6)	// the two above: asked for, not waited for
#define KEMPER_MODULE_COUNT	(sizeof(modules) / sizeof(modules[0]))

// --- what has come in --------------------------------------------------------
static uint8_t rx[KEMPER_RX_MAX];
static uint8_t rx_len = 0;
static bool rx_over = false;		// and it did not fit, so it is dropped
static char rig_name[DISPLAY_TEXT_MAX + 1] = {0};		// the last one shown, so it is written once

static bool started = false;
static volatile bool ask_modules = false;	// set from the USB interrupt
static uint32_t beacon_at = 0;
static uint32_t name_at = 0;

bool kemper_is_on(void){
	return pGlobalSettings[GLOBAL_SETTINGS_KEMPER_MODE] == 1 && !sw_safe_mode();
}

void kemper_reset(void){
	rx_len = 0;
	rx_over = false;
	rig_name[0] = 0;
	started = false;
	ask_modules = false;
	beacon_at = 0;
	name_at = 0;
}

static void kemper_send(const uint8_t *body, uint8_t body_len){
	uint8_t msg[16];
	uint8_t len = 0;

	msg[len++] = SYSEX_START;
	msg[len++] = KEMPER_MANUF_1;
	msg[len++] = KEMPER_MANUF_2;
	msg[len++] = KEMPER_MANUF_3;
	msg[len++] = KEMPER_PRODUCT;
	msg[len++] = KEMPER_DEVICE;
	for(uint8_t i=0; i<body_len && len < sizeof(msg) - 1; i++){
		msg[len++] = body[i];
	}
	msg[len++] = SYSEX_END;

	// The buffer a message is put together in is shared with the answers the
	// USB interrupt sends, so it is not left half written when one lands
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	sysex_send_message(msg, len);
	if(!primask) __enable_irq();
	midiCmd_send_bytes_serial(msg, len);
}

// The beacon: asks the amp to report what it is doing from now on
static void kemper_send_beacon(uint8_t flags){
	const uint8_t body[] = { KEMPER_FN_BEACON, 0x00, 0x40, KEMPER_BEACON_SET,
			flags, KEMPER_BEACON_LEASE };
	kemper_send(body, sizeof(body));
}

static void kemper_ask_rig_name(void){
	const uint8_t body[] = { KEMPER_FN_REQ_STRING, 0x00, KEMPER_PAGE_RIG, KEMPER_PARAM_RIG_NAME };
	kemper_send(body, sizeof(body));
}

static void kemper_ask_module(uint8_t i){
	const uint8_t body[] = { KEMPER_FN_REQ_PARAM, 0x00,
			modules[i].page, KEMPER_PARAM_ON_OFF };
	kemper_send(body, sizeof(body));
}

// All eight at once, for the LEDs to start out right and to catch up after a
// rig change
static void kemper_ask_modules(void){
	for(uint8_t i=0; i<KEMPER_MODULE_COUNT; i++){
		kemper_ask_module(i);
	}
}

void kemper_task(void){
	if(!kemper_is_on()) return;

	uint32_t now = HAL_GetTick();
	if(!started){
		started = true;
		beacon_at = now + KEMPER_BEACON_MS;
		name_at = now + KEMPER_ASK_MS;
		kemper_send_beacon(KEMPER_BEACON_FIRST);
		kemper_ask_rig_name();
		kemper_ask_modules();
		return;
	}
	if((int32_t)(now - beacon_at) >= 0){
		beacon_at = now + KEMPER_BEACON_MS;
		kemper_send_beacon(KEMPER_BEACON_AGAIN);
	}
	if((int32_t)(now - name_at) >= 0){
		name_at = now + KEMPER_ASK_MS;
		kemper_ask_rig_name();
		// The amp reports the first six modules by itself, but not the
		// delay and the reverb, so those two are asked for every time
		for(uint8_t i=KEMPER_FIRST_ASKED; i<KEMPER_MODULE_COUNT; i++){
			kemper_ask_module(i);
		}
	}
	if(ask_modules){
		ask_modules = false;
		kemper_ask_modules();
	}
}

// --- reading what the amp says ----------------------------------------------
static void kemper_module_state(uint8_t page, uint8_t on){
	for(uint8_t i=0; i<KEMPER_MODULE_COUNT; i++){
		if(modules[i].page != page) continue;
		uint8_t msg[3];
		msg[0] = 0xB0;			// the channel does not count here
		msg[1] = modules[i].cc;
		msg[2] = on ? 127 : 0;
		sw_feedback_any_channel(msg);
		if(modules[i].cc_tails){
			msg[1] = modules[i].cc_tails;
			sw_feedback_any_channel(msg);
		}
		return;
	}
}

static void kemper_rig_name(const uint8_t *text, uint8_t len){
	if(len > sizeof(rig_name) - 1) len = sizeof(rig_name) - 1;
	if(len == strlen(rig_name) && memcmp(rig_name, text, len) == 0) return;
	memcpy(rig_name, text, len);
	rig_name[len] = 0;
	// The info line, beside the bank name, so the bank is still readable
	display_host_text(DISPLAY_TEXT_INFO, TEXT_KEEP_ALWAYS, text, len);
	ask_modules = true;	// another rig: its modules are another matter
}

static void kemper_message(const uint8_t *msg, uint8_t len){
	if(len < KEMPER_HEAD_LEN + 4) return;		// function, instance, page, parameter
	uint8_t function = msg[KEMPER_HEAD_LEN];
	uint8_t page = msg[KEMPER_HEAD_LEN + 2];
	uint8_t parameter = msg[KEMPER_HEAD_LEN + 3];

	if(function == KEMPER_FN_PARAM && len >= KEMPER_HEAD_LEN + 6){
		if(parameter == KEMPER_PARAM_ON_OFF){
			kemper_module_state(page, msg[KEMPER_HEAD_LEN + 5] & 0x7F);
		}
	} else if(function == KEMPER_FN_STRING){
		if(page == KEMPER_PAGE_RIG && parameter == KEMPER_PARAM_RIG_NAME){
			const uint8_t *text = msg + KEMPER_HEAD_LEN + 4;
			uint8_t text_len = (uint8_t)(len - (KEMPER_HEAD_LEN + 4));
			while(text_len && (text[text_len - 1] == SYSEX_END || text[text_len - 1] == 0)){
				text_len--;		// the end byte, and the string's own terminator
			}
			kemper_rig_name(text, text_len);
		}
	}
}

/*
 * A System Exclusive message that is not ours, in the three byte pieces the USB
 * interrupt hands over. They are too small to tell whose the message is by the
 * first one, so it is put together first and looked at when it ends.
 */
void kemper_sysex_chunk(const uint8_t *data, uint8_t len, bool is_end){
	if(!kemper_is_on()){
		rx_len = 0;
		rx_over = false;
		return;
	}
	if(rx_len && len && data[0] == SYSEX_START){
		rx_len = 0;		// the message before it never ended
		rx_over = false;
	}

	if(rx_len + len > KEMPER_RX_MAX){
		rx_over = true;		// longer than anything the pedal watches
	} else {
		memcpy(rx + rx_len, data, len);
		rx_len = (uint8_t)(rx_len + len);
	}

	if(is_end){
		// F0 and the maker's three bytes; the two after them are the
		// product and the device, which the amp answers with zeroes
		if(!rx_over && rx_len > KEMPER_HEAD_LEN && rx[0] == SYSEX_START
				&& rx[1] == KEMPER_MANUF_1 && rx[2] == KEMPER_MANUF_2
				&& rx[3] == KEMPER_MANUF_3){
			kemper_message(rx, rx_len);
		}
		rx_len = 0;
		rx_over = false;
	}
}
