/*
 * health.c
 *
 * Nothing is allocated at run time, so the one thing that can run short is
 * the stack, shared by the main loop and the interrupts. At start the RAM
 * between the end of the variables and the stack is filled with a pattern;
 * how much of it is still untouched from the bottom is the least the stack
 * has had to spare since. GET_STATE reports it with the time since start,
 * which also tells a test that the watchdog restarted the pedal, as the
 * restart itself puts everything back as it was (restart_state.c).
 */

#include "health.h"
#include "stm32f1xx_hal.h"

#define STACK_PATTERN	(0x5AA5C33CU)
#define STACK_MARGIN	(64U)		// bytes below the stack in use when painting

#ifndef SIM
extern uint32_t _end;				// the linker script: the end of .noinit

void health_paint_stack(void){
	uint32_t *p = &_end;
	uint32_t *top = (uint32_t*)(__get_MSP() - STACK_MARGIN);
	while(p < top){
		*(p++) = STACK_PATTERN;
	}
}

uint32_t health_stack_free(void){
	const uint32_t *p = &_end;
	const uint32_t *top = (const uint32_t*)__get_MSP();
	while(p < top && *p == STACK_PATTERN){
		p++;
	}
	return (uint32_t)((const uint8_t*)p - (const uint8_t*)&_end);
}
#else
void health_paint_stack(void){}
uint32_t health_stack_free(void){ return 0; }
#endif

uint32_t health_uptime_s(void){
	return HAL_GetTick() / 1000U;
}
