/*
 * switch_router.c
 *
 *  Created on: 8 Jul 2021
 *      Author: D Harvie
 */
#include "main.h"
#include "midi_defines.h"
#include "midi_cmds.h"
#include "flash_midi_settings.h"
#include "display.h"
#include "usbd_hid_custom.h"
#include "usbd_midi_if.h"
#include "tempo.h"
#include "display.h"
#include "state_store.h"
#include "leds.h"
#include "sleep.h"
#include "expression.h"
#include "switch_router.h"
#include <string.h>

void update_leds_on_bank_change(void);
static void fire_bank_enter_cmds(uint8_t bank);
static void fire_bank_leave_cmds(uint8_t bank);
static void apply_scene(uint8_t mask, uint8_t states);
static void release_group(uint8_t i);
uint8_t sw_button_is_toggle(uint8_t bank, uint8_t sw);
static bool switch_down(GPIO_TypeDef *port, uint16_t pin);

// Command lists and the pauses inside them, see run_cmd_list further down
#define PENDING_OWNER_NONE	(0xFF)	// a list with no button to release
#define LIST_SKIP_BANK		(0x01)	// bank change commands are ignored in this list
#define LIST_UP_AFTER		(0x02)	// the release pass follows the press pass
static bool run_cmd_list(uint8_t *base, uint8_t first, uint8_t start, uint8_t toggle, uint8_t owner, uint8_t flags, bool allow_wait);
static void run_list_up(uint8_t *base, uint8_t first, uint8_t toggle, uint8_t flags);
static bool pending_defer_release(uint8_t owner);
static void pending_flush_owner(uint8_t owner);
static bool pending_any(void);
static void pending_clear(void);
static void ramp_stop_all(void);
static void ramp_stop(uint8_t channel, uint8_t cc);
static void lfo_stop(uint8_t channel, uint8_t cc);
static void lfo_stop_all(void);
static void lfo_restart_all(void);

/*
 * Creating some constant arrays for the switches that can be scanned and handled
 * in a loop to simplify code and reduce duplication;
 */
typedef struct {
	GPIO_TypeDef *sw_gpio_port;
	uint16_t sw_gpio_pin;
	volatile uint16_t *pSwChangeState;
	GPIO_TypeDef *led_gpio_port;
	uint16_t led_gpio_pin;
	uint32_t switch_toggle_state; // Bit per bank (0..MIDI_NUM_BANKS-1)
	uint32_t led_cmd_toggle;
	// Long press: a second command set fired when the button is held
	uint32_t long_toggle_state;   // Toggle state of the long press commands, bit per bank
	uint32_t long_cmd_present;    // Bit per bank: this button has long press commands
	uint32_t long_cmd_toggle;     // Bit per bank: any long press command is a toggle
	// Double press: a third command set fired by two presses in quick succession
	uint32_t double_toggle_state; // Toggle state of the double press commands, bit per bank
	uint32_t double_cmd_present;  // Bit per bank: this button has double press commands
	uint32_t double_cmd_toggle;   // Bit per bank: any double press command is a toggle
	// Tap LED: bit per bank, the button holds a Tap command in Tap / Clock mode
	uint32_t tap_blink;
	uint32_t clock_blink;
	uint32_t press_tick;         // HAL tick when the button went down
	uint32_t release_tick;       // HAL tick when a possible first press of a double ended
	uint8_t press_state;         // PRESS_IDLE / PRESS_PENDING / PRESS_SHORT / PRESS_LONG
	// Auto-repeat of the CCInc / PCInc commands marked Repeat while held
	uint8_t *repeat_list;        // List that fired and holds such commands, NULL for none
	uint8_t repeat_first;        // First command of the part of it that fired (a cycle state)
	uint32_t repeat_tick;        // HAL tick of the last firing
	uint16_t repeat_interval;    // ms until the next one
} sw_t;

#define PRESS_IDLE		(0)  // Released
#define PRESS_PENDING	(1)  // Down, waiting to see if it becomes a long press or half a double
#define PRESS_SHORT		(2)  // Short press commands fired, waiting for release
#define PRESS_LONG		(3)  // Long press commands fired, waiting for release
#define PRESS_WAIT_SECOND	(4)  // Released after a tap, waiting to see if a second press follows
#define PRESS_DOUBLE	(5)  // Double press commands fired, waiting for release

typedef struct {
	uint32_t systick_timout;
	uint8_t *pRomCmd;
} delayed_cmd_t;

#define SW_PORTA_MASK (SW_1_Pin | SW_2_Pin | SW_E_Pin | SW_D_Pin | SW_C_Pin)
#define SW_PORTB_MASK (SW_A_Pin | SW_3_Pin | SW_4_Pin | SW_5_Pin)
#define SW_PORTC_MASK (SW_B_Pin)

uint16_t port_A_previous_state = SW_PORTA_MASK; // All pins will be high un-pressed
volatile uint16_t port_A_switches_changed = 0;
uint16_t port_B_previous_state = SW_PORTB_MASK; // All pins will be high un-pressed
volatile uint16_t port_B_switches_changed = 0;
uint16_t port_C_previous_state = SW_PORTC_MASK; // All pins will be high un-pressed
volatile uint16_t port_C_switches_changed = 0;

volatile uint8_t debounce_counter = 0;
// Flag to indicate if USB is suspended. If so, we shouldn't update LEDs or read switches in the main loop
// because the main loop might keep running even if USB is suspended (if low_power_enable is 0)
static volatile uint8_t is_app_suspended = 0; 

extern uint8_t f_sys_config_complete;

uint8_t switch_current_page = 0;

sw_t a_sw_obj[] = {
		{ .sw_gpio_port = SW_1_GPIO_Port, .sw_gpio_pin = SW_1_Pin, .pSwChangeState = &port_A_switches_changed, .led_gpio_port = LED_1_GPIO_Port, .led_gpio_pin = LED_1_Pin, .switch_toggle_state = 0},
		{ .sw_gpio_port = SW_2_GPIO_Port, .sw_gpio_pin = SW_2_Pin, .pSwChangeState = &port_A_switches_changed, .led_gpio_port = LED_2_GPIO_Port, .led_gpio_pin = LED_2_Pin, .switch_toggle_state = 0},
		{ .sw_gpio_port = SW_3_GPIO_Port, .sw_gpio_pin = SW_3_Pin, .pSwChangeState = &port_B_switches_changed, .led_gpio_port = LED_3_GPIO_Port, .led_gpio_pin = LED_3_Pin, .switch_toggle_state = 0},
		{ .sw_gpio_port = SW_4_GPIO_Port, .sw_gpio_pin = SW_4_Pin, .pSwChangeState = &port_B_switches_changed, .led_gpio_port = LED_4_GPIO_Port, .led_gpio_pin = LED_4_Pin, .switch_toggle_state = 0},

		{ .sw_gpio_port = SW_A_GPIO_Port, .sw_gpio_pin = SW_A_Pin, .pSwChangeState = &port_B_switches_changed, .led_gpio_port = LED_A_GPIO_Port, .led_gpio_pin = LED_A_Pin, .switch_toggle_state = 0},
		{ .sw_gpio_port = SW_B_GPIO_Port, .sw_gpio_pin = SW_B_Pin, .pSwChangeState = &port_C_switches_changed, .led_gpio_port = LED_B_GPIO_Port, .led_gpio_pin = LED_B_Pin, .switch_toggle_state = 0},
		{ .sw_gpio_port = SW_C_GPIO_Port, .sw_gpio_pin = SW_C_Pin, .pSwChangeState = &port_A_switches_changed, .led_gpio_port = LED_C_GPIO_Port, .led_gpio_pin = LED_C_Pin, .switch_toggle_state = 0},
		{ .sw_gpio_port = SW_D_GPIO_Port, .sw_gpio_pin = SW_D_Pin, .pSwChangeState = &port_A_switches_changed, .led_gpio_port = LED_D_GPIO_Port, .led_gpio_pin = LED_D_Pin, .switch_toggle_state = 0}
};

#define MAX_DELAYED_CMDS (32)

delayed_cmd_t delayed_cmds[MAX_DELAYED_CMDS];


/*
 * This scans the switch ports each ms for changes in the systick interrupt context.
 * We can't use port interrupts, as some of the pins are on non-interrupt pins.
 *
 * Switch changes are then handled in the main loop.
 */
void sw_scan(void){

	if(!f_sys_config_complete){
		return;
	}

	if(debounce_counter){
		debounce_counter--;
		return;
	}

	/* PORTA input pins */
	uint16_t current_port_A = GPIOA->IDR & SW_PORTA_MASK;
	port_A_switches_changed |= current_port_A  ^ port_A_previous_state;
	port_A_previous_state = current_port_A;

	/* PORTB input pins */
	uint16_t current_port_B = GPIOB->IDR & SW_PORTB_MASK;
	port_B_switches_changed |= current_port_B  ^ port_B_previous_state;
	port_B_previous_state = current_port_B;

	/* PORTC input pins */
	uint16_t current_port_C = GPIOC->IDR & SW_PORTC_MASK;
	port_C_switches_changed |= current_port_C  ^ port_C_previous_state;
	port_C_previous_state = current_port_C;

	if(port_A_switches_changed | port_B_switches_changed | port_C_switches_changed){
		sleep_note_activity();
		debounce_counter = 10; // 10ms debounce delay
		return;
	}

}

static inline uint8_t get_sw_toggle_state(sw_t *sw){
	return (sw->switch_toggle_state >> switch_current_page) & 1U;
}

static inline void toggle_sw_state(sw_t *sw){
	sw->switch_toggle_state ^= (1UL << switch_current_page);
	state_store_mark_dirty();
	if(sw->led_cmd_toggle & (1UL << switch_current_page)){
		display_request_refresh();
	}
}


static uint8_t key_press_count[256] = {0};
static uint8_t mod_press_count[8] = {0};

static void update_keyboard_state(uint8_t mod_byte, uint8_t key_code, uint8_t is_pressed) {
    // Modifiers
    for(int i=0; i<8; i++) {
        if((mod_byte >> i) & 1) {
            if(is_pressed) {
                if(mod_press_count[i] < 255) mod_press_count[i]++;
            } else {
                if(mod_press_count[i] > 0) mod_press_count[i]--;
            }
        }
    }
    
    // Key Code
    if(key_code != 0) {
       if(is_pressed) {
            if(key_press_count[key_code] < 255) key_press_count[key_code]++;
       } else {
            if(key_press_count[key_code] > 0) key_press_count[key_code]--;
       }
    }
    
    // Build Report: [report id][modifiers][reserved][6 key codes]
    uint8_t report[9] = {HID_REPORT_ID_KEYBOARD, 0};

    // Mod Byte
    for(int i=0; i<8; i++) {
        if(mod_press_count[i] > 0) report[1] |= (1<<i);
    }

    // Keys (max 6)
    int k = 0;
    for(int i=0; i<256 && k < 6; i++) {
        if(key_press_count[i] > 0) {
            report[3+k] = i;
            k++;
        }
    }

    HID_SendReport_FS(report, sizeof(report));
}

// Consumer control (media keys): one usage at a time, 0 releases it
static void send_media_usage(uint16_t usage){
    uint8_t report[3] = {HID_REPORT_ID_CONSUMER, usage & 0xFF, (usage >> 8) & 0x03};
    HID_SendReport_FS(report, sizeof(report));
}

static inline uint16_t media_usage_from_rom(const uint8_t *pRom){
    return pRom[1] | ((pRom[2] & 0x03) << 8);
}

/*
 * Relative CC ("CCInc"): every press moves a value by a step and sends it.
 * The value has to live in RAM, indexed by which command slot it came from,
 * so it survives repeated presses but resets at power on to the configured
 * start value. 0xFF marks a slot that has not been used yet.
 */
#define CCINC_SLOTS (2 * MIDI_NUM_BANKS * MIDI_NUM_SWITCHES * MIDI_NUM_COMMANDS_PER_SWITCH)
static uint8_t ccinc_value[CCINC_SLOTS];

static void ccinc_reset(void){
	for(uint32_t i=0; i<CCINC_SLOTS; i++) ccinc_value[i] = 0xFF;
}

// Unique slot index for a command, whether it came from the short or long list
static int32_t ccinc_index(const uint8_t *pRom){
	int32_t per_set = MIDI_NUM_BANKS * MIDI_NUM_SWITCHES * MIDI_NUM_COMMANDS_PER_SWITCH;
	if(pRom >= pSwitchCmds && pRom < pSwitchCmds + per_set * MIDI_ROM_CMD_SIZE){
		return (pRom - pSwitchCmds) / MIDI_ROM_CMD_SIZE;
	}
	if(pRom >= pLongPressCmds && pRom < pLongPressCmds + per_set * MIDI_ROM_CMD_SIZE){
		return per_set + (pRom - pLongPressCmds) / MIDI_ROM_CMD_SIZE;
	}
	return -1; // e.g. a bank-enter command: no stored value, always starts fresh
}

