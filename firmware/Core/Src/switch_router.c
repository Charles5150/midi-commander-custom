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
#include "state_store.h"

void update_leds_on_bank_change(void);

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
	uint8_t switch_toggle_state; // Each bit will be a flag for pages 0-7
	uint8_t led_cmd_toggle;
	// Long press: a second command set fired when the button is held
	uint8_t long_toggle_state;   // Toggle state of the long press commands, bit per page
	uint8_t long_cmd_present;    // Bit per page: this button has long press commands
	uint8_t long_cmd_toggle;     // Bit per page: any long press command is a toggle
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
		debounce_counter = 10; // 10ms debounce delay
		return;
	}

}

static inline uint8_t get_sw_toggle_state(sw_t *sw){
	return sw->switch_toggle_state & (1 << switch_current_page);
}

static inline void toggle_sw_state(sw_t *sw){
	sw->switch_toggle_state ^= (1 << switch_current_page);
	state_store_mark_dirty();
	if(sw->led_cmd_toggle & (1 << switch_current_page)){
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
    
    // Build Report
    uint8_t report[8] = {0};
    
    // Mod Byte
    for(int i=0; i<8; i++) {
        if(mod_press_count[i] > 0) report[0] |= (1<<i);
    }
    
    // Keys (max 6)
    int k = 0;
    for(int i=0; i<256 && k < 6; i++) {
        if(key_press_count[i] > 0) {
            report[2+k] = i;
            k++;
        }
    }
    
    HID_SendReport_FS(report, 8);
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
uint8_t calculate_led_state(uint8_t pressed, uint8_t mode){
	uint32_t tick = HAL_GetTick();
	uint8_t blink_on = ((tick % 200) < 100) ? 1 : 0; // 50% duty, 200ms period
	
	if(mode == 2){ // AlwaysOn (Blink on press)
		if(pressed) return blink_on; // Blink when pressed
		else return 1; // Always ON when released
	} else if (mode == 1){ // Reverse (Inverted)
		return !pressed;
	} else { // Normal
		return pressed;
	}
}

void sw_led_init(void){
	// Scan all commands in EEPROM, and build the table of whether the LED should toggle with the switch, or be momentary
	for(int page=0; page<8; page++){
		for(int sw=0; sw<8; sw++){
			// Clear the toggle bit
			a_sw_obj[sw].led_cmd_toggle &= ~(1<<page);

			for(int cmd=0; cmd<MIDI_NUM_COMMANDS_PER_SWITCH; cmd++){
				uint8_t *pCmd = get_rom_pointer(page, sw, cmd);
				if(midiCmd_get_cmd_toggle(pCmd)){
					a_sw_obj[sw].led_cmd_toggle |= (1<<page);
				}
			}

			// Same for the long press command set
			a_sw_obj[sw].long_cmd_present &= ~(1<<page);
			a_sw_obj[sw].long_cmd_toggle &= ~(1<<page);
			for(int cmd=0; cmd<MIDI_NUM_COMMANDS_PER_SWITCH; cmd++){
				uint8_t *pCmd = get_long_rom_pointer(page, sw, cmd);
				if(cmd_is_present(pCmd)){
					a_sw_obj[sw].long_cmd_present |= (1<<page);
					if(midiCmd_get_cmd_toggle(pCmd)){
						a_sw_obj[sw].long_cmd_toggle |= (1<<page);
					}
				}
			}
			a_sw_obj[sw].press_state = PRESS_IDLE;
		}
	}

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
	case CMD_START_NIBBLE:
		status = midiCmd_send_start_command();
		break;
	case CMD_STOP_NIBBLE:
		status = midiCmd_send_stop_command();
		break;
	default:
		break;
	}

	if (status == ERROR_BUFFERS_FULL) {
		Error("Buffers full");
 	}
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
	case CMD_START_NIBBLE:
		break;
	case CMD_STOP_NIBBLE:
		break;
	default:
		break;
	}

	if (status == ERROR_BUFFERS_FULL) {
		Error("Buffers full");
 	}
}

void set_led(uint8_t sw_no, uint8_t state){
	GPIO_PinState pinState = (state) ? GPIO_PIN_RESET : GPIO_PIN_SET;
	HAL_GPIO_WritePin(a_sw_obj[sw_no].led_gpio_port, a_sw_obj[sw_no].led_gpio_pin, pinState);

}

void update_leds_on_bank_change(void){
	for(int i=0; i<8; i++){
		if(a_sw_obj[i].led_cmd_toggle & (1<<switch_current_page)){
			uint8_t mode = get_button_led_mode(i);
			uint8_t active = get_sw_toggle_state(&a_sw_obj[i]);
			uint8_t state = calculate_led_state(active, mode);
			set_led(i, state ? SET : RESET);
		} else {
			// Update based on mode (assuming released state)
			uint8_t mode = get_button_led_mode(i);
			// For update, we assume Not Pressed. 
			// If AlwaysOn -> ON. If Reverse -> ON. Normal -> OFF.
			uint8_t state = calculate_led_state(0, mode);
			set_led(i, state ? SET : RESET);
		}
	}
	
	// Also update Bank LEDs initial state
	{
		uint8_t mode_down = get_bank_down_led_mode();
		// SW_E Down
		uint8_t state = calculate_led_state(0, mode_down);
		HAL_GPIO_WritePin(LED_E_GPIO_Port, LED_E_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);
		
		uint8_t mode_up = get_bank_up_led_mode();
		// SW_5 Up
		state = calculate_led_state(0, mode_up);
		HAL_GPIO_WritePin(LED_5_GPIO_Port, LED_5_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);
	}
}

