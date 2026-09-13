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

void update_leds_on_bank_change(void);
static void fire_bank_enter_cmds(uint8_t bank);
static void apply_scene(uint8_t mask, uint8_t states);
uint8_t sw_button_is_toggle(uint8_t bank, uint8_t sw);

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
	uint32_t press_tick;         // HAL tick when the button went down
	uint8_t press_state;         // PRESS_IDLE / PRESS_PENDING / PRESS_SHORT / PRESS_LONG
} sw_t;

#define PRESS_IDLE		(0)  // Released
#define PRESS_PENDING	(1)  // Down, waiting to see if it becomes a long press
#define PRESS_SHORT		(2)  // Short press commands fired, waiting for release
#define PRESS_LONG		(3)  // Long press commands fired, waiting for release

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

static void send_ccinc(uint8_t *pRom){
	uint8_t channel = pRom[0] & 0x0F;
	uint8_t cc = pRom[1] & 0x7F;
	uint8_t wrap = (pRom[1] & 0x80) != 0;
	uint8_t step = pRom[2] ? pRom[2] : 1;
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

	if(slot >= 0) ccinc_value[slot] = (uint8_t)next;
	midiCmd_send_cc(channel, cc, (uint8_t)next);
	display_show_cc(cc, (uint8_t)next);
}

// A stored SysEx payload, wrapped in F0 ... F7 and sent to USB and DIN
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

static inline uint8_t cmd_is_present(const uint8_t *pRom){
	uint8_t t = *pRom & 0xF0;
	return t != CMD_NO_CMD_NIBBLE && t != 0xF0; // 0xF0 = erased flash
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

// Commands stored for "entering this bank"
static uint8_t* get_bank_enter_pointer(uint8_t bank, uint8_t cmd){
	return pBankEnterCmds + (MIDI_ROM_KEY_STRIDE * bank) + (MIDI_ROM_CMD_SIZE * cmd);
}

static void goto_bank(uint8_t bank){
	if(bank >= MIDI_NUM_BANKS || bank == switch_current_page) return;
	switch_current_page = bank;
	update_leds_on_bank_change();
	display_setBankName(switch_current_page);
	state_store_mark_dirty();
	fire_bank_enter_cmds(bank);
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
		if(pSetlist[i] == switch_current_page){ idx = i; break; }
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

	int16_t b = (int16_t)switch_current_page + delta;
	while(b < 0) b += MIDI_NUM_BANKS;
	while(b >= MIDI_NUM_BANKS) b -= MIDI_NUM_BANKS;
	return (uint8_t)b;
}

static uint32_t long_press_threshold_ms(void){
	uint8_t v = pGlobalSettings[GLOBAL_SETTINGS_LONG_PRESS];
	if(v == 0 || v == 0xFF) return 500;
	return (uint32_t)v * 10;
}

static inline uint8_t sanitize_led_mode(uint8_t mode){
	// Erased flash (0xFF) or any unknown value falls back to Normal
	return (mode <= LED_MODE_ALWAYS_ON) ? mode : LED_MODE_NORMAL;
}

// 0=Normal, 1=Reverse, 2=AlwaysOn(Blink), read from the per-button LED mode table
uint8_t get_button_led_mode(uint8_t sw){
	return sanitize_led_mode(pButtonLedModes[switch_current_page * MIDI_NUM_SWITCHES + sw]);
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

void sw_led_init(void){
	// Scan all commands in EEPROM, and build the table of whether the LED should toggle with the switch, or be momentary
	for(int page=0; page<MIDI_NUM_BANKS; page++){
		for(int sw=0; sw<8; sw++){
			// Clear the toggle bit
			a_sw_obj[sw].led_cmd_toggle &= ~(1UL<<page);

			for(int cmd=0; cmd<MIDI_NUM_COMMANDS_PER_SWITCH; cmd++){
				uint8_t *pCmd = get_rom_pointer(page, sw, cmd);
				if(midiCmd_get_cmd_toggle(pCmd)){
					a_sw_obj[sw].led_cmd_toggle |= (1UL<<page);
				}
			}

			// Same for the long press command set
			a_sw_obj[sw].long_cmd_present &= ~(1UL<<page);
			a_sw_obj[sw].long_cmd_toggle &= ~(1UL<<page);
			for(int cmd=0; cmd<MIDI_NUM_COMMANDS_PER_SWITCH; cmd++){
				uint8_t *pCmd = get_long_rom_pointer(page, sw, cmd);
				if(cmd_is_present(pCmd)){
					a_sw_obj[sw].long_cmd_present |= (1UL<<page);
					if(midiCmd_get_cmd_toggle(pCmd)){
						a_sw_obj[sw].long_cmd_toggle |= (1UL<<page);
					}
				}
			}
			a_sw_obj[sw].press_state = PRESS_IDLE;
		}
	}

	ccinc_reset();

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
		status = midiCmd_send_pc_command_from_rom(pRom);
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
		send_ccinc(pRom);
		break;
	case CMD_TAP_NIBBLE:
		if((*pRom & 0x0F) == 1){
			tempo_clock_toggle();
		} else {
			tempo_tap();
		}
		display_show_tempo();
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
		status = midiCmd_send_panic();
		break;
	case CMD_SCENE_NIBBLE:
		apply_scene(pRom[1], pRom[2]);
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
			uint8_t state = calculate_led_state(0, mode);
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
	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		uint8_t *pRom = get_bank_enter_pointer(bank, j);
		if((*pRom & 0xF0) == CMD_BANK_NIBBLE) continue;
		handle_cmd_sw_down(pRom, MIDI_CONTROL_ON);
	}
	pending_bank = 0xFF; // nothing here may change the bank
}

static void apply_pending_bank(void){
	if(pending_bank != 0xFF){
		uint8_t target = pending_bank;
		pending_bank = 0xFF;
		goto_bank(target);
	}
}

// LED of a momentary (non toggle) button following the physical press
static void set_momentary_led(uint8_t i, uint8_t pressed){
	if(!(a_sw_obj[i].led_cmd_toggle & (1UL<<switch_current_page))){
		uint8_t mode = get_button_led_mode(i);
		uint8_t state = calculate_led_state(pressed, mode);
		set_led(i, state);
	}
}

static void fire_short_down(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
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

	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		handle_cmd_sw_down(get_rom_pointer(switch_current_page, i, j), get_sw_toggle_state(sw));
	}
	apply_pending_bank();
}