// A repeat (repeat true) that cannot move any further sends nothing
static void send_ccinc(uint8_t *pRom, bool repeat){
	uint8_t channel = pRom[0] & 0x0F;
	uint8_t cc = pRom[1] & 0x7F;
	uint8_t wrap = (pRom[1] & 0x80) != 0;
	uint8_t step = (pRom[2] & 0x7F) ? (pRom[2] & 0x7F) : 1;
	uint8_t down = (pRom[3] & 0x80) != 0;
	uint8_t start = pRom[3] & 0x7F;

	int32_t slot = ccinc_index(pRom);
	uint8_t current = start;
	if(slot >= 0){
		if(ccinc_value[slot] == 0xFF) ccinc_value[slot] = start;
		current = ccinc_value[slot];
	}

	int16_t next = (int16_t)current + (down ? -(int16_t)step : (int16_t)step);
	if(next > 127) next = wrap ? (int16_t)(next - 128) : 127;
	if(next < 0)   next = wrap ? (int16_t)(next + 128) : 0;
	if(repeat && next == current) return;

	if(slot >= 0) ccinc_value[slot] = (uint8_t)next;
	midiCmd_send_cc(channel, cc, (uint8_t)next);
	display_show_cc(cc, (uint8_t)next);
}

/*
 * Relative Program Change ("next / previous preset"): moves from the program
 * last sent on the channel, whoever sent it: a PC command, a bank being
 * entered, or the host over USB. Nothing sent yet counts as program 0. Shared
 * by every button, so a Next and a Previous button work as a pair.
 */
static uint8_t pc_current[16] = { [0 ... 15] = 0xFF };

void sw_note_program(uint8_t channel, uint8_t program){
	pc_current[channel & 0x0F] = program & 0x7F;
}

static void send_pc_relative(const uint8_t *pRom, bool repeat){
	uint8_t channel = pRom[0] & 0x0F;
	int16_t step = (pRom[1] & 0x7F) ? (pRom[1] & 0x7F) : 1;
	int16_t top = pRom[3] & 0x7F;
	bool wrap = (pRom[3] & 0x80) != 0;
	int16_t current = (pc_current[channel] <= 127) ? pc_current[channel] : 0;

	bool down = pRom[2] == PC_REL_DOWN || pRom[2] == PC_REL_DOWN_REPEAT;
	int16_t next = current + (down ? -step : step);
	if(wrap){
		next %= top + 1;
		if(next < 0) next += top + 1;
	} else {
		if(next > top) next = top;
		if(next < 0) next = 0;
	}
	if(repeat && next == current) return;

	uint8_t pc[4] = { CMD_PC_NIBBLE | channel, (uint8_t)next, 0x80, 0xFF }; // no Bank Select
	midiCmd_send_pc_command_from_rom(pc);
	pc_current[channel] = (uint8_t)next;

	char msg[9];
	snprintf(msg, sizeof(msg), "PC %u", (unsigned)next);
	display_show_message(msg);
}

// A stored SysEx payload, wrapped in F0 ... F7 and sent to USB and DIN
// A Tap command that steps the tempo up or down
static bool tap_is_step(const uint8_t *pRom){
	uint8_t mode = pRom[0] & 0x0F;
	return mode == TAP_MODE_UP || mode == TAP_MODE_DOWN;
}

/*
 * Tap command: tap the tempo, start or stop the clock, set the tempo to a
 * fixed BPM, or step it up or down. The new tempo shows on the display; the
 * running clock and the free beat pick it up at once.
 */
static void send_tap(const uint8_t *pRom){
	uint16_t bpm = tempo_get_bpm();
	uint8_t step = pRom[2] & 0x7F;
	switch(pRom[0] & 0x0F){
	case TAP_MODE_CLOCK:
		tempo_clock_toggle();
		break;
	case TAP_MODE_SET:
		tempo_set_bpm((uint16_t)((pRom[2] & 0x7F) | ((pRom[3] & 0x7F) << 7)));
		break;
	case TAP_MODE_UP:
		tempo_set_bpm((uint16_t)(bpm + (step ? step : 1)));
		break;
	case TAP_MODE_DOWN:
		step = step ? step : 1;
		tempo_set_bpm(bpm > step ? (uint16_t)(bpm - step) : 0);	// clamped to the minimum
		break;
	default:
		tempo_tap();
		break;
	}
	display_show_tempo();
}

static void send_stored_sysex(const uint8_t *pRom){
	uint8_t index = pRom[1];
	if(index >= SYSEX_STRING_COUNT) return;
	const uint8_t *entry = pSysExStrings + index * SYSEX_STRING_STRIDE;
	uint8_t len = entry[0];
	if(len == 0 || len > SYSEX_STRING_MAX) return; // empty or erased flash

	uint8_t msg[SYSEX_STRING_MAX + 2];
	msg[0] = SYSEX_START;
	for(uint8_t i=0; i<len; i++) msg[1+i] = entry[1+i] & 0x7F;
	msg[1+len] = SYSEX_END;

	sysex_send_message(msg, len + 2);
	midiCmd_send_bytes_serial(msg, len + 2);
}

uint8_t* get_rom_pointer(uint8_t page, uint8_t sw, uint8_t cmd){
	return pSwitchCmds + (MIDI_ROM_KEY_STRIDE * sw) + (MIDI_ROM_CMD_SIZE * cmd) + (MIDI_ROM_KEY_STRIDE * 8 * page);
}

static uint8_t* get_long_rom_pointer(uint8_t page, uint8_t sw, uint8_t cmd){
	return pLongPressCmds + (MIDI_ROM_KEY_STRIDE * sw) + (MIDI_ROM_CMD_SIZE * cmd) + (MIDI_ROM_KEY_STRIDE * 8 * page);
}

static uint8_t* get_double_rom_pointer(uint8_t page, uint8_t sw, uint8_t cmd){
	return pDoublePressCmds + (MIDI_ROM_KEY_STRIDE * sw) + (MIDI_ROM_CMD_SIZE * cmd) + (MIDI_ROM_KEY_STRIDE * 8 * page);
}

/*
 * Whether a command does anything at all, which is what tells a button it has
 * long press or double press commands. The empty command type counts when its
 * low nibble names one of the commands that share it (Wait, Exp, MMC, Song and
 * the rest), so a long press that only sends one of those still fires.
 */
static inline uint8_t cmd_is_present(const uint8_t *pRom){
	uint8_t t = *pRom & 0xF0;
	if(t == CMD_NO_CMD_NIBBLE) return (*pRom & 0x0F) != 0;
	return t != 0xF0; // 0xF0 = erased flash
}

/*
 * Cycle buttons. Cycle commands split a button's short press list into states:
 * the commands before the first Cycle are state 1, those after it state 2, and
 * so on. Each press sends the next state's commands, back to state 1 after the
 * last, and the display shows the label of the state last sent. A button starts
 * before its first state, so its first press sends state 1. Every button of
 * every bank keeps its place while the pedal is on; a change of configuration
 * or a power cycle starts them all again.
 */
#define CYCLE_NONE	(0xFF)	// nothing sent yet
static uint8_t cycle_pos[CFG_BUTTONS] = { [0 ... CFG_BUTTONS - 1] = CYCLE_NONE };

static inline bool cmd_is_cycle(const uint8_t *pRom){
	return (pRom[0] & 0xF0) == CMD_NO_CMD_NIBBLE && (pRom[0] & 0x0F) == CMD_CYCLE_MODE;
}

// Number of states of a list, 1 for a list without Cycle commands
static uint8_t cycle_states(const uint8_t *base){
	uint8_t n = 1;
	for(uint8_t j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		if(cmd_is_cycle(base + j * MIDI_ROM_CMD_SIZE)) n++;
	}
	return n;
}

// The Cycle command opening a state, or 0xFF for state 0 (or one past the last)
static uint8_t cycle_marker(const uint8_t *base, uint8_t state){
	if(state == 0) return 0xFF;
	for(uint8_t j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		if(cmd_is_cycle(base + j * MIDI_ROM_CMD_SIZE) && --state == 0) return j;
	}
	return 0xFF;
}

// First command of a state
static uint8_t cycle_first(const uint8_t *base, uint8_t state){
	uint8_t marker = cycle_marker(base, state);
	return (marker == 0xFF) ? 0 : (uint8_t)(marker + 1);
}

// Step a button of the current bank on to its next state and return the first
// command of that state; 0 for a button that does not cycle
static uint8_t cycle_advance(uint8_t i){
	const uint8_t *base = get_rom_pointer(switch_current_page, i, 0);
	uint8_t n = cycle_states(base);
	if(n == 1) return 0;
	uint8_t *pos = &cycle_pos[switch_current_page * MIDI_NUM_SWITCHES + i];
	*pos = (*pos == CYCLE_NONE || *pos + 1 >= n) ? 0 : (uint8_t)(*pos + 1);
	display_request_refresh();
	return cycle_first(base, *pos);
}

// First command of the state a button of the current bank last sent
static uint8_t cycle_current_first(uint8_t i){
	uint8_t pos = cycle_pos[switch_current_page * MIDI_NUM_SWITCHES + i];
	if(pos == CYCLE_NONE) return 0;
	return cycle_first(get_rom_pointer(switch_current_page, i, 0), pos);
}

const uint8_t *sw_button_label(uint8_t bank, uint8_t sw){
	uint16_t k = (uint16_t)(bank * MIDI_NUM_SWITCHES + sw);
	const uint8_t *own = pButtonLabels + k * BUTTON_LABEL_LEN;
	uint8_t pos = cycle_pos[k];
	if(pos == CYCLE_NONE) return own;
	const uint8_t *base = get_rom_pointer(bank, sw, 0);
	uint8_t marker = cycle_marker(base, pos);
	if(marker == 0xFF) return own;
	uint8_t index = base[marker * MIDI_ROM_CMD_SIZE + 1];
	if(index >= CYCLE_LABEL_COUNT) return own;	// CYCLE_NO_LABEL
	return pCycleLabels + index * BUTTON_LABEL_LEN;
}

static uint8_t bank_jump_step(void){
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_BANK_JUMP_STEP];
	if(v == 0 || v == 0xFF || v >= MIDI_NUM_BANKS) return 8;
	return v;
}

// A bank change requested by a command is applied only once the whole command
// list has run, so the remaining commands still come from the bank the button
// belongs to.
static uint8_t pending_bank = 0xFF;
// A configuration switch asked for by a Bank command: a slot, CONFIG_NEXT, or
// 0xFF for none. Applied once every button is released, see handle_switches.
static uint8_t pending_config = 0xFF;
// A Page command waiting for its list to finish: the bank holding the page, or
// 0xFF for none. See toggle_page().
static uint8_t pending_page = 0xFF;
/*
 * Second page of a bank: another bank shown in its place while the bank stays
 * the one the song is in. page_home is that bank while a page is shown, 0xFF
 * otherwise.
 */
static uint8_t page_home = 0xFF;
/*
 * The bank left by the last bank change, whoever asked for it: a button, the
 * computer or a command. A Bank command in Back mode returns to it, so a
 * detour to a utility bank costs one button there. 0xFF until the first
 * change, and a Back command then does nothing.
 */
static uint8_t previous_bank = 0xFF;

// Commands stored for "entering this bank"
static uint8_t* get_bank_enter_pointer(uint8_t bank, uint8_t cmd){
	return pBankEnterCmds + (MIDI_ROM_KEY_STRIDE * bank) + (MIDI_ROM_CMD_SIZE * cmd);
}

static inline bool cmd_is_exp(const uint8_t *pRom){
	return (pRom[0] & 0xF0) == CMD_NO_CMD_NIBBLE && (pRom[0] & 0x0F) == CMD_EXP_MODE;
}

// The 14 bit value the MMC and Song commands carry in their last two bytes
static inline uint16_t cmd_value14(const uint8_t *pRom){
	return (uint16_t)(pRom[2] & 0x7F) | ((uint16_t)(pRom[3] & 0x7F) << 7);
}

/*
 * Exp: point an expression pedal somewhere else. A toggling one does it while
 * its button is on and gives the pedal back its own target when switched off.
 */
static void send_exp(const uint8_t *pRom, uint8_t toggleState){
	uint8_t pedal = pRom[1] & 0x7F;
	if((pRom[1] & 0x80) && !toggleState){
		expression_set_target(pedal, EXP_TARGET_RESET, 0);
	} else {
		expression_set_target(pedal, pRom[2], pRom[3]);
	}
}

/*
 * What Exp commands have done lasts until the bank changes, and then the
 * pedals start from the new bank's own targets, overridden by the toggling
 * Exp commands of its buttons that are on. So the pedals always match the
 * LEDs, however the bank was left.
 */
static void exp_targets_for_bank(void){
	expression_clear_targets();
	for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++){
		if(!sw_button_is_toggle(switch_current_page, i)) continue;
		if(!get_sw_toggle_state(&a_sw_obj[i])) continue;
		for(uint8_t j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
			uint8_t *pRom = get_rom_pointer(switch_current_page, i, j);
			if(cmd_is_cycle(pRom)) break;
			if(cmd_is_exp(pRom) && (pRom[1] & 0x80)) send_exp(pRom, MIDI_CONTROL_ON);
		}
	}
}

