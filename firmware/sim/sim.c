/*
 * sim.c
 *
 * The pedal without the pedal: the firmware's own sources, built for
 * WebAssembly (sim/build.sh), with this file in place of main.c, the
 * interrupt handlers and ST's HAL. The web configurator loads the module and
 * talks to it over the same SysEx the pedal answers, so every tab works on it
 * as on the pedal: see web/sim.js.
 *
 * Time only moves when the page asks: sim_run(ms) runs each millisecond as
 * the chip does, SysTick's work first (switch scan, tempo, display lines),
 * then one pass of the main loop. The flash is 256 kB of the module's memory
 * at FLASH_BASE: the page fills it with a configuration and keeps it across
 * restarts, for which it starts a fresh module (sim_restart_asked).
 *
 * What comes out, USB MIDI, the DIN output and the computer keyboard (HID),
 * goes into one queue of records: port, length, bytes. Nothing here is the
 * firmware's logic: that is all in Core/Src, exactly as the pedal runs it.
 */
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "switch_router.h"
#include "display.h"
#include "leds.h"
#include "expression.h"
#include "tempo.h"
#include "sleep.h"
#include "state_store.h"
#include "restart_state.h"
#include "kemper.h"
#include "gt1000.h"
#include "latency.h"
#include "dfu_entry.h"
#include "ssd1306.h"
#include "usbd_midi_if.h"
#include <string.h>

void sw_scan(void);	// declared where stm32f1xx_it.c calls it

#define EXPORT(name)	__attribute__((export_name(#name)))

// --- The chip ---------------------------------------------------------------
uint32_t SystemCoreClock = 72000000U;
volatile uint32_t sim_primask = 0;
volatile uint32_t sim_ipsr = 0;
uint32_t sim_reset_flags = 0;
DWT_Type sim_dwt;
CoreDebug_Type sim_coredebug;
SCB_Type sim_scb;
GPIO_TypeDef sim_gpio[3];
TIM_TypeDef sim_tim2;

UART_HandleTypeDef huart2 = { .Instance = 2, .gState = HAL_UART_STATE_READY };
uint8_t f_sys_config_complete = 0;

static volatile uint32_t tick = 0;
static bool restart_asked = false;
static bool uart_done_pending = false;
static uint16_t adc_value[2];		// what each expression jack reads, 0..4095

#define IRQ_SYSTICK		(15U)
#define IRQ_USB			(16U + 20U)
#define IRQ_DMA			(16U + 16U)

uint32_t HAL_GetTick(void){ return tick; }
void HAL_IncTick(void){ tick++; }

// The waits in the boot and in the display driver: time just goes on
void HAL_Delay(uint32_t ms){ tick += ms; }

void NVIC_SystemReset(void){ restart_asked = true; }

void Error_Handler(void){ restart_asked = true; }
void Error(char *msg){ (void)msg; Error_Handler(); }

// --- Flash ------------------------------------------------------------------
// As on the chip: a half word can only be written where the page is erased,
// or turned to zero.
HAL_StatusTypeDef HAL_FLASH_Unlock(void){ return HAL_OK; }
HAL_StatusTypeDef HAL_FLASH_Lock(void){ return HAL_OK; }

static bool in_flash(uint32_t address, uint32_t size){
	return address >= FLASH_BASE && address + size <= FLASH_BASE + SIM_FLASH_SIZE;
}

HAL_StatusTypeDef HAL_FLASH_Program(uint32_t type, uint32_t address, uint64_t data){
	if(type != FLASH_TYPEPROGRAM_HALFWORD || (address & 1) || !in_flash(address, 2)) return HAL_ERROR;
	volatile uint16_t *p = (volatile uint16_t *)address;
	uint16_t value = (uint16_t)data;
	if(*p != 0xFFFF && value != 0) return HAL_ERROR;
	*p = value;
	return HAL_OK;
}