static void fire_short_up(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	set_momentary_led(i, 0);
	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		handle_cmd_sw_up(get_rom_pointer(switch_current_page, i, j), get_sw_toggle_state(sw));
	}
}

static void fire_long_down(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	sw->long_toggle_state ^= (1UL << switch_current_page);
	state_store_mark_dirty();
	uint8_t toggleState = (sw->long_toggle_state >> switch_current_page) & 1;
	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		handle_cmd_sw_down(get_long_rom_pointer(switch_current_page, i, j), toggleState);
	}
	apply_pending_bank();
}

static void fire_long_up(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	set_momentary_led(i, 0);
	uint8_t toggleState = (sw->long_toggle_state >> switch_current_page) & 1;
	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		handle_cmd_sw_up(get_long_rom_pointer(switch_current_page, i, j), toggleState);
	}
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

	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		uint8_t *pRom = base + j * MIDI_ROM_CMD_SIZE;
		if((*pRom & 0xF0) == CMD_BANK_NIBBLE) continue;
		handle_cmd_sw_down(pRom, toggle);
	}
	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		uint8_t *pRom = base + j * MIDI_ROM_CMD_SIZE;
		if((*pRom & 0xF0) == CMD_BANK_NIBBLE) continue;
		handle_cmd_sw_up(pRom, toggle);
	}
	pending_bank = 0xFF;
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

	if(!HAL_GPIO_ReadPin(port, pin)){
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

	flush_delayed_cmds();
	flash_settings_select(slot);

	// A different configuration starts from its first bank with nothing on
	switch_current_page = 0;
	for(int i=0; i<MIDI_NUM_SWITCHES; i++){
		a_sw_obj[i].switch_toggle_state = 0;
		a_sw_obj[i].long_toggle_state = 0;
	}
	pending_bank = 0xFF;

	// Rebuild everything derived from the configuration
	leds_init();
	sw_led_init();
	expression_init();

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
		}
	}
	if(changed){
		state_store_mark_dirty();
	}
}