// The bank the song is in: the one shown, or the one whose page is shown
static uint8_t home_bank(void){
	return (page_home != 0xFF) ? page_home : switch_current_page;
}

static void goto_bank(uint8_t bank){
	if(bank >= MIDI_NUM_BANKS) return;
	if(page_home == 0xFF && bank == switch_current_page) return;
	previous_bank = home_bank();
	if(page_home != 0xFF){
		// Leaving the bank from its page leaves the page first
		fire_bank_leave_cmds(switch_current_page);
		switch_current_page = page_home;
		page_home = 0xFF;
	}
	fire_bank_leave_cmds(switch_current_page);
	switch_current_page = bank;
	exp_targets_for_bank();
	update_leds_on_bank_change();
	display_setBankName(switch_current_page);
	state_store_mark_dirty();
	fire_bank_enter_cmds(bank);
}

static void show_page(uint8_t bank){
	switch_current_page = bank;
	update_leds_on_bank_change();
	display_showPage(bank);
	state_store_mark_dirty();
}

/*
 * Page: show another bank's buttons, names and labels in place of this one's,
 * and back again. It is not a bank change: the pedals keep what Exp commands
 * set, what the computer wrote stays on the display, Bank Up and Down move on
 * from the bank itself, and it is the bank that power on comes back to. Going
 * to the page sends its bank's enter commands, and coming back its leave
 * commands, so a page can switch something on the device and back.
 */
static void toggle_page(uint8_t target){
	if(page_home != 0xFF){
		uint8_t home = page_home;
		fire_bank_leave_cmds(switch_current_page);
		page_home = 0xFF;
		show_page(home);
	} else if(target < MIDI_NUM_BANKS && target != switch_current_page){
		page_home = switch_current_page;
		show_page(target);
		fire_bank_enter_cmds(target);
	}
}

// Requested from interrupt context; applied at the top of handle_switches.
static volatile uint8_t requested_bank = 0xFF;

void sw_request_bank(uint8_t bank){
	if(bank < MIDI_NUM_BANKS) requested_bank = bank;
}

/*
 * Setlist: when enabled, relative bank moves follow a stored order instead of
 * the bank numbers. The list ends at the first entry that is not a valid bank,
 * so erased flash (0xFF) is simply an empty list. Absolute jumps (GoTo, bank
 * change from MIDI) are unaffected.
 */
static uint8_t setlist_len(void){
	if(pGlobalSettings[GLOBAL_SETTINGS_SETLIST_MODE] != 1) return 0;
	uint8_t n = 0;
	while(n < SETLIST_MAX && pSetlist[n] < MIDI_NUM_BANKS) n++;
	return n;
}

static uint8_t setlist_step(uint8_t n, int16_t delta){
	int16_t idx = -1;
	for(uint8_t i=0; i<n; i++){
		if(pSetlist[i] == home_bank()){ idx = i; break; }
	}
	// Off the list: Up enters at the start, Down at the end
	if(idx < 0) return pSetlist[(delta >= 0) ? 0 : n - 1];
	int16_t j = idx + delta;
	while(j < 0) j += n;
	while(j >= n) j -= n;
	return pSetlist[j];
}

// Step through the banks, wrapping around at both ends
static uint8_t bank_step(int16_t delta){
	uint8_t n = setlist_len();
	if(n) return setlist_step(n, delta);

	int16_t b = (int16_t)home_bank() + delta;
	while(b < 0) b += MIDI_NUM_BANKS;
	while(b >= MIDI_NUM_BANKS) b -= MIDI_NUM_BANKS;
	return (uint8_t)b;
}

static uint32_t long_press_threshold_ms(void){
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_LONG_PRESS];
	if(v == 0 || v == 0xFF) return 500;
	return (uint32_t)v * 10;
}

// How long after a tap a second press still makes it a double press
static uint32_t double_press_window_ms(void){
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_DOUBLE_PRESS];
	if(v == 0 || v == 0xFF) return 300;
	return (uint32_t)v * 10;
}

static inline uint8_t sanitize_led_mode(uint8_t mode){
	// Erased flash (0xFF) or any unknown value falls back to Normal
	return (mode <= LED_MODE_ALWAYS_ON) ? mode : LED_MODE_NORMAL;
}

// 0=Normal, 1=Reverse, 2=AlwaysOn(Blink), read from the per-button LED mode table
uint8_t get_button_led_mode(uint8_t sw){
	uint8_t v = pButtonLedModes[switch_current_page * MIDI_NUM_SWITCHES + sw];
	if(v == 0xFF) return LED_MODE_NORMAL;
	return sanitize_led_mode(v & LED_MODE_MASK);
}

// Exclusive group of a button of the current bank, 0 for none. Shares the
// LED mode byte, whose top bits older configurations always left at zero.
static uint8_t get_button_group(uint8_t sw){
	uint8_t v = pButtonLedModes[switch_current_page * MIDI_NUM_SWITCHES + sw];
	if(v == 0xFF) return 0;
	return (v >> BUTTON_GROUP_SHIFT) & BUTTON_GROUP_MASK;
}

// Whether a button of the current bank asks its LED to flash at the tempo,
// as a Tap button's does. Shares the LED mode byte, in a bit older
// configurations always left at zero.
static bool get_button_tempo_flash(uint8_t sw){
	uint8_t v = pButtonLedModes[switch_current_page * MIDI_NUM_SWITCHES + sw];
	if(v == 0xFF) return false;
	return (v & BUTTON_TEMPO_FLASH) != 0;
}

uint8_t get_bank_down_led_mode(){ // SW_E is Bank Down
	return sanitize_led_mode(pGlobalSettings[5]);
}

uint8_t get_bank_up_led_mode(){ // SW_5 is Bank Up
	return sanitize_led_mode(pGlobalSettings[4]);
}

// Helper to determine LED state based on Mode and Press state
// pressed: 1 if button is held down (physically)
// mode: 0=Normal, 1=Reverse, 2=AlwaysOn
// Brightness level (0..LEDS_LEVELS) an LED should have given whether its
// button is active and its light mode. "Lit at rest" (Reverse/AlwaysOn while
// inactive) uses the rest brightness so it can be dimmer than an active LED.
uint8_t calculate_led_state(uint8_t pressed, uint8_t mode){
	uint32_t tick = HAL_GetTick();
	uint8_t blink_on = ((tick % 200) < 100) ? 1 : 0; // 50% duty, 200ms period

	if(mode == 2){ // AlwaysOn: lit at rest, blinks while active
		return pressed ? (blink_on ? leds_level_active() : 0) : leds_level_rest();
	} else if (mode == 1){ // Reverse: lit at rest, off while active
		return pressed ? 0 : leds_level_rest();
	} else { // Normal
		return pressed ? leds_level_active() : 0;
	}
}

// Note a Tap command in any of a button's lists, for the beat flash
static void note_tap_cmd(sw_t *sw, uint8_t page, const uint8_t *pCmd){
	if((pCmd[0] & 0xF0) != CMD_TAP_NIBBLE) return;
	switch(pCmd[0] & 0x0F){
	case TAP_MODE_TAP:   sw->tap_blink |= (1UL<<page); break;
	case TAP_MODE_CLOCK: sw->clock_blink |= (1UL<<page); break;
	default: break;	// setting the tempo is no reason to flash
	}
}

static void tap_led_task(void);

void sw_led_init(void){
	// Scan all commands in EEPROM, and build the table of whether the LED should toggle with the switch, or be momentary
	for(int page=0; page<MIDI_NUM_BANKS; page++){
		for(int sw=0; sw<8; sw++){
			// Clear the toggle bit
			a_sw_obj[sw].led_cmd_toggle &= ~(1UL<<page);
			a_sw_obj[sw].tap_blink &= ~(1UL<<page);
			a_sw_obj[sw].clock_blink &= ~(1UL<<page);

			for(int cmd=0; cmd<MIDI_NUM_COMMANDS_PER_SWITCH; cmd++){
				uint8_t *pCmd = get_rom_pointer(page, sw, cmd);
				if(midiCmd_get_cmd_toggle(pCmd)){
					a_sw_obj[sw].led_cmd_toggle |= (1UL<<page);
				}
				note_tap_cmd(&a_sw_obj[sw], page, pCmd);
			}

			// Same for the long press command set
			a_sw_obj[sw].long_cmd_present &= ~(1UL<<page);
			a_sw_obj[sw].long_cmd_toggle &= ~(1UL<<page);
			for(int cmd=0; cmd<MIDI_NUM_COMMANDS_PER_SWITCH; cmd++){
				uint8_t *pCmd = get_long_rom_pointer(page, sw, cmd);
				note_tap_cmd(&a_sw_obj[sw], page, pCmd);
				if(cmd_is_present(pCmd)){
					a_sw_obj[sw].long_cmd_present |= (1UL<<page);
					if(midiCmd_get_cmd_toggle(pCmd)){
						a_sw_obj[sw].long_cmd_toggle |= (1UL<<page);
					}
				}
			}

			// And the double press set, which lives in the extension area and
			// only counts when the tools wrote it for this configuration
			a_sw_obj[sw].double_cmd_present &= ~(1UL<<page);
			a_sw_obj[sw].double_cmd_toggle &= ~(1UL<<page);
			if(flash_settings_double_stored()){
				for(int cmd=0; cmd<MIDI_NUM_COMMANDS_PER_SWITCH; cmd++){
					uint8_t *pCmd = get_double_rom_pointer(page, sw, cmd);
					note_tap_cmd(&a_sw_obj[sw], page, pCmd);
					if(cmd_is_present(pCmd)){
						a_sw_obj[sw].double_cmd_present |= (1UL<<page);
						if(midiCmd_get_cmd_toggle(pCmd)){
							a_sw_obj[sw].double_cmd_toggle |= (1UL<<page);
						}
					}
				}
			}
			a_sw_obj[sw].press_state = PRESS_IDLE;
		}
	}

	ccinc_reset();
	pending_clear();

	// Init all delayed cmds to off
	for(int i=0; i<MAX_DELAYED_CMDS; i++){
		delayed_cmds[i].systick_timout = UINT32_MAX;
	}

	// Init all the LEDs based on current page (0) and settings
	update_leds_on_bank_change();
}


/*
 * Functions for the command duration, i.e. delay until switching a cmd/note/pb off.
 */
int get_available_delayed_cmd_slot(void){
	for(int i=0; i<MAX_DELAYED_CMDS; i++){
		if(delayed_cmds[i].systick_timout == UINT32_MAX){
			return i;
		}
	}

	return -1;
}

void handle_delayed_cmds(void){
	for(int i=0; i<MAX_DELAYED_CMDS; i++){
		if(delayed_cmds[i].systick_timout < HAL_GetTick()){
			uint8_t* pRom = delayed_cmds[i].pRomCmd;
			switch(*pRom & 0xF0){
			case CMD_PB_NIBBLE:
				midiCmd_send_pb_command_from_rom(pRom, MIDI_CONTROL_OFF);
				break;
			case CMD_NOTE_NIBBLE:
				midiCmd_send_note_command_from_rom(pRom, MIDI_CONTROL_OFF);
				break;
			case CMD_KEY_NIBBLE:
				update_keyboard_state(pRom[1], pRom[2], 0); // Release
				break;
			case CMD_MEDIA_NIBBLE:
				send_media_usage(0); // Release
				break;
			default:
				break;
			}
			delayed_cmds[i].systick_timout = UINT32_MAX;
		}
	}
}

// Sets the cmd point to switch off and the delay timeout into the delayed cmds table
void set_cmd_duration_delay(uint8_t *pRom){
	int slot = get_available_delayed_cmd_slot();
	if(slot >= 0){
		delayed_cmds[slot].pRomCmd = pRom;
		delayed_cmds[slot].systick_timout = HAL_GetTick() + midiCmd_get_delay(pRom);
	}
}