HAL_StatusTypeDef HAL_FLASHEx_Erase(FLASH_EraseInitTypeDef *init, uint32_t *page_error){
	uint32_t size = init->NbPages * FLASH_PAGE_SIZE;
	*page_error = 0xFFFFFFFFU;
	if((init->PageAddress % FLASH_PAGE_SIZE) || !in_flash(init->PageAddress, size)){
		*page_error = init->PageAddress;
		return HAL_ERROR;
	}
	memset((void *)init->PageAddress, 0xFF, size);
	return HAL_OK;
}

// --- The display: each transfer is over as soon as it starts ----------------
void i2c_display_init(void){}
void i2c_display_reset(void){}
uint8_t i2c_display_busy(void){ return 0; }
uint8_t i2c_display_stuck(void){ return 0; }

// What the panel shows: each page as the last line sent for it left it
static uint8_t panel[SSD1306_WIDTH * 8];
// Transfers still to fail before the DMA starts, as on a NACK of the address
static uint32_t i2c_fails = 0;

uint8_t i2c_display_write(const uint8_t *data, uint16_t size){
	if(i2c_fails){
		i2c_fails--;
		return 0;
	}
	// A line: page address, two column commands, then the page's data
	if(size == SSD1306_WIDTH + 7 && data[0] == 0x80 && (data[1] & 0xF8) == 0xB0){
		memcpy(&panel[SSD1306_WIDTH * (data[1] & 7)], data + 7, SSD1306_WIDTH);
	}
	uint32_t ipsr = sim_ipsr;
	sim_ipsr = IRQ_DMA;
	ssd1306_TxDone();
	sim_ipsr = ipsr;
	return 1;
}

// --- What goes out ----------------------------------------------------------
#define PORT_USB	(0U)
#define PORT_DIN	(1U)
#define PORT_KEYS	(2U)

static uint8_t out_queue[8192];
static uint32_t out_len = 0;

static void out_put(uint8_t port, const uint8_t *data, uint16_t size){
	if(out_len + 3U + size > sizeof(out_queue)) return;	// the page stopped reading
	out_queue[out_len++] = port;
	out_queue[out_len++] = (uint8_t)(size & 0xFF);
	out_queue[out_len++] = (uint8_t)(size >> 8);
	memcpy(out_queue + out_len, data, size);
	out_len += size;
}

// USB MIDI events of four bytes, as the USB class would send them
void USBD_MIDI_SendPacket(uint8_t *buffer, uint8_t len){
	out_put(PORT_USB, buffer, len);
}

uint8_t HID_SendReport_FS(uint8_t *report, uint16_t len){
	out_put(PORT_KEYS, report, len);
	return USBD_OK;
}

// The DIN output: the transfer ends at the next interrupt point, so the
// driver sees it busy for a moment, as it does at 31250 baud
HAL_StatusTypeDef HAL_UART_Transmit_DMA(UART_HandleTypeDef *h, uint8_t *data, uint16_t size){
	if(h->gState != HAL_UART_STATE_READY) return HAL_BUSY;
	h->gState = HAL_UART_STATE_BUSY_TX;
	out_put(PORT_DIN, data, size);
	uart_done_pending = true;
	return HAL_OK;
}

static void uart_interrupts(void){
	for(uint8_t n = 0; uart_done_pending && n < 16; n++){
		uart_done_pending = false;
		huart2.gState = HAL_UART_STATE_READY;
		sim_ipsr = IRQ_DMA;
		HAL_UART_TxCpltCallback(&huart2);
		sim_ipsr = 0;
	}
}

// --- The expression pedals --------------------------------------------------
bool adc_sample(uint32_t channel, uint32_t *value){
	*value = adc_value[channel == ADC_CHANNEL_8 ? 1 : 0];
	return true;
}
void adc_stop(void){}

// --- No bootloader to go to -------------------------------------------------
bool dfu_entry_possible(void){ return false; }
void dfu_entry_request(void){}
void dfu_entry_task(void){}