// LED of a momentary (non toggle) button following the physical press
static void set_momentary_led(uint8_t i, uint8_t pressed){
	if(!(a_sw_obj[i].led_cmd_toggle & (1<<switch_current_page))){
		uint8_t mode = get_button_led_mode(i);
		uint8_t state = calculate_led_state(pressed, mode);
		set_led(i, state ? SET : RESET);
	}
}

static void fire_short_down(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	toggle_sw_state(sw);

	// Either toggle the LED, or set it if not toggling
	if(sw->led_cmd_toggle & (1<<switch_current_page)){
		uint8_t mode = get_button_led_mode(i);
		uint8_t active = get_sw_toggle_state(sw);
		uint8_t state = calculate_led_state(active, mode);
		set_led(i, state ? SET : RESET);
	} else {
		set_momentary_led(i, 1);
	}

	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		handle_cmd_sw_down(get_rom_pointer(switch_current_page, i, j), get_sw_toggle_state(sw));
	}
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
	sw->long_toggle_state ^= (1 << switch_current_page);
	state_store_mark_dirty();
	uint8_t toggleState = (sw->long_toggle_state >> switch_current_page) & 1;
	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		handle_cmd_sw_down(get_long_rom_pointer(switch_current_page, i, j), toggleState);
	}
}

static void fire_long_up(uint8_t i){
	sw_t *sw = &a_sw_obj[i];
	set_momentary_led(i, 0);
	uint8_t toggleState = (sw->long_toggle_state >> switch_current_page) & 1;
	for(int j=0; j<MIDI_NUM_COMMANDS_PER_SWITCH; j++){
		handle_cmd_sw_up(get_long_rom_pointer(switch_current_page, i, j), toggleState);
	}
}

void handle_switches(void){
	if(is_app_suspended) return;

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
				if(sw->long_cmd_present & (1<<switch_current_page)){
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
			if(a_sw_obj[i].led_cmd_toggle & (1<<switch_current_page)){
				// Toggle Mode: Active if toggle state is ON
				is_active = get_sw_toggle_state(&a_sw_obj[i]);
			} else {
				// Momentary Mode: Active if physically pressed
				if(!HAL_GPIO_ReadPin(a_sw_obj[i].sw_gpio_port, a_sw_obj[i].sw_gpio_pin)){
					is_active = 1;
				}
			}
			uint8_t state = calculate_led_state(is_active, mode);
			set_led(i, state ? SET : RESET);
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
		HAL_GPIO_WritePin(LED_E_GPIO_Port, LED_E_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);
	}

	// Bank Up Switch State
	uint8_t sw_5_down = !HAL_GPIO_ReadPin(SW_5_GPIO_Port, SW_5_Pin);
	if(bank_up_mode == 2 && sw_5_down) {
		uint8_t state = calculate_led_state(1, bank_up_mode);
		HAL_GPIO_WritePin(LED_5_GPIO_Port, LED_5_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);
	}


	// The bank change switches logic (Event based)
	if(port_A_switches_changed & SW_E_Pin){
		port_A_switches_changed &= ~SW_E_Pin;

		if(!HAL_GPIO_ReadPin(SW_E_GPIO_Port, SW_E_Pin)){
			// Bank Down Pressed
			uint8_t state = calculate_led_state(1, bank_down_mode);
			HAL_GPIO_WritePin(LED_E_GPIO_Port, LED_E_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);

			if(switch_current_page > 0){
				switch_current_page--;
				update_leds_on_bank_change();
				display_setBankName(switch_current_page);
				state_store_mark_dirty();
			}
		} else {
			// Bank Down Released
			uint8_t state = calculate_led_state(0, bank_down_mode);
			HAL_GPIO_WritePin(LED_E_GPIO_Port, LED_E_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);
		}
	}

	if(port_B_switches_changed & SW_5_Pin){
		port_B_switches_changed &= ~SW_5_Pin;

		if(!HAL_GPIO_ReadPin(SW_5_GPIO_Port, SW_5_Pin)){
			// Bank Up Pressed
			uint8_t state = calculate_led_state(1, bank_up_mode);
			HAL_GPIO_WritePin(LED_5_GPIO_Port, LED_5_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);

			if(switch_current_page < 7){
				switch_current_page++;
				update_leds_on_bank_change();
				display_setBankName(switch_current_page);
				state_store_mark_dirty();
			}
		} else {
			// Bank Up Released
			uint8_t state = calculate_led_state(0, bank_up_mode);
			HAL_GPIO_WritePin(LED_5_GPIO_Port, LED_5_Pin, state ? GPIO_PIN_RESET : GPIO_PIN_SET);
		}
	}
}


void set_all_leds(uint8_t state){
	// Command LEDs
	for(int i=0; i<8; i++){
		set_led(i, state);
	}

	// Bank LEDs
	GPIO_PinState pinState = (state) ? GPIO_PIN_RESET : GPIO_PIN_SET;
	HAL_GPIO_WritePin(LED_E_GPIO_Port, LED_E_Pin, pinState);
	HAL_GPIO_WritePin(LED_5_GPIO_Port, LED_5_Pin, pinState);
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

void sw_get_toggle_states(uint8_t out[8]){
	for(int i=0; i<8; i++){
		out[i] = a_sw_obj[i].switch_toggle_state;
	}
}

void sw_get_long_toggle_states(uint8_t out[8]){
	for(int i=0; i<8; i++){
		out[i] = a_sw_obj[i].long_toggle_state;
	}
}

void sw_restore_state(uint8_t page, const uint8_t toggles[8], const uint8_t long_toggles[8]){
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