void handle_cmd_sw_down(uint8_t *pRom, uint8_t toggleState){
	/*
	 * Assume success by default since this was the behavior before adding this status.
	 */
	int8_t status = 0;

	switch(*pRom & 0xF0){
	case CMD_PC_NIBBLE:
		if(PC_IS_RELATIVE(pRom[2])){
			send_pc_relative(pRom, false);
		} else {
			status = midiCmd_send_pc_command_from_rom(pRom);
			sw_note_program(pRom[0], pRom[1]);
		}
		break;
	case CMD_CC_NIBBLE:
		if(midiCmd_get_cmd_toggle(pRom)){
			status = midiCmd_send_cc_command_from_rom(pRom, toggleState);
		} else {
			// Not toggling, so set command and either set a duration or not
			status = midiCmd_send_cc_command_from_rom(pRom, MIDI_CONTROL_ON);
		}
		break;
	case CMD_PB_NIBBLE:
		if(midiCmd_get_cmd_toggle(pRom)){
			status = midiCmd_send_pb_command_from_rom(pRom, toggleState);
		} else {
			// Not toggling, so set command and either set a duration or not
			status = midiCmd_send_pb_command_from_rom(pRom, MIDI_CONTROL_ON);
			if(midiCmd_get_delay(pRom) != 0){
				set_cmd_duration_delay(pRom);
			}
		}
		break;
	case CMD_NOTE_NIBBLE:
		if(midiCmd_get_cmd_toggle(pRom)){
			status = midiCmd_send_note_command_from_rom(pRom, toggleState);
		} else {
			// Not toggling, so set command and either set a duration or not
			status = midiCmd_send_note_command_from_rom(pRom, MIDI_CONTROL_ON);
			if(midiCmd_get_delay(pRom) != 0){
				set_cmd_duration_delay(pRom);
			}
		}
		break;
	case CMD_KEY_NIBBLE:
    {
        // Key Mode Logic
        // Mode is stored in the lower nibble of Byte 0
        uint8_t key_mode = pRom[0] & 0x0F;
        uint32_t delay_val = midiCmd_get_delay(pRom);

		if(midiCmd_get_cmd_toggle(pRom)){
			// Toggle Logic (Valid for Normal Mode 0 only mostly?)
			update_keyboard_state(pRom[1], pRom[2], toggleState);
		} else {
            // Momentary / Manual Logic based on Mode
            if (key_mode == 1) { // Down Only
                if (delay_val > 0) HAL_Delay(delay_val); // Blocking Pre-Delay
                update_keyboard_state(pRom[1], pRom[2], 1); // Press
            } 
            else if (key_mode == 2) { // Up Only
                if (delay_val > 0) HAL_Delay(delay_val); // Blocking Pre-Delay
                update_keyboard_state(pRom[1], pRom[2], 0); // Release
            }
            else { // Mode 0: Normal Momentary (Pulse)
                // Immediate Press
			    update_keyboard_state(pRom[1], pRom[2], 1); 
                // Auto Release after Duration
			    if(delay_val != 0){
				    set_cmd_duration_delay(pRom);
			    }
            }
		}
    }
		break;
	case CMD_MEDIA_NIBBLE:
		if(midiCmd_get_cmd_toggle(pRom)){
			// Hold: press on one press, release on the next
			send_media_usage(toggleState ? media_usage_from_rom(pRom) : 0);
		} else {
			send_media_usage(media_usage_from_rom(pRom));
			if(midiCmd_get_delay(pRom) != 0){
				set_cmd_duration_delay(pRom); // auto release
			}
		}
		break;
	case CMD_CCINC_NIBBLE:
		send_ccinc(pRom, false);
		break;
	case CMD_TAP_NIBBLE:
		send_tap(pRom);
		break;
	case CMD_SYSEX_NIBBLE:
		send_stored_sysex(pRom);
		break;
	case CMD_BANK_NIBBLE:
		// Applied after the command list finishes (see pending_bank)
		switch(*pRom & 0x0F){
		case 1:  pending_bank = bank_step(+(int16_t)pRom[1]); break;
		case 2:  pending_bank = bank_step(-(int16_t)pRom[1]); break;
		case BANK_MODE_CONFIG:      pending_config = (pRom[1] < CONFIG_SLOTS) ? pRom[1] : 0xFF; break;
		case BANK_MODE_NEXT_CONFIG: pending_config = CONFIG_NEXT; break;
		case BANK_MODE_PAGE:        pending_page = pRom[1] & 0x7F; break;
		case BANK_MODE_BACK:        pending_bank = previous_bank; break;
		default: pending_bank = (pRom[1] < MIDI_NUM_BANKS) ? pRom[1] : 0xFF; break;
		}
		break;
	case CMD_START_NIBBLE:
		status = midiCmd_send_start_command();
		break;
	case CMD_STOP_NIBBLE:
		status = midiCmd_send_stop_command();
		break;
	case CMD_PANIC_NIBBLE:
		ramp_stop_all();	// or a ramp or LFO would bring the sound back
		lfo_stop_all();
		status = midiCmd_send_panic();
		break;
	case CMD_SCENE_NIBBLE:
		apply_scene(pRom[1], pRom[2]);
		break;
	case CMD_NO_CMD_NIBBLE:
		switch(*pRom & 0x0F){
		case CMD_EXP_MODE:
			send_exp(pRom, toggleState);
			break;
		case CMD_MMC_MODE:
			status = midiCmd_send_mmc(pRom[1], cmd_value14(pRom));
			break;
		case CMD_SONG_MODE:
			if(pRom[1] == SONG_POSITION){
				status = midiCmd_send_song_position(cmd_value14(pRom));
			} else {
				status = midiCmd_send_song_select(cmd_value14(pRom) & 0x7F);
			}
			break;
		default:
			break;
		}
		break;
	default:
		break;
	}

	/*
	 * A full transmit buffer used to call Error(), which disables interrupts
	 * and spins forever: the pedal froze until it was power cycled. Dropping
	 * the message is the right answer for a MIDI stream, so the status is
	 * deliberately ignored here.
	 */
	(void)status;
}

void handle_cmd_sw_up(uint8_t *pRom, uint8_t toggleState){
	/*
	 * Assume success by default since this was the behavior before adding this status.
	 */
	int8_t status = 0;

	switch(*pRom & 0xF0){
	case CMD_PC_NIBBLE:
		break;
	case CMD_CC_NIBBLE:
		if(!midiCmd_get_cmd_toggle(pRom)){
			status = midiCmd_send_cc_command_from_rom(pRom, MIDI_CONTROL_OFF);
		}
		break;
	case CMD_PB_NIBBLE:
		if(!midiCmd_get_cmd_toggle(pRom)) {
			if(midiCmd_get_delay(pRom) == 0) {
				// No cmd duration delay, so immediately release
				status = midiCmd_send_pb_command_from_rom(pRom, MIDI_CONTROL_OFF);
			}
		}
		break;
	case CMD_NOTE_NIBBLE:
		if(!midiCmd_get_cmd_toggle(pRom)) {
			if(midiCmd_get_delay(pRom) == 0) {
				// No cmd duration delay, so immediately release
				status = midiCmd_send_note_command_from_rom(pRom, MIDI_CONTROL_OFF);
			}
		}
		break;
	case CMD_KEY_NIBBLE:
		if(!midiCmd_get_cmd_toggle(pRom)) {
			if(midiCmd_get_delay(pRom) == 0) {
				// No cmd duration delay, so immediately release
				update_keyboard_state(pRom[1], pRom[2], 0); // Release
			}
		}
		break;
	case CMD_MEDIA_NIBBLE:
		if(!midiCmd_get_cmd_toggle(pRom) && midiCmd_get_delay(pRom) == 0) {
			send_media_usage(0); // Release
		}
		break;
	case CMD_START_NIBBLE:
		break;
	case CMD_STOP_NIBBLE:
		break;
	default:
		break;
	}

	/*
	 * A full transmit buffer used to call Error(), which disables interrupts
	 * and spins forever: the pedal froze until it was power cycled. Dropping
	 * the message is the right answer for a MIDI stream, so the status is
	 * deliberately ignored here.
	 */
	(void)status;
}

void set_led(uint8_t sw_no, uint8_t level){
	leds_set(sw_no, level);
}

// The button that goes back from a page stays lit while the page is shown
static uint8_t page_led_on(uint8_t i){
	if(page_home == 0xFF) return 0;
	for(uint8_t j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		const uint8_t *pRom = get_rom_pointer(switch_current_page, i, j);
		if(pRom[0] == (CMD_BANK_NIBBLE | BANK_MODE_PAGE)) return 1;
	}
	return 0;
}

void update_leds_on_bank_change(void){
	for(int i=0; i<8; i++){
		if(a_sw_obj[i].led_cmd_toggle & (1UL<<switch_current_page)){
			uint8_t mode = get_button_led_mode(i);
			uint8_t active = get_sw_toggle_state(&a_sw_obj[i]);
			uint8_t state = calculate_led_state(active, mode);
			set_led(i, state);
		} else {
			// Update based on mode (assuming released state)
			uint8_t mode = get_button_led_mode(i);
			// For update, we assume Not Pressed. 
			// If AlwaysOn -> ON. If Reverse -> ON. Normal -> OFF.
			uint8_t state = calculate_led_state(page_led_on(i), mode);
			set_led(i, state);
		}
	}
	
	// Also update Bank LEDs initial state
	{
		uint8_t mode_down = get_bank_down_led_mode();
		// SW_E Down
		uint8_t state = calculate_led_state(0, mode_down);
		leds_set(LED_ID_BANK_DOWN, state);
		
		uint8_t mode_up = get_bank_up_led_mode();
		// SW_5 Up
		state = calculate_led_state(0, mode_up);
		leds_set(LED_ID_BANK_UP, state);
	}
}

/*
 * Commands sent once when a bank is entered, typically a Program Change that
 * selects the patch for that bank. They are one-shot: no release is sent, and
 * Bank commands are ignored so entering a bank cannot chain into another one.
 */
static void fire_bank_enter_cmds(uint8_t bank){
	if(bank >= MIDI_NUM_BANKS) return;
	run_cmd_list(get_bank_enter_pointer(bank, 0), 0, 0, MIDI_CONTROL_ON,
			PENDING_OWNER_NONE, LIST_SKIP_BANK, true);
}

static inline bool cmd_is_leave(const uint8_t *pRom){
	return (pRom[0] & 0xF0) == CMD_NO_CMD_NIBBLE && (pRom[0] & 0x0F) == CMD_LEAVE_MODE;
}

/*
 * Commands sent on leaving a bank: those below a Leave command in its enter
 * list. They go out just before the next bank's enter commands, straight
 * through: a pause among them is skipped, so the two lists never overlap. A
 * pause at the top of the next bank's enter list spaces them out instead.
 */
static void fire_bank_leave_cmds(uint8_t bank){
	if(bank >= MIDI_NUM_BANKS) return;
	uint8_t *base = get_bank_enter_pointer(bank, 0);
	for(uint8_t j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		if(cmd_is_leave(base + j * MIDI_ROM_CMD_SIZE)){
			run_cmd_list(base, 0, (uint8_t)(j + 1), MIDI_CONTROL_ON,
					PENDING_OWNER_NONE, LIST_SKIP_BANK, false);
			return;
		}
	}
}

static void apply_pending_bank(void){
	if(pending_page != 0xFF){
		uint8_t target = pending_page;
		pending_page = 0xFF;
		if(pending_bank == 0xFF) toggle_page(target);	// a bank change wins
	}
	if(pending_bank != 0xFF){
		uint8_t target = pending_bank;
		pending_bank = 0xFF;
		goto_bank(target);
	}
}

/*
 * Wait: a command that pauses the rest of its list instead of sending
 * anything, for the device that drops a CC arriving right behind a Program
 * Change. The pedal cannot stop and count: a button held down, the expression
 * pedal and the display all have to keep working, so a list that reaches a
 * Wait stops there and pending_task picks up the rest once the time is up.
 *
 * A button released while its list is still waiting has its release pass held
 * back until the list finishes, so nothing is switched off before it has been
 * sent. Pressing the same button again runs whatever is left at once: a new
 * press always starts from a finished list.
 */
#define PENDING_LISTS		(4)

typedef struct {
	uint8_t *base;		// first command of the list
	uint8_t first;		// first command of the part that fired, for the release pass
	uint32_t due;		// HAL tick when the rest of it runs
	uint8_t next;		// index of the command to run next
	uint8_t toggle;		// toggle state the list was fired with
	uint8_t owner;		// button waiting to be released, or PENDING_OWNER_NONE
	uint8_t flags;
	bool release_pending;	// the button was let go while the list was waiting
	bool active;
} pending_list_t;

static pending_list_t pending_lists[PENDING_LISTS];

static inline bool cmd_is_wait(const uint8_t *pRom){
	return (pRom[0] & 0xF0) == CMD_NO_CMD_NIBBLE && (pRom[0] & 0x0F) == CMD_WAIT_MODE;
}

static bool pending_schedule(uint8_t *base, uint8_t first, uint8_t next, uint8_t toggle,
		uint8_t owner, uint8_t flags, uint32_t ms){
	for(uint8_t i=0; i<PENDING_LISTS; i++){
		pending_list_t *p = &pending_lists[i];
		if(p->active) continue;
		p->base = base;
		p->first = first;
		p->due = HAL_GetTick() + ms;
		p->next = next;
		p->toggle = toggle;
		p->owner = owner;
		p->flags = flags;
		p->release_pending = false;
		p->active = true;
		return true;
	}
	return false;	// every slot busy: the rest of the list runs without pausing
}

static bool pending_defer_release(uint8_t owner){
	for(uint8_t i=0; i<PENDING_LISTS; i++){
		if(pending_lists[i].active && pending_lists[i].owner == owner){
			pending_lists[i].release_pending = true;
			return true;
		}
	}
	return false;
}

// Run what is left of a button's list now, pauses collapsed, so a new press
// never overlaps the previous one
static void pending_flush_owner(uint8_t owner){
	for(uint8_t i=0; i<PENDING_LISTS; i++){
		pending_list_t *p = &pending_lists[i];
		if(!p->active || p->owner != owner) continue;
		pending_list_t run = *p;
		p->active = false;
		run_cmd_list(run.base, run.first, run.next, run.toggle, run.owner, run.flags, false);
		if(run.release_pending) run_list_up(run.base, run.first, run.toggle, run.flags);
	}
}