// --- sin and cos, for the display library's arcs ----------------------------
double sin(double x){
	const double pi = 3.14159265358979323846;
	while(x > pi) x -= 2 * pi;
	while(x < -pi) x += 2 * pi;
	double term = x, sum = x;
	for(int n = 1; n < 10; n++){
		term *= -x * x / ((2 * n) * (2 * n + 1));
		sum += term;
	}
	return sum;
}
double cos(double x){ return sin(x + 1.57079632679489661923); }

// --- The switches -----------------------------------------------------------
// 1 2 3 4 A B C D, then Bank Down and Bank Up. A switch pulls its pin low.
typedef struct { GPIO_TypeDef *port; uint16_t pin; } pin_t;
static const pin_t switch_pins[10] = {
	{ SW_1_GPIO_Port, SW_1_Pin }, { SW_2_GPIO_Port, SW_2_Pin },
	{ SW_3_GPIO_Port, SW_3_Pin }, { SW_4_GPIO_Port, SW_4_Pin },
	{ SW_A_GPIO_Port, SW_A_Pin }, { SW_B_GPIO_Port, SW_B_Pin },
	{ SW_C_GPIO_Port, SW_C_Pin }, { SW_D_GPIO_Port, SW_D_Pin },
	{ SW_E_GPIO_Port, SW_E_Pin }, { SW_5_GPIO_Port, SW_5_Pin },
};

// --- Boot and the millisecond -----------------------------------------------
typedef enum { BOOT_BANNER, BOOT_USB, RUNNING } phase_t;
static phase_t phase;
static uint32_t phase_until;

// What main() finds at boot and uses once the banner is over
static bool boot_restore, boot_restarted;
static uint8_t boot_bank;
static uint32_t boot_toggles[8], boot_long[8], boot_double[8];
static live_state_t live;

static void systick(void){
	tick++;
	sim_dwt.CYCCNT += SystemCoreClock / 1000U;
	sim_ipsr = IRQ_SYSTICK;
	sw_scan();
	tempo_tick_1ms();
	ssd1306_tick();
	sim_ipsr = 0;
	uart_interrupts();
}

// main() up to its first wait. reset_flags is RCC_FLAG_IWDGRST after the
// watchdog, which never bites here: the page passes 0.
EXPORT(sim_boot) void sim_boot(uint32_t reset_flags){
	sim_reset_flags = reset_flags;
	for(int i = 0; i < 3; i++) sim_gpio[i].IDR = 0xFFFF;	// no switch down

	latency_init();
	display_init();
	flash_settings_recover();

	uint8_t saved_slot = 0;
	bool have_state = state_store_load(&boot_bank, boot_toggles, boot_long, boot_double, &saved_slot);
	boot_restarted = restart_state_load(&live);
	if(boot_restarted){
		boot_bank = live.bank;
		saved_slot = live.slot;
		memcpy(boot_toggles, live.toggles, sizeof(boot_toggles));
		memcpy(boot_long, live.long_toggles, sizeof(boot_long));
		memcpy(boot_double, live.double_toggles, sizeof(boot_double));
	}
	if((have_state || boot_restarted) && saved_slot != 0 && flash_settings_slot_valid(saved_slot)){
		flash_settings_select(saved_slot);
	}
	usb_ports_latch();
	display_setConfigName();
	leds_init();
	sw_init();
	sw_led_init();

	boot_restore = (boot_restarted || (pGlobalSettings[GLOBAL_SETTINGS_REMEMBER_STATE] == 1 && have_state))
			&& saved_slot == flash_settings_active_slot();
	phase = BOOT_BANNER;
	phase_until = tick + 1000U;
}

// main() after its waits, up to its loop
static void boot_finish(void){
	bool safe_mode = sw_check_safe_mode();
	f_sys_config_complete = 1;
	if(!safe_mode && boot_restore){
		sw_restore_state(boot_bank, boot_toggles, boot_long, boot_double);
	}
	display_setBankName(sw_get_current_page());
	expression_init();
	if(safe_mode){
		expression_quiet_start();
		display_show_safe_mode();
	} else if(boot_restarted){
		display_show_restarted();
	}
	tempo_init();
	if(boot_restarted && !safe_mode) tempo_set_bpm(live.bpm);
	sleep_init();
	phase = RUNNING;
}

