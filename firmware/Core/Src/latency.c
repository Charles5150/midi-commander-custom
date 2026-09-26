/*
 * latency.c
 *
 * The time from a switch going down to the first MIDI message it sends
 * being handed to USB, measured by the pedal itself with the core's cycle
 * counter. A computer timing the same thing sees its own USB and MIDI
 * stack as well, which on a Mac is several milliseconds in steps of five,
 * far more than the pedal's part.
 *
 * The start is when the change is first seen: the 1 ms switch scan for a
 * foot, the USB interrupt that queues a virtual press for the computer.
 * The oldest change not yet handled is kept, so a press that waits behind
 * a slow pass of the main loop counts that wait. Only presses that fire at
 * once are timed: a button with a long or double press waits on purpose,
 * and a bank switch fires on its release, which is then the start.
 * Only messages sent from the main loop close a measurement, not the
 * answers the USB interrupt sends to SysEx, and a press that sends nothing
 * over USB leaves nothing behind.
 */

#include "latency.h"
#include "stm32f1xx_hal.h"

#define CYCLES_PER_US	(SystemCoreClock / 1000000U)
#define LATENCY_US_MAX	(0x1FFFFFU)	// three 7-bit bytes

static volatile uint32_t mark_cycles;
static volatile uint8_t mark_valid = 0;
static uint32_t pass_cycles;		// the mark this pass of handle_switches took
static uint8_t pass_valid = 0;
static uint32_t open_cycles;		// a press firing now, waiting for its first message
static uint8_t open = 0;

static uint32_t samples[LATENCY_SAMPLES];
static uint8_t sample_next = 0;
static uint8_t sample_count = 0;
static uint16_t total = 0;
static uint32_t worst = 0;

void latency_init(void){
	CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
	DWT->CYCCNT = 0;
	DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

uint32_t latency_now(void){
	return DWT->CYCCNT;
}

// A switch changed at cycle when: kept unless an older change is still waiting
void latency_mark(uint32_t when){
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	if(!mark_valid){
		mark_cycles = when;
		mark_valid = 1;
	}
	if(!primask) __enable_irq();
}

// At the start of a pass of handle_switches: the changes it will handle
void latency_take_mark(void){
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	pass_valid = mark_valid;
	pass_cycles = mark_cycles;
	mark_valid = 0;
	if(!primask) __enable_irq();
}

// A press fires now
void latency_begin(void){
	open = pass_valid;
	open_cycles = pass_cycles;
}

void latency_end(void){
	open = 0;
}

// A message goes out over USB
void latency_sent(void){
	if(!open || __get_IPSR() != 0) return;
	open = 0;
	uint32_t us = (DWT->CYCCNT - open_cycles) / CYCLES_PER_US;
	if(us > LATENCY_US_MAX) us = LATENCY_US_MAX;
	uint32_t primask = __get_PRIMASK();
	__disable_irq();	// read by the SysEx answer, from the USB interrupt
	samples[sample_next] = us;
	sample_next = (uint8_t)((sample_next + 1) % LATENCY_SAMPLES);
	if(sample_count < LATENCY_SAMPLES) sample_count++;
	if(total < 0x3FFF) total++;
	if(us > worst) worst = us;
	if(!primask) __enable_irq();
}

static uint8_t *put_us(uint8_t *p, uint32_t us){
	*(p++) = (us >> 14) & 0x7F;
	*(p++) = (us >> 7) & 0x7F;
	*(p++) = us & 0x7F;
	return p;
}

/*
 * The SysEx answer's body: presses timed (two 7-bit bytes), the slowest in
 * microseconds, then the last ones, oldest first, three bytes each.
 * Returns its length. clear starts counting again.
 */
uint8_t latency_report(uint8_t *out, uint8_t clear){
	uint8_t *p = out;
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	*(p++) = (total >> 7) & 0x7F;
	*(p++) = total & 0x7F;
	p = put_us(p, worst);
	uint8_t first = (uint8_t)((sample_next + LATENCY_SAMPLES - sample_count) % LATENCY_SAMPLES);
	for(uint8_t i=0; i<sample_count; i++){
		p = put_us(p, samples[(first + i) % LATENCY_SAMPLES]);
	}
	if(clear){
		sample_count = 0;
		total = 0;
		worst = 0;
	}
	if(!primask) __enable_irq();
	return (uint8_t)(p - out);
}