static bool pending_any(void){
	for(uint8_t i=0; i<PENDING_LISTS; i++){
		if(pending_lists[i].active) return true;
	}
	return false;
}

static void pending_clear(void){
	for(uint8_t i=0; i<PENDING_LISTS; i++) pending_lists[i].active = false;
}

static void pending_task(void){
	uint32_t now = HAL_GetTick();
	for(uint8_t i=0; i<PENDING_LISTS; i++){
		pending_list_t *p = &pending_lists[i];
		if(!p->active || (int32_t)(now - p->due) < 0) continue;
		pending_list_t run = *p;
		p->active = false;	// free the slot: the rest of the list may need it
		if(run_cmd_list(run.base, run.first, run.next, run.toggle, run.owner, run.flags, true)){
			if(run.release_pending) run_list_up(run.base, run.first, run.toggle, run.flags);
		} else if(run.release_pending){
			pending_defer_release(run.owner);	// another Wait: the release waits too
		}
	}
}

/*
 * Ramp: a command that sends nothing itself but turns the CC command right
 * below it into a ramp. Instead of jumping to its value, the CC walks there
 * over the ramp's time: on the way to On when the button is pressed (or a
 * toggle switched on), on the way to Off when it is released (or switched
 * off). Like a Wait, the pedal does not stop while it runs; ramp_task sends
 * the steps from the main loop.
 *
 * A ramp starts from the other end of the command, Off on the way to On and
 * the other way round, so a swell always sounds the same. A ramp started on a
 * channel and CC already ramping starts where that one got to instead, so
 * pressing again halfway turns it round without a jump.
 */
#define RAMP_SLOTS		(8)
#define RAMP_STEP_MS	(5)	// at most one message per ramp this often

typedef struct {
	uint32_t start;		// HAL tick the ramp started
	uint32_t ms;		// its whole time
	uint32_t last_tick;	// when the last step went out
	uint8_t channel;
	uint8_t cc;
	uint8_t from;
	uint8_t to;
	uint8_t value;		// last value sent
	bool active;
} ramp_t;

static ramp_t ramps[RAMP_SLOTS];

static inline bool cmd_is_ramp(const uint8_t *pRom){
	return (pRom[0] & 0xF0) == CMD_NO_CMD_NIBBLE && (pRom[0] & 0x0F) == CMD_RAMP_MODE;
}

static uint32_t ramp_time_ms(const uint8_t *pRom){
	return ((uint32_t)pRom[2] | ((uint32_t)pRom[3] << 8)) * 10;
}

static void ramp_stop_all(void){
	for(uint8_t i=0; i<RAMP_SLOTS; i++) ramps[i].active = false;
}

static void ramp_stop(uint8_t channel, uint8_t cc){
	for(uint8_t i=0; i<RAMP_SLOTS; i++){
		if(ramps[i].channel == channel && ramps[i].cc == cc) ramps[i].active = false;
	}
}

static uint8_t ramp_value_at(const ramp_t *r, uint32_t now){
	uint32_t elapsed = now - r->start;
	if(elapsed >= r->ms) return r->to;
	int32_t span = (int32_t)r->to - (int32_t)r->from;
	int32_t step = (span * (int32_t)elapsed * 2 + (span >= 0 ? (int32_t)r->ms : -(int32_t)r->ms))
			/ (2 * (int32_t)r->ms);	// rounded to the nearest value
	return (uint8_t)((int32_t)r->from + step);
}

/*
 * The CC command pRom, on its way to On (on = 1) or Off, as a ramp of ms.
 * Off above 127 means the command has no off value: nothing to ramp to, and
 * on the way to On such a command starts from 0.
 */
static void ramp_cc(const uint8_t *pRom, uint8_t on, uint32_t ms){
	uint8_t channel = pRom[0] & 0x0F;
	uint8_t cc = pRom[1] & 0x7F;
	bool has_off = pRom[3] <= 0x7F;
	if(!on && !has_off) return;
	lfo_stop(channel, cc);	// the ramp takes over the CC
	uint8_t to = on ? (pRom[2] & 0x7F) : pRom[3];
	uint8_t from = on ? (has_off ? pRom[3] : 0) : (pRom[2] & 0x7F);

	uint32_t now = HAL_GetTick();
	ramp_t *r = NULL;
	bool running = false;
	for(uint8_t i=0; i<RAMP_SLOTS; i++){
		if(ramps[i].active && ramps[i].channel == channel && ramps[i].cc == cc){
			r = &ramps[i];
			running = true;
			from = r->value;	// carry on from where it got to
			break;
		}
	}
	for(uint8_t i=0; r == NULL && i<RAMP_SLOTS; i++){
		if(!ramps[i].active) r = &ramps[i];
	}

	if(r == NULL || ms == 0 || from == to){
		// No time, nowhere to go or every slot busy: straight to the value
		if(r != NULL && running) r->active = false;
		midiCmd_send_cc(channel, cc, to);
		return;
	}

	r->start = now;
	r->ms = ms;
	r->last_tick = now;
	r->channel = channel;
	r->cc = cc;
	r->from = from;
	r->to = to;
	r->value = from;
	r->active = true;
	if(!running) midiCmd_send_cc(channel, cc, from);	// the device may be elsewhere
}

static void ramp_task(void){
	uint32_t now = HAL_GetTick();
	for(uint8_t i=0; i<RAMP_SLOTS; i++){
		ramp_t *r = &ramps[i];
		if(!r->active) continue;
		bool done = (now - r->start) >= r->ms;
		if(!done && (now - r->last_tick) < RAMP_STEP_MS) continue;
		uint8_t v = ramp_value_at(r, now);
		if(v != r->value){
			midiCmd_send_cc(r->channel, r->cc, v);
			r->value = v;
			r->last_tick = now;
		}
		if(done) r->active = false;
	}
}

/*
 * LFO: like a Ramp, a command that sends nothing itself but turns the CC
 * command right below it into an LFO: while the button is held (or the toggle
 * is on) the CC swings between its Off and On values by itself, one cycle per
 * note division of the tempo, and on release (or switched off) it stops and
 * the CC gets its Off value as usual. A CC with no Off value swings from 0.
 *
 * The LFO is locked to the beat the tap LED shows, the host's clock while it
 * is followed: every cycle starts on a beat, counted from the beat of the
 * press, so a new tap or tempo is followed straight away. The shapes start
 * from the bottom (Sine, Triangle, Saw up), the top (Saw down, Square) or a
 * random value, which changes once a cycle.
 *
 * An LFO keeps running when the bank changes, like any CC the button left on,
 * and the toggled ones start again after a power cycle.
 */
#define LFO_SLOTS		(8)
#define LFO_STEP_MS		(5)		// at most one message per LFO this often
#define LFO_SHAPE_MAX	(1000)	// full swing of a shape

typedef struct {
	uint32_t start_beat;	// beat the LFO started on
	uint32_t last_tick;		// when the last step went out
	uint32_t last_pos;		// position in the cycle at the last step
	uint16_t div;			// cycle length, in 24ths of a beat
	uint8_t channel;
	uint8_t cc;
	uint8_t lo;				// value at the bottom of the shape
	uint8_t hi;				// and at the top
	uint8_t shape;
	uint8_t value;			// last value sent
	uint16_t random;		// the Random shape's value for this cycle
	bool active;
} lfo_t;

static lfo_t lfos[LFO_SLOTS];
static const uint16_t lfo_div_ticks[LFO_DIV_COUNT] = LFO_DIV_TICKS;

// sin^2 over half a cycle, the bottom-to-top half of the Sine shape
static const uint16_t lfo_sine[33] = {
	0, 2, 10, 22, 38, 59, 84, 113, 146, 183, 222, 264, 309, 355, 402, 451,
	500, 549, 598, 645, 691, 736, 778, 817, 854, 887, 916, 941, 962, 978, 990, 998, 1000
};

static uint16_t lfo_rand(void){
	static uint32_t x = 2463534242UL;
	x ^= x << 13;
	x ^= x >> 17;
	x ^= x << 5;
	return (uint16_t)(x % (LFO_SHAPE_MAX + 1));
}

static inline bool cmd_is_lfo(const uint8_t *pRom){
	return (pRom[0] & 0xF0) == CMD_NO_CMD_NIBBLE && (pRom[0] & 0x0F) == CMD_LFO_MODE;
}

// Where the LFO is in its cycle, in thousandths of a clock (24th of a beat)
static uint32_t lfo_pos(const lfo_t *l){
	uint32_t beat, ms;
	tempo_beat_now(&beat, &ms);
	if(ms > 60000) ms = 60000;
	uint32_t frac = ms * tempo_get_bpm() * 2 / 5;	// ms * bpm * 24000 / 60000
	if(frac > 23999) frac = 23999;	// a late beat: wait for it at the end
	uint32_t pos = ((beat - l->start_beat) % l->div) * 24000 + frac;
	return pos % ((uint32_t)l->div * 1000);
}

// The shape at pos, 0 at the bottom to LFO_SHAPE_MAX at the top
static uint16_t lfo_shape_at(const lfo_t *l, uint32_t pos){
	uint32_t period = (uint32_t)l->div * 1000;
	uint32_t x = pos * 1024 / period;	// 0-1023 through the cycle
	switch(l->shape){
	case LFO_SHAPE_SINE: {
		uint32_t h = x < 512 ? x : 1023 - x;	// mirrored halves, 0-511
		uint32_t i = h >> 4, f = h & 15;
		return (uint16_t)(lfo_sine[i] + ((lfo_sine[i + 1] - lfo_sine[i]) * f + 8) / 16);
	}
	case LFO_SHAPE_TRIANGLE:
		return (uint16_t)((x < 512 ? x : 1023 - x) * LFO_SHAPE_MAX / 511);
	case LFO_SHAPE_SAW_UP:
		return (uint16_t)(x * LFO_SHAPE_MAX / 1023);
	case LFO_SHAPE_SAW_DOWN:
		return (uint16_t)(LFO_SHAPE_MAX - x * LFO_SHAPE_MAX / 1023);
	case LFO_SHAPE_SQUARE:
		return x < 512 ? LFO_SHAPE_MAX : 0;
	case LFO_SHAPE_RANDOM:
	default:
		return l->random;
	}
}

static uint8_t lfo_value(const lfo_t *l, uint32_t pos){
	int32_t span = (int32_t)l->hi - (int32_t)l->lo;
	int32_t v = span * lfo_shape_at(l, pos);
	v = (v + (v >= 0 ? LFO_SHAPE_MAX / 2 : -LFO_SHAPE_MAX / 2)) / LFO_SHAPE_MAX;
	return (uint8_t)((int32_t)l->lo + v);
}

static void lfo_send(lfo_t *l, uint32_t pos){
	uint8_t v = lfo_value(l, pos);
	if(v != l->value){
		midiCmd_send_cc(l->channel, l->cc, v);
		l->value = v;
	}
	l->last_pos = pos;
	l->last_tick = HAL_GetTick();
}

// The CC command pRom as an LFO, with the division and shape of the LFO lfo
static void lfo_start(const uint8_t *lfo, const uint8_t *pRom){
	uint8_t channel = pRom[0] & 0x0F;
	uint8_t cc = pRom[1] & 0x7F;
	lfo_t *l = NULL;
	for(uint8_t i=0; i<LFO_SLOTS; i++){
		if(lfos[i].active && lfos[i].channel == channel && lfos[i].cc == cc){
			l = &lfos[i];	// the same CC again: start over
			break;
		}
	}
	for(uint8_t i=0; l == NULL && i<LFO_SLOTS; i++){
		if(!lfos[i].active) l = &lfos[i];
	}
	if(l == NULL){
		// Every slot busy: an ordinary CC
		midiCmd_send_cc(channel, cc, pRom[2] & 0x7F);
		return;
	}
	ramp_stop(channel, cc);

	uint32_t ms;
	tempo_beat_now(&l->start_beat, &ms);
	l->div = lfo_div_ticks[lfo[2] < LFO_DIV_COUNT ? lfo[2] : LFO_DIV_COUNT - 1];
	l->channel = channel;
	l->cc = cc;
	l->hi = pRom[2] & 0x7F;
	l->lo = pRom[3] <= 0x7F ? pRom[3] : 0;
	l->shape = lfo[3] < LFO_SHAPE_COUNT ? lfo[3] : LFO_SHAPE_SINE;
	l->random = lfo_rand();
	l->value = 0xFF;	// the first value always goes out
	l->active = true;
	lfo_send(l, lfo_pos(l));
}

static void lfo_stop(uint8_t channel, uint8_t cc){
	for(uint8_t i=0; i<LFO_SLOTS; i++){
		if(lfos[i].channel == channel && lfos[i].cc == cc) lfos[i].active = false;
	}
}

static void lfo_stop_all(void){
	for(uint8_t i=0; i<LFO_SLOTS; i++) lfos[i].active = false;
}

