/*
 * leds.c
 *
 * See leds.h. The LEDs are wired to VCC through a resistor, so a pin driven
 * low turns its LED on. Every PWM tick the ISR computes, per GPIO port, which
 * pins must be low (level > counter) and which high, and writes each port
 * once through BSRR, so the whole refresh costs a handful of register writes.
 */

#include "leds.h"
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"

#define PWM_TICK_HZ			(8000U)			// LEDS_LEVELS * 500 Hz refresh
#define DEFAULT_PERCENT		(100U)

typedef struct {
	GPIO_TypeDef *port;
	uint16_t pin;
} led_pin_t;

static const led_pin_t led_pins[LEDS_COUNT] = {
	{ LED_1_GPIO_Port, LED_1_Pin },
	{ LED_2_GPIO_Port, LED_2_Pin },
	{ LED_3_GPIO_Port, LED_3_Pin },
	{ LED_4_GPIO_Port, LED_4_Pin },
	{ LED_A_GPIO_Port, LED_A_Pin },
	{ LED_B_GPIO_Port, LED_B_Pin },
	{ LED_C_GPIO_Port, LED_C_Pin },
	{ LED_D_GPIO_Port, LED_D_Pin },
	{ LED_E_GPIO_Port, LED_E_Pin },	// Bank Down
	{ LED_5_GPIO_Port, LED_5_Pin },	// Bank Up
};

static volatile uint8_t led_level[LEDS_COUNT];
static volatile uint8_t pwm_counter = 0;
static uint8_t level_active = LEDS_LEVELS;
static uint8_t level_rest = LEDS_LEVELS;

static uint8_t percent_to_level(uint8_t percent){
	// 0xFF is blank flash; 0 is what configurations written before this
	// setting existed hold. Both mean "not set" and default to full brightness.
	if(percent == 0 || percent > 100) percent = DEFAULT_PERCENT;
	uint8_t level = (uint8_t)((percent * LEDS_LEVELS + 50U) / 100U);
	return level ? level : 1;	// 1 % still gives a faintly lit LED
}

uint8_t leds_level_active(void){ return level_active; }
uint8_t leds_level_rest(void){ return level_rest; }

void leds_set(uint8_t led, uint8_t level){
	if(led >= LEDS_COUNT) return;
	led_level[led] = (level > LEDS_LEVELS) ? LEDS_LEVELS : level;
}

void leds_set_all(uint8_t level){
	for(uint8_t i=0; i<LEDS_COUNT; i++){
		leds_set(i, level);
	}
}

void leds_init(void){
	level_active = percent_to_level(pGlobalSettings[GLOBAL_SETTINGS_LED_BRIGHTNESS]);
	level_rest   = percent_to_level(pGlobalSettings[GLOBAL_SETTINGS_LED_REST_BRIGHTNESS]);
	leds_set_all(0);

	// TIM2 on APB1: timer clock = 2 x PCLK1 = 72 MHz. 72e6 / 9 / 1000 = 8 kHz.
	__HAL_RCC_TIM2_CLK_ENABLE();
	TIM2->CR1 = 0;
	TIM2->PSC = 9 - 1;
	TIM2->ARR = 1000 - 1;
	TIM2->EGR = TIM_EGR_UG;			// load PSC/ARR
	TIM2->SR  = 0;
	TIM2->DIER = TIM_DIER_UIE;
	HAL_NVIC_SetPriority(TIM2_IRQn, 3, 0);	// below USB, DMA and the switch scan
	HAL_NVIC_EnableIRQ(TIM2_IRQn);
	TIM2->CR1 = TIM_CR1_CEN;
}

void TIM2_IRQHandler(void){
	if(!(TIM2->SR & TIM_SR_UIF)) return;
	TIM2->SR = ~TIM_SR_UIF;

	uint8_t counter = pwm_counter;
	pwm_counter = (uint8_t)((counter + 1) % LEDS_LEVELS);

	// Per port: pins to drive low (LED on) and high (LED off)
	uint32_t a_on = 0, a_off = 0, b_on = 0, b_off = 0, c_on = 0, c_off = 0;
	for(uint8_t i=0; i<LEDS_COUNT; i++){
		uint8_t on = led_level[i] > counter;
		GPIO_TypeDef *port = led_pins[i].port;
		uint32_t pin = led_pins[i].pin;
		if(port == GPIOA){ if(on) a_on |= pin; else a_off |= pin; }
		else if(port == GPIOB){ if(on) b_on |= pin; else b_off |= pin; }
		else { if(on) c_on |= pin; else c_off |= pin; }
	}
	// BSRR: low half sets (high = LED off), high half resets (low = LED on)
	if(a_on | a_off) GPIOA->BSRR = (a_on << 16) | a_off;
	if(b_on | b_off) GPIOB->BSRR = (b_on << 16) | b_off;
	if(c_on | c_off) GPIOC->BSRR = (c_on << 16) | c_off;
}