static void feedback_task(void){
	for(uint8_t n=0; n<FEEDBACK_PER_PASS && feedback_tail != feedback_head; n++){
		feedback_apply(feedback_queue[feedback_tail]);
		feedback_tail = (uint8_t)((feedback_tail + 1) % FEEDBACK_QUEUE_LEN);
	}
}

void handle_switches(void){
	if(is_app_suspended) return;

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

	// The Command switches
	uint32_t now = HAL_GetTick();
	for(int i=0; i<8; i++){
		sw_t *sw = &a_sw_obj[i];

		// A pending press becomes a long press once held past the threshold
		if(sw->press_state == PRESS_PENDING && (now - sw->press_tick) >= long_press_threshold_ms()){
			fire_long_down(i);
			sw->press_state = PRESS_LONG;
		}

		if(*sw->pSwChangeState & sw->sw_gpio_pin){
			*sw->pSwChangeState &= ~sw->sw_gpio_pin;

			if(!HAL_GPIO_ReadPin(sw->sw_gpio_port, sw->sw_gpio_pin)){
				// Switch Down
				if(sw->long_cmd_present & (1UL<<switch_current_page)){
					// Can't tell yet whether this is a short or a long press
					sw->press_tick = now;
					sw->press_state = PRESS_PENDING;
					set_momentary_led(i, 1);
				} else {
					fire_short_down(i);
					sw->press_state = PRESS_SHORT;
				}
			} else {
				// Switch up
				switch(sw->press_state){
				case PRESS_PENDING:
					// Released before the threshold: it was a short press
					fire_short_down(i);
					fire_short_up(i);
					break;
				case PRESS_SHORT:
					fire_short_up(i);
					break;
				case PRESS_LONG:
					fire_long_up(i);
					break;
				default:
					break;
				}
				sw->press_state = PRESS_IDLE;
			}
		}
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
				if(!HAL_GPIO_ReadPin(a_sw_obj[i].sw_gpio_port, a_sw_obj[i].sw_gpio_pin)){
					is_active = 1;
				}
			}
			uint8_t state = calculate_led_state(is_active, mode);
			set_led(i, state);
		}
	}
	
	// Bank LEDs Update - Handle Blink
	// We need to continuously update them if they are in Blink mode
	uint8_t bank_down_mode = get_bank_down_led_mode();
	uint8_t bank_up_mode = get_bank_up_led_mode();
	
	// We need to check switch state for Bank buttons
	// Since port_X_switches_changed only tells us about changes, we need to read pins for continuous blink
	// SW_E is Bank Down, SW_5 is Bank Up
	
	// Bank Down Switch State
	uint8_t sw_e_down = !HAL_GPIO_ReadPin(SW_E_GPIO_Port, SW_E_Pin);
	// Only update loop if blink is needed or change happened?
	// To support Blink, we should update if mode is 2 and sw is down
	if(bank_down_mode == 2 && sw_e_down) {
		uint8_t state = calculate_led_state(1, bank_down_mode);
		leds_set(LED_ID_BANK_DOWN, state);
	}

	// Bank Up Switch State
	uint8_t sw_5_down = !HAL_GPIO_ReadPin(SW_5_GPIO_Port, SW_5_Pin);
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

void set_all_leds(uint8_t state){
	leds_set_all(state ? leds_level_active() : 0);
}

uint8_t sw_get_current_page(void){
	return switch_current_page;
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
	}
	for(int i=0; i<8; i++){
		a_sw_obj[i].switch_toggle_state = toggles[i];
		a_sw_obj[i].long_toggle_state = long_toggles[i];
	}
	update_leds_on_bank_change();
}

void setIsSuspended(uint8_t suspended){
	is_app_suspended = suspended;
	if(suspended){
		set_all_leds(0);
	}
}