static void lfo_task(void){
	uint32_t now = HAL_GetTick();
	for(uint8_t i=0; i<LFO_SLOTS; i++){
		lfo_t *l = &lfos[i];
		if(!l->active || (now - l->last_tick) < LFO_STEP_MS) continue;
		uint32_t pos = lfo_pos(l);
		if(pos < l->last_pos) l->random = lfo_rand();	// a new cycle
		lfo_send(l, pos);
	}
}

/*
 * After a power cycle: the LFOs of the toggle buttons that are on, in every
 * bank, run again, so the sound matches the LEDs.
 */
static void lfo_restart_all(void){
	lfo_stop_all();
	for(uint8_t b=0; b<MIDI_NUM_BANKS; b++){
		for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++){
			if(!sw_button_is_toggle(b, i) || !sw_get_toggle_state(b, i)) continue;
			const uint8_t *prev = NULL;
			for(uint8_t j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
				uint8_t *pRom = get_rom_pointer(b, i, j);
				if(cmd_is_cycle(pRom)) break;
				if(prev && (*pRom & 0xF0) == CMD_CC_NIBBLE && midiCmd_get_cmd_toggle(pRom)){
					lfo_start(prev, pRom);
				}
				prev = cmd_is_lfo(pRom) ? pRom : NULL;
			}
		}
	}
}

/*
 * One command list, from command `start` on, up to the end of the list or the
 * next Cycle command. `first` is where the part of the list that fired begins,
 * the state of a cycle button, which is where its release pass starts. Returns
 * false when it stopped at a Wait and left the rest to pending_task.
 */
static bool run_cmd_list(uint8_t *base, uint8_t first, uint8_t start, uint8_t toggle,
		uint8_t owner, uint8_t flags, bool allow_wait){
	uint32_t ramp = 0;	// time of a Ramp just above the command, 0 for none
	const uint8_t *lfo = NULL;	// an LFO just above the command
	for(uint8_t j=start; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		uint8_t *pRom = base + j * MIDI_ROM_CMD_SIZE;
		if(cmd_is_cycle(pRom)) break;	// the next state
		if(cmd_is_leave(pRom)) break;	// a bank's commands on leaving it
		if((flags & LIST_SKIP_BANK) && (*pRom & 0xF0) == CMD_BANK_NIBBLE) continue;
		uint32_t ramp_ms = ramp;
		const uint8_t *lfo_cmd = lfo;
		ramp = 0;	// a Ramp or LFO only reaches the command right below it
		lfo = NULL;
		if(cmd_is_ramp(pRom)){
			ramp = ramp_time_ms(pRom);
			continue;
		}
		if(cmd_is_lfo(pRom)){
			lfo = pRom;
			continue;
		}
		if(cmd_is_wait(pRom)){
			uint32_t ms = (uint32_t)pRom[2] * 10;
			if(allow_wait && ms &&
					pending_schedule(base, first, (uint8_t)(j + 1), toggle, owner, flags, ms)){
				return false;
			}
			continue;
		}
		if(ramp_ms && (*pRom & 0xF0) == CMD_CC_NIBBLE){
			ramp_cc(pRom, midiCmd_get_cmd_toggle(pRom) ? toggle : MIDI_CONTROL_ON, ramp_ms);
			continue;
		}
		if(lfo_cmd && (*pRom & 0xF0) == CMD_CC_NIBBLE){
			if(!midiCmd_get_cmd_toggle(pRom) || toggle){
				lfo_start(lfo_cmd, pRom);
				continue;
			}
			lfo_stop(pRom[0] & 0x0F, pRom[1] & 0x7F);	// switched off: then its Off value
		}
		handle_cmd_sw_down(pRom, toggle);
	}

	if(flags & LIST_SKIP_BANK){
		pending_bank = 0xFF;	// nothing in this list may change the bank
		pending_page = 0xFF;
	} else {
		apply_pending_bank();
	}
	if(flags & LIST_UP_AFTER) run_list_up(base, first, toggle, flags);
	return true;
}

// The release pass of a list. Pauses belong to the press, so this one runs
// straight through.
static void run_list_up(uint8_t *base, uint8_t first, uint8_t toggle, uint8_t flags){
	uint32_t ramp = 0;
	bool lfo = false;
	for(uint8_t j=first; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		uint8_t *pRom = base + j * MIDI_ROM_CMD_SIZE;
		if(cmd_is_cycle(pRom)) break;
		uint32_t ramp_ms = ramp;
		bool lfo_above = lfo;
		ramp = cmd_is_ramp(pRom) ? ramp_time_ms(pRom) : 0;
		lfo = cmd_is_lfo(pRom);
		if(lfo_above && (*pRom & 0xF0) == CMD_CC_NIBBLE && !midiCmd_get_cmd_toggle(pRom)){
			lfo_stop(pRom[0] & 0x0F, pRom[1] & 0x7F);	// released: then its Off value
		}
		if((flags & LIST_SKIP_BANK) && (*pRom & 0xF0) == CMD_BANK_NIBBLE) continue;
		if(ramp_ms && (*pRom & 0xF0) == CMD_CC_NIBBLE){
			// A momentary CC ramps back to Off; a toggle one moves on the press only
			if(!midiCmd_get_cmd_toggle(pRom)) ramp_cc(pRom, MIDI_CONTROL_OFF, ramp_ms);
			continue;
		}
		handle_cmd_sw_up(pRom, toggle);
	}
}

/*
 * Auto-repeat. A CCInc or PCInc command marked Repeat fires again while its
 * button is held: after REPEAT_DELAY_MS, then every REPEAT_START_MS, each gap
 * a quarter shorter than the last down to REPEAT_MIN_MS. Only the marked
 * commands of the list that fired repeat, straight away, whatever pauses the
 * list holds. Holding a button with long press commands makes a long press,
 * so its short list cannot repeat, but its long list can.
 */
#define REPEAT_DELAY_MS		(500U)
#define REPEAT_START_MS		(200U)
#define REPEAT_MIN_MS		(50U)

static bool cmd_repeats(const uint8_t *pRom){
	switch(pRom[0] & 0xF0){
	case CMD_CCINC_NIBBLE:
		return (pRom[2] & CCINC_REPEAT_BIT) != 0;
	case CMD_TAP_NIBBLE:
		return tap_is_step(pRom) && (pRom[2] & TAP_REPEAT_BIT) != 0;
	case CMD_PC_NIBBLE:
		return pRom[2] == PC_REL_UP_REPEAT || pRom[2] == PC_REL_DOWN_REPEAT;
	default:
		return false;
	}
}

// Called as a list fires: remember it if the part that fired, from command
// `first` to the next Cycle, has anything to repeat
static void repeat_arm(sw_t *sw, uint8_t *base, uint8_t first){
	sw->repeat_list = NULL;
	for(uint8_t j=first; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		if(cmd_is_cycle(base + j * MIDI_ROM_CMD_SIZE)) return;
		if(cmd_repeats(base + j * MIDI_ROM_CMD_SIZE)){
			sw->repeat_list = base;
			sw->repeat_first = first;
			sw->repeat_tick = HAL_GetTick();
			sw->repeat_interval = REPEAT_DELAY_MS;
			return;
		}
	}
}

static void repeat_task(sw_t *sw, uint32_t now){
	if(sw->repeat_list == NULL) return;
	if(sw->press_state != PRESS_SHORT && sw->press_state != PRESS_LONG &&
			sw->press_state != PRESS_DOUBLE){
		sw->repeat_list = NULL;	// released, or never held
		return;
	}
	if((now - sw->repeat_tick) < sw->repeat_interval) return;
	// Step the clock by the interval, not to now, so the main loop's pace
	// does not stretch every gap; after a long stall, start again from now
	sw->repeat_tick += sw->repeat_interval;
	if((now - sw->repeat_tick) >= sw->repeat_interval) sw->repeat_tick = now;
	if(sw->repeat_interval == REPEAT_DELAY_MS){
		sw->repeat_interval = REPEAT_START_MS;
	} else {
		uint16_t next = (uint16_t)(sw->repeat_interval * 3 / 4);
		sw->repeat_interval = (next > REPEAT_MIN_MS) ? next : REPEAT_MIN_MS;
	}
	for(uint8_t j=sw->repeat_first; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		uint8_t *pRom = sw->repeat_list + j * MIDI_ROM_CMD_SIZE;
		if(cmd_is_cycle(pRom)) break;
		if(!cmd_repeats(pRom)) continue;
		if((pRom[0] & 0xF0) == CMD_CCINC_NIBBLE){
			send_ccinc(pRom, true);
		} else if((pRom[0] & 0xF0) == CMD_TAP_NIBBLE){
			send_tap(pRom);
		} else {
			send_pc_relative(pRom, true);
		}
	}
}

// LED of a momentary (non toggle) button following the physical press
static void set_momentary_led(uint8_t i, uint8_t pressed){
	if(!(a_sw_obj[i].led_cmd_toggle & (1UL<<switch_current_page))){
		if(page_led_on(i)) pressed = 1;
		uint8_t mode = get_button_led_mode(i);
		uint8_t state = calculate_led_state(pressed, mode);
		set_led(i, state);
	}
}

/*
 * Exclusive groups: a toggle button of a group about to be switched on first
 * switches off every other button of its group in the current bank, each
 * pressed as if by foot so its off commands, LED and display cell follow.
 * They go first so that, when the group's buttons drive the same parameter,
 * the button just pressed is the one the device ends up on. Only switching
 * on triggers this, so the buttons switched off cannot cascade, and pressing
 * the lit button of a group switches it off like any toggle.
 */
static void release_group(uint8_t i){
	uint8_t group = get_button_group(i);
	if(group == 0) return;
	if(!sw_button_is_toggle(switch_current_page, i)) return;
	if(get_sw_toggle_state(&a_sw_obj[i])) return;	// switching off
	for(uint8_t j=0; j<MIDI_NUM_SWITCHES; j++){
		if(j == i || get_button_group(j) != group) continue;
		if(!sw_button_is_toggle(switch_current_page, j)) continue;
		if(get_sw_toggle_state(&a_sw_obj[j])) sw_trigger_button(j);
	}
}

static void fire_short_down(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	pending_flush_owner(i);
	release_group(i);
	toggle_sw_state(sw);

	// Either toggle the LED, or set it if not toggling
	if(sw->led_cmd_toggle & (1UL<<switch_current_page)){
		uint8_t mode = get_button_led_mode(i);
		uint8_t active = get_sw_toggle_state(sw);
		uint8_t state = calculate_led_state(active, mode);
		set_led(i, state);
	} else {
		set_momentary_led(i, 1);
	}

	uint8_t first = cycle_advance(i);
	repeat_arm(sw, get_rom_pointer(switch_current_page, i, 0), first);
	run_cmd_list(get_rom_pointer(switch_current_page, i, 0), first, first, get_sw_toggle_state(sw), i, 0, true);
}

/*
 * Momentary hold: a toggle button with BUTTON_MOMENTARY_HOLD latches on a tap
 * and works as a momentary switch when held. Its press toggles at once, as
 * always; held past the long press threshold, its release presses it once
 * more, so it goes back to where it was: on only while held, or off only while
 * held if it was on. A button with a long press list uses the hold for that
 * list instead, and a cycle button has no state to go back to.
 */
static bool button_momentary_hold(uint8_t i){
	uint8_t v = pButtonLedModes[switch_current_page * MIDI_NUM_SWITCHES + i];
	if(v == 0xFF || !(v & BUTTON_MOMENTARY_HOLD)) return false;
	if(!sw_button_is_toggle(switch_current_page, i)) return false;
	return cycle_states(get_rom_pointer(switch_current_page, i, 0)) == 1;
}

static void fire_short_up(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	set_momentary_led(i, 0);
	if(pending_defer_release(i)) return;	// still waiting: released once it finishes
	run_list_up(get_rom_pointer(switch_current_page, i, 0), cycle_current_first(i), get_sw_toggle_state(sw), 0);
}

static void fire_long_down(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	pending_flush_owner(i);
	sw->long_toggle_state ^= (1UL << switch_current_page);
	state_store_mark_dirty();
	uint8_t toggleState = (sw->long_toggle_state >> switch_current_page) & 1;
	repeat_arm(sw, get_long_rom_pointer(switch_current_page, i, 0), 0);
	run_cmd_list(get_long_rom_pointer(switch_current_page, i, 0), 0, 0, toggleState, i, 0, true);
}

static void fire_long_up(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	set_momentary_led(i, 0);
	if(pending_defer_release(i)) return;
	uint8_t toggleState = (sw->long_toggle_state >> switch_current_page) & 1;
	run_list_up(get_long_rom_pointer(switch_current_page, i, 0), 0, toggleState, 0);
}

// Press tracking for the two bank switches, so they can tell a short press
// (step one bank) from a long press (jump Bank_Jump_Step banks).
typedef struct {
	uint32_t press_tick;
	uint8_t state;		// PRESS_IDLE / PRESS_PENDING / PRESS_LONG
} bank_press_t;