// One millisecond of the pedal
static void millisecond(void){
	systick();
	switch(phase){
	case BOOT_BANNER:
	case BOOT_USB:
		display_banner_task();
		if(tick >= phase_until){
			if(phase == BOOT_BANNER){
				phase = BOOT_USB;	// where the pedal shows up on USB
				phase_until = tick + 200U;
			} else {
				boot_finish();
			}
		}
		break;
	case RUNNING:
		sysex_flash_task();
		if(sysex_upload_paused()) break;
		handle_switches();
		expression_task();
		state_store_task();
		restart_state_task();
		tempo_task();
		display_task();
		sleep_task();
		kemper_task();
		gt1000_task();
		dfu_entry_task();
		break;
	}
	uart_interrupts();
}

// --- What the page calls ----------------------------------------------------
EXPORT(sim_run) void sim_run(uint32_t ms){
	for(uint32_t i = 0; i < ms && !restart_asked; i++){
		millisecond();
	}
}

EXPORT(sim_ready) bool sim_ready(void){ return phase == RUNNING; }
EXPORT(sim_restart_asked) bool sim_restart_asked(void){ return restart_asked; }
EXPORT(sim_tick) uint32_t sim_tick(void){ return tick; }
EXPORT(sim_flash) uint8_t *sim_flash(void){ return (uint8_t *)FLASH_BASE; }
EXPORT(sim_flash_size) uint32_t sim_flash_size(void){ return SIM_FLASH_SIZE; }

// A switch going down or up, 0..9: 1 2 3 4 A B C D, Bank Down, Bank Up
EXPORT(sim_switch) void sim_switch(uint32_t id, bool down){
	if(id >= 10) return;
	if(down) switch_pins[id].port->IDR &= ~(uint32_t)switch_pins[id].pin;
	else switch_pins[id].port->IDR |= switch_pins[id].pin;
}

// An expression pedal, 0..1: 0 heel .. 4095 toe. An empty jack reads 0.
EXPORT(sim_pedal) void sim_pedal(uint32_t id, uint32_t value){
	if(id < 2) adc_value[id] = value > 4095 ? 4095 : (uint16_t)value;
}

// USB MIDI events coming in from the computer, four bytes each
static uint8_t in_buffer[256];
EXPORT(sim_in_buffer) uint8_t *sim_in_buffer(void){ return in_buffer; }
EXPORT(sim_usb_in) void sim_usb_in(uint32_t len){
	if(len > sizeof(in_buffer)) len = sizeof(in_buffer);
	sim_ipsr = IRQ_USB;
	MIDI_DataRx(in_buffer, (uint16_t)len);
	sim_ipsr = 0;
	uart_interrupts();
}

// What went out since the last call: records of port, length (2 bytes), data
EXPORT(sim_out) uint8_t *sim_out(void){ return out_queue; }
EXPORT(sim_out_len) uint32_t sim_out_len(void){ return out_len; }
EXPORT(sim_out_clear) void sim_out_clear(void){ out_len = 0; }

// The screen as the pedal holds it, 130 x 64: a byte per column per 8 rows
EXPORT(sim_screen) const uint8_t *sim_screen(void){ return ssd1306_GetBuffer(); }
EXPORT(sim_screen_on) bool sim_screen_on(void){ return ssd1306_GetDisplayOn(); }
EXPORT(sim_panel) const uint8_t *sim_panel(void){ return panel; }
EXPORT(sim_i2c_fail) void sim_i2c_fail(uint32_t n){ i2c_fails = n; }

// The ten LEDs, 0..16, in the order of the switches
static uint8_t led_out[10];
EXPORT(sim_leds) const uint8_t *sim_leds(void){
	for(uint8_t i = 0; i < LEDS_COUNT; i++) led_out[i] = leds_get(i);
	return led_out;
}