static bank_press_t bank_down_press = { .state = PRESS_IDLE };
static bank_press_t bank_up_press = { .state = PRESS_IDLE };

static uint8_t bank_switch_mode(void){
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_BANK_SWITCH_MODE];
	return (v <= BANK_SWITCH_MIDI_ONLY) ? v : BANK_SWITCH_BANK_ONLY;
}

/*
 * Commands for one of the bank switches. Fired as a tap, the down list then
 * the up list, so toggles flip once per press. Each list keeps its own toggle
 * state. Bank commands are ignored here: the switch's own bank change, or the
 * mode that suppresses it, is what decides where you end up.
 */
static uint8_t bank_switch_toggle[BANK_SWITCH_LISTS];

static void fire_bank_switch_cmds(uint8_t which, bool long_press){
	if(bank_switch_mode() == BANK_SWITCH_BANK_ONLY) return;

	uint8_t list = (uint8_t)(which * 2 + (long_press ? 1 : 0));
	if(list >= BANK_SWITCH_LISTS) return;

	bank_switch_toggle[list] ^= 1;
	uint8_t toggle = bank_switch_toggle[list];
	uint8_t *base = pBankSwitchCmds + list * MIDI_ROM_KEY_STRIDE;

	run_cmd_list(base, 0, 0, toggle, PENDING_OWNER_NONE, LIST_SKIP_BANK | LIST_UP_AFTER, true);
}

static void handle_bank_switch(bank_press_t *bp, GPIO_TypeDef *port, uint16_t pin,
		volatile uint16_t *pChanged, uint8_t led_id, uint8_t led_mode,
		int16_t direction, uint32_t now, uint8_t which){
	// Held past the threshold: jump by the configured step, once per press
	if(bp->state == PRESS_PENDING && (now - bp->press_tick) >= long_press_threshold_ms()){
		bp->state = PRESS_LONG;
		if(bank_switch_mode() != BANK_SWITCH_MIDI_ONLY){
			goto_bank(bank_step(direction * (int16_t)bank_jump_step()));
		}
		fire_bank_switch_cmds(which, true);
	}

	// Keep blinking LED modes alive while the switch is held
	if(led_mode == LED_MODE_ALWAYS_ON && bp->state != PRESS_IDLE){
		leds_set(led_id, calculate_led_state(1, led_mode));
	}

	if(!(*pChanged & pin)) return;
	*pChanged &= ~pin;

	if(switch_down(port, pin)){
		// Pressed: wait to see whether this becomes a long press
		bp->press_tick = now;
		bp->state = PRESS_PENDING;
		leds_set(led_id, calculate_led_state(1, led_mode));
	} else {
		// Released: a press that never reached the threshold steps one bank
		if(bp->state == PRESS_PENDING){
			if(bank_switch_mode() != BANK_SWITCH_MIDI_ONLY){
				goto_bank(bank_step(direction));
			}
			fire_bank_switch_cmds(which, false);
		}
		bp->state = PRESS_IDLE;
		leds_set(led_id, calculate_led_state(0, led_mode));
	}
}

/*
 * Configuration switching.
 *
 * Every configuration pointer moves at once, so this must not happen while a
 * button's command lists are still being read: the release would run the new
 * configuration's list. It is therefore applied from handle_switches once all
 * switches are up.
 */
static bool all_switches_released(void){
	if(pending_any()) return false;	// a list is still running out its pauses
	for(int i=0; i<MIDI_NUM_SWITCHES; i++){
		if(a_sw_obj[i].press_state != PRESS_IDLE) return false;
	}
	return bank_down_press.state == PRESS_IDLE && bank_up_press.state == PRESS_IDLE;
}

// Send now every release still waiting on a timer, so no note is left hanging
static void flush_delayed_cmds(void){
	for(int i=0; i<MAX_DELAYED_CMDS; i++){
		if(delayed_cmds[i].systick_timout != UINT32_MAX){
			delayed_cmds[i].systick_timout = 0;
		}
	}
	handle_delayed_cmds();
}

static void switch_config(uint8_t target){
	uint8_t from = flash_settings_active_slot();
	uint8_t slot = target;

	if(target == CONFIG_NEXT){
		slot = 0xFF;
		for(uint8_t k=1; k<CONFIG_SLOTS; k++){
			uint8_t s = (uint8_t)((from + k) % CONFIG_SLOTS);
			if(flash_settings_slot_valid(s)){ slot = s; break; }
		}
		if(slot == 0xFF){
			display_show_message("NO CFG");
			return;
		}
	}
	if(slot >= CONFIG_SLOTS || slot == from) return;
	if(!flash_settings_slot_valid(slot)){
		char msg[9];
		snprintf(msg, sizeof(msg), "NO CFG %u", (unsigned)(slot + 1));
		display_show_message(msg);
		return;
	}

	if(page_home != 0xFF) fire_bank_leave_cmds(switch_current_page);
	fire_bank_leave_cmds(home_bank());
	flush_delayed_cmds();
	pending_clear();	// their commands live in the configuration we are leaving
	flash_settings_select(slot);

	// A different configuration starts from its first bank with nothing on
	switch_current_page = 0;
	page_home = 0xFF;
	previous_bank = 0xFF;	// the bank left belongs to the other configuration
	for(int i=0; i<MIDI_NUM_SWITCHES; i++){
		a_sw_obj[i].switch_toggle_state = 0;
		a_sw_obj[i].long_toggle_state = 0;
		a_sw_obj[i].double_toggle_state = 0;
	}
	memset(cycle_pos, CYCLE_NONE, sizeof(cycle_pos));
	pending_bank = 0xFF;
	pending_page = 0xFF;

	// Rebuild everything derived from the configuration
	leds_init();
	sw_led_init();
	expression_init();
	expression_clear_targets();
	lfo_stop_all();

	display_setBankName(0);
	display_show_config(slot);
	state_store_mark_dirty();
	fire_bank_enter_cmds(0);
}

void sw_trigger_button(uint8_t sw){
	if(sw >= MIDI_NUM_SWITCHES || is_app_suspended) return;
	// A quick tap: the down list, then the up list, exactly like a foot press
	fire_short_down(sw);
	fire_short_up(sw);
}

/*
 * Scene: put the toggle buttons of the current bank into a chosen state in one
 * press. Every affected button that is not already where it should be is
 * pressed, exactly as if by foot, so its own commands, LED and display cell
 * follow. Buttons already in the wanted state are left alone, so recalling the
 * same scene twice sends nothing the second time. Non-toggle buttons have no
 * state to set and are skipped.
 *
 * A scene pressing a button whose own list holds a scene is ignored rather
 * than recursing, and a bank change the scene's own button had queued is kept
 * aside so a pressed button cannot apply it halfway through.
 */
static void apply_scene(uint8_t mask, uint8_t states){
	static bool applying = false;
	if(applying) return;
	applying = true;

	uint8_t saved_pending = pending_bank;
	pending_bank = 0xFF;

	for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++){
		if(!(mask & (1U << i))) continue;
		if(!sw_button_is_toggle(switch_current_page, i)) continue;
		uint8_t want = (states >> i) & 1U;
		if(get_sw_toggle_state(&a_sw_obj[i]) != want){
			sw_trigger_button(i);
		}
	}

	if(pending_bank == 0xFF) pending_bank = saved_pending;
	applying = false;
}

/*
 * Virtual pedal. The configurator presses and releases switches over SysEx so
 * a configuration can be tried without a foot on the pedal. A virtual press
 * does not bypass anything: it marks the switch as held and raises the same
 * change flag the switch scan raises, so short, long and double presses, the
 * bank switches and the LEDs all behave exactly as with a real press.
 *
 * The USB interrupt only queues the request; handle_switches applies it. A
 * virtual press left down (the configurator closed mid-press) lets go by
 * itself after VIRTUAL_MAX_HOLD_MS.
 */
#define VIRTUAL_QUEUE_LEN		(16)
#define VIRTUAL_MAX_HOLD_MS		(10000U)

static uint8_t virtual_queue[VIRTUAL_QUEUE_LEN];	// id | 0x80 when down
static volatile uint8_t virtual_head = 0;	// written by the USB interrupt only
static volatile uint8_t virtual_tail = 0;	// written by the main loop only
static uint16_t virtual_down = 0;			// bit per virtual switch id
static uint32_t virtual_tick[SW_VIRTUAL_COUNT];

void sw_virtual_press(uint8_t id, uint8_t down){
	if(id >= SW_VIRTUAL_COUNT) return;
	uint8_t next = (uint8_t)((virtual_head + 1) % VIRTUAL_QUEUE_LEN);
	if(next == virtual_tail) return;
	virtual_queue[virtual_head] = id | (down ? 0x80 : 0);
	virtual_head = next;
}

static void virtual_pin(uint8_t id, GPIO_TypeDef **port, uint16_t *pin, volatile uint16_t **changed){
	if(id < MIDI_NUM_SWITCHES){
		*port = a_sw_obj[id].sw_gpio_port;
		*pin = a_sw_obj[id].sw_gpio_pin;
		*changed = a_sw_obj[id].pSwChangeState;
	} else if(id == SW_VIRTUAL_BANK_DOWN){
		*port = SW_E_GPIO_Port;
		*pin = SW_E_Pin;
		*changed = &port_A_switches_changed;
	} else {
		*port = SW_5_GPIO_Port;
		*pin = SW_5_Pin;
		*changed = &port_B_switches_changed;
	}
}

static void virtual_set(uint8_t id, bool down){
	uint16_t bit = (uint16_t)(1U << id);
	if(((virtual_down & bit) != 0) == down) return;
	if(down){
		virtual_down |= bit;
		virtual_tick[id] = HAL_GetTick();
	} else {
		virtual_down &= (uint16_t)~bit;
	}
	GPIO_TypeDef *port;
	uint16_t pin;
	volatile uint16_t *changed;
	virtual_pin(id, &port, &pin, &changed);
	__disable_irq();	// the switch scan sets these flags from SysTick
	*changed |= pin;
	__enable_irq();
	sleep_note_activity();
}

static void virtual_task(void){
	// One change per switch per pass: a press and its release arriving
	// together (a host sending CC 127 then 0) must not cancel out before the
	// switch loop has seen the press, so the release waits for the next pass.
	uint16_t touched = 0;
	while(virtual_tail != virtual_head){
		uint8_t e = virtual_queue[virtual_tail];
		uint16_t bit = (uint16_t)(1U << (e & 0x7F));
		if(touched & bit) break;
		touched |= bit;
		virtual_tail = (uint8_t)((virtual_tail + 1) % VIRTUAL_QUEUE_LEN);
		virtual_set(e & 0x7F, (e & 0x80) != 0);
	}
	uint32_t now = HAL_GetTick();
	for(uint8_t id=0; id<SW_VIRTUAL_COUNT; id++){
		if((virtual_down & (1U << id)) && (now - virtual_tick[id]) >= VIRTUAL_MAX_HOLD_MS){
			virtual_set(id, false);
		}
	}
}

// A switch is down when a foot holds it or a virtual press does
static bool switch_down(GPIO_TypeDef *port, uint16_t pin){
	if(!HAL_GPIO_ReadPin(port, pin)) return true;
	if(!virtual_down) return false;
	for(uint8_t id=0; id<SW_VIRTUAL_COUNT; id++){
		GPIO_TypeDef *p;
		uint16_t n;
		volatile uint16_t *c;
		virtual_pin(id, &p, &n, &c);
		if(p == port && n == pin) return (virtual_down >> id) & 1U;
	}
	return false;
}

/*
 * LED feedback (LED_Feedback): a CC or a note arriving over USB puts the
 * toggle buttons that send it into the state it describes, so their LEDs and
 * display cells follow a DAW or an amp editor. Only the state changes: nothing
 * is sent, so a host echoing our own messages back cannot cause a loop.
 *
 * Every bank is updated, not only the current one, and the long press list
 * too, so the next press sends the opposite of what the host last reported.
 * The USB interrupt only queues the message; it is applied here, in the main
 * loop, where the switch state is owned. A full queue drops messages.
 */
#define FEEDBACK_QUEUE_LEN		(32)
#define FEEDBACK_PER_PASS		(4)

static uint8_t feedback_queue[FEEDBACK_QUEUE_LEN][3];
static volatile uint8_t feedback_head = 0;	// written by the USB interrupt only
static volatile uint8_t feedback_tail = 0;	// written by the main loop only

void sw_feedback_message(const uint8_t *data){
	if(pGlobalSettings[GLOBAL_SETTINGS_LED_FEEDBACK] != 1) return;
	uint8_t next = (uint8_t)((feedback_head + 1) % FEEDBACK_QUEUE_LEN);
	if(next == feedback_tail) return;
	feedback_queue[feedback_head][0] = data[0];
	feedback_queue[feedback_head][1] = data[1] & 0x7F;
	feedback_queue[feedback_head][2] = data[2] & 0x7F;
	feedback_head = next;
}

/*
 * What an incoming message says about one command: 1 on, 0 off, -1 nothing.
 * A CC is on when its value is nearer the command's OnValue than its OffValue;
 * a command without an OffValue only recognises its OnValue. A Note On with a
 * velocity turns a note command on, a Note Off or velocity 0 turns it off.
 */
static int8_t feedback_state_for(uint8_t *pRom, const uint8_t *msg){
	if(!midiCmd_get_cmd_toggle(pRom)) return -1;
	if((pRom[0] & 0x0F) != (msg[0] & 0x0F)) return -1;
	if((pRom[1] & 0x7F) != msg[1]) return -1;

	uint8_t type = pRom[0] & 0xF0;
	uint8_t value = msg[2];
	switch(msg[0] & 0xF0){
	case 0xB0:
		if(type != CMD_CC_NIBBLE) return -1;
		{
			uint8_t on = pRom[2] & 0x7F;
			if(pRom[3] > 0x7F) return (value == on) ? 1 : -1;
			uint8_t off = pRom[3];
			uint8_t d_on  = (value > on)  ? value - on  : on - value;
			uint8_t d_off = (value > off) ? value - off : off - value;
			return (d_on <= d_off) ? 1 : 0;
		}
	case 0x90:
		if(type != CMD_NOTE_NIBBLE) return -1;
		return (value > 0) ? 1 : 0;
	case 0x80:
		if(type != CMD_NOTE_NIBBLE) return -1;
		return 0;
	default:
		return -1;
	}
}

// The state one command list asks for, or -1. The last matching command wins.
static int8_t feedback_list_state(uint8_t *(*rom)(uint8_t, uint8_t, uint8_t),
		uint8_t bank, uint8_t sw, const uint8_t *msg){
	int8_t want = -1;
	for(uint8_t j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		int8_t s = feedback_state_for(rom(bank, sw, j), msg);
		if(s >= 0) want = s;
	}
	return want;
}

static void feedback_apply(const uint8_t *msg){
	bool changed = false;
	for(uint8_t i=0; i<MIDI_NUM_SWITCHES; i++){
		sw_t *sw = &a_sw_obj[i];
		for(uint8_t b=0; b<MIDI_NUM_BANKS; b++){
			uint32_t bit = 1UL << b;

			if(sw->led_cmd_toggle & bit){
				int8_t want = feedback_list_state(get_rom_pointer, b, i, msg);
				if(want >= 0 && ((sw->switch_toggle_state & bit) != 0) != (want == 1)){
					sw->switch_toggle_state ^= bit;
					changed = true;
					if(b == switch_current_page){
						if(!sleep_is_asleep()){
							set_led(i, calculate_led_state(want, get_button_led_mode(i)));
						}
						display_request_refresh();
					}
				}
			}

			if(sw->long_cmd_toggle & bit){
				int8_t want = feedback_list_state(get_long_rom_pointer, b, i, msg);
				if(want >= 0 && ((sw->long_toggle_state & bit) != 0) != (want == 1)){
					sw->long_toggle_state ^= bit;
					changed = true;
				}
			}

			if(sw->double_cmd_toggle & bit){
				int8_t want = feedback_list_state(get_double_rom_pointer, b, i, msg);
				if(want >= 0 && ((sw->double_toggle_state & bit) != 0) != (want == 1)){
					sw->double_toggle_state ^= bit;
					changed = true;
				}
			}
		}
	}
	if(changed){
		state_store_mark_dirty();
	}
}

/*
 * Double press: the button's third command list, with its own toggle state.
 * Like the long press list it has no LED of its own.
 */
static void fire_double_down(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	pending_flush_owner(i);
	sw->double_toggle_state ^= (1UL << switch_current_page);
	uint8_t toggleState = (sw->double_toggle_state >> switch_current_page) & 1;
	repeat_arm(sw, get_double_rom_pointer(switch_current_page, i, 0), 0);
	run_cmd_list(get_double_rom_pointer(switch_current_page, i, 0), 0, 0, toggleState, i, 0, true);
}

static void fire_double_up(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	uint8_t toggleState = (sw->double_toggle_state >> switch_current_page) & 1;
	if(pending_defer_release(i)) return;
	run_list_up(get_double_rom_pointer(switch_current_page, i, 0), 0, toggleState, 0);
}

static void feedback_task(void){
	for(uint8_t n=0; n<FEEDBACK_PER_PASS && feedback_tail != feedback_head; n++){
		feedback_apply(feedback_queue[feedback_tail]);
		feedback_tail = (uint8_t)((feedback_tail + 1) % FEEDBACK_QUEUE_LEN);
	}
}

void handle_switches(void){
	if(is_app_suspended) return;

	virtual_task();

	// A bank change asked for from interrupt context (incoming MIDI)
	if(requested_bank != 0xFF){
		uint8_t target = requested_bank;
		requested_bank = 0xFF;
		goto_bank(target);
	}

	// A configuration switch waits until every button is up
	if(pending_config != 0xFF && all_switches_released()){
		uint8_t target = pending_config;
		pending_config = 0xFF;
		switch_config(target);
		return;
	}

	feedback_task();
	pending_task();	// lists left half way by a Wait
	ramp_task();	// CC ramps under way
	lfo_task();		// and LFOs

	// The Command switches
	uint32_t now = HAL_GetTick();
	for(int i=0; i<8; i++){
		sw_t *sw = &a_sw_obj[i];

		uint32_t bit = 1UL << switch_current_page;
		bool has_long = (sw->long_cmd_present & bit) != 0;
		bool has_double = (sw->double_cmd_present & bit) != 0;

		// A pending press becomes a long press once held past the threshold.
		// A button with no long press commands, pending only because of its
		// double press, is simply a short press being held.
		if(sw->press_state == PRESS_PENDING && (now - sw->press_tick) >= long_press_threshold_ms()){
			if(has_long){
				fire_long_down(i);
				sw->press_state = PRESS_LONG;
			} else {
				fire_short_down(i);
				sw->press_state = PRESS_SHORT;
			}
		}

		// No second press in time: the tap was a single short press
		if(sw->press_state == PRESS_WAIT_SECOND && (now - sw->release_tick) >= double_press_window_ms()){
			sw->press_state = PRESS_IDLE;
			fire_short_down(i);
			fire_short_up(i);
		}

		if(*sw->pSwChangeState & sw->sw_gpio_pin){
			*sw->pSwChangeState &= ~sw->sw_gpio_pin;

			if(switch_down(sw->sw_gpio_port, sw->sw_gpio_pin)){
				// Switch Down
				if(sw->press_state == PRESS_WAIT_SECOND){
					// The second press of a double press
					set_momentary_led(i, 1);
					fire_double_down(i);
					sw->press_state = PRESS_DOUBLE;
				} else if(has_long || has_double){
					// Can't tell yet whether this is a short, long or double press
					sw->press_tick = now;
					sw->press_state = PRESS_PENDING;
					set_momentary_led(i, 1);
				} else {
					sw->press_tick = now;
					fire_short_down(i);
					sw->press_state = PRESS_SHORT;
				}
			} else {
				// Switch up
				uint8_t next = PRESS_IDLE;
				switch(sw->press_state){
				case PRESS_PENDING:
					if(has_double){
						// Maybe the first half of a double press: wait for a second one
						set_momentary_led(i, 0);
						sw->release_tick = now;
						next = PRESS_WAIT_SECOND;
					} else {
						// Released before the threshold: it was a short press
						fire_short_down(i);
						fire_short_up(i);
					}
					break;
				case PRESS_SHORT:
					fire_short_up(i);
					if(button_momentary_hold(i) && (now - sw->press_tick) >= long_press_threshold_ms()){
						sw_trigger_button(i);	// held: back to the state before the press
					}
					break;
				case PRESS_LONG:
					fire_long_up(i);
					break;
				case PRESS_DOUBLE:
					set_momentary_led(i, 0);
					fire_double_up(i);
					break;
				default:
					break;
				}
				sw->press_state = next;
			}
		}

		repeat_task(sw, now);
	}

	handle_delayed_cmds();
	
	// Continuous Blink Update Loop for AlwaysOn Buttons
	for(int i=0; i<8; i++){
		uint8_t mode = get_button_led_mode(i);
		if(mode == 2){ // AlwaysOn (Blink)
			uint8_t is_active = 0;
			if(a_sw_obj[i].led_cmd_toggle & (1UL<<switch_current_page)){
				// Toggle Mode: Active if toggle state is ON
				is_active = get_sw_toggle_state(&a_sw_obj[i]);
			} else {
				// Momentary Mode: Active if physically pressed
				if(switch_down(a_sw_obj[i].sw_gpio_port, a_sw_obj[i].sw_gpio_pin)){
					is_active = 1;
				}
			}
			uint8_t state = calculate_led_state(is_active, mode);
			set_led(i, state);
		}
	}
	
	tap_led_task();

	// Bank LEDs Update - Handle Blink
	// We need to continuously update them if they are in Blink mode
	uint8_t bank_down_mode = get_bank_down_led_mode();
	uint8_t bank_up_mode = get_bank_up_led_mode();
	
	// We need to check switch state for Bank buttons
	// Since port_X_switches_changed only tells us about changes, we need to read pins for continuous blink
	// SW_E is Bank Down, SW_5 is Bank Up
	
	// Bank Down Switch State
	uint8_t sw_e_down = switch_down(SW_E_GPIO_Port, SW_E_Pin);
	// Only update loop if blink is needed or change happened?
	// To support Blink, we should update if mode is 2 and sw is down
	if(bank_down_mode == 2 && sw_e_down) {
		uint8_t state = calculate_led_state(1, bank_down_mode);
		leds_set(LED_ID_BANK_DOWN, state);
	}

	// Bank Up Switch State
	uint8_t sw_5_down = switch_down(SW_5_GPIO_Port, SW_5_Pin);
	if(bank_up_mode == 2 && sw_5_down) {
		uint8_t state = calculate_led_state(1, bank_up_mode);
		leds_set(LED_ID_BANK_UP, state);
	}


	// The bank change switches: a short press steps one bank, a long press
	// jumps Bank_Jump_Step banks. Both wrap around.
	handle_bank_switch(&bank_down_press, SW_E_GPIO_Port, SW_E_Pin, &port_A_switches_changed,
			LED_ID_BANK_DOWN, bank_down_mode, -1, now, BANK_SWITCH_DOWN);
	handle_bank_switch(&bank_up_press, SW_5_GPIO_Port, SW_5_Pin, &port_B_switches_changed,
			LED_ID_BANK_UP, bank_up_mode, +1, now, BANK_SWITCH_UP);
}

/*
 * Tap LED: the buttons of this bank holding a Tap command flash at the start
 * of every beat, those in Clock mode only while the clock runs, and so does
 * any button whose LED mode byte asks for it. The flash is an overlay on top
 * of whatever the LED shows, so nothing else is disturbed.
 */
static void tap_led_task(void){
	uint16_t mask = 0;
	if(!is_app_suspended && !sleep_is_asleep() && tempo_beat_flash()){
		uint32_t bit = 1UL << switch_current_page;
		bool clock = tempo_clock_running();
		for(int i=0; i<8; i++){
			if((a_sw_obj[i].tap_blink & bit) || get_button_tempo_flash(i)
					|| (clock && (a_sw_obj[i].clock_blink & bit))){
				mask |= (uint16_t)(1U << i);
			}
		}
	}
	leds_set_flash(mask);
}

void set_all_leds(uint8_t state){
	leds_set_all(state ? leds_level_active() : 0);
}

uint8_t sw_get_current_page(void){
	return switch_current_page;
}

uint8_t sw_get_home_bank(void){
	return home_bank();
}

uint8_t sw_button_is_toggle(uint8_t bank, uint8_t sw){
	if(sw >= MIDI_NUM_SWITCHES || bank >= MIDI_NUM_BANKS) return 0;
	return (a_sw_obj[sw].led_cmd_toggle >> bank) & 1;
}

uint8_t sw_get_toggle_state(uint8_t bank, uint8_t sw){
	if(sw >= MIDI_NUM_SWITCHES || bank >= MIDI_NUM_BANKS) return 0;
	return (a_sw_obj[sw].switch_toggle_state >> bank) & 1;
}

void sw_get_toggle_states(uint32_t out[8]){
	for(int i=0; i<8; i++){
		out[i] = a_sw_obj[i].switch_toggle_state;
	}
}

void sw_get_long_toggle_states(uint32_t out[8]){
	for(int i=0; i<8; i++){
		out[i] = a_sw_obj[i].long_toggle_state;
	}
}

void sw_restore_state(uint8_t page, const uint32_t toggles[8], const uint32_t long_toggles[8]){
	if(page < MIDI_NUM_BANKS){
		switch_current_page = page;
		page_home = 0xFF;
	}
	for(int i=0; i<8; i++){
		a_sw_obj[i].switch_toggle_state = toggles[i];
		a_sw_obj[i].long_toggle_state = long_toggles[i];
	}
	exp_targets_for_bank();
	lfo_restart_all();
	update_leds_on_bank_change();
}

void setIsSuspended(uint8_t suspended){
	is_app_suspended = suspended;
	if(suspended){
		leds_set_flash(0);
		set_all_leds(0);
	}
}
