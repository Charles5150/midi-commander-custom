/*
 * health.h
 *
 * What the pedal can tell about itself over a long run: how much stack it
 * never reached, and how long it has been on.
 */

#ifndef INC_HEALTH_H_
#define INC_HEALTH_H_

#include <stdint.h>

void health_paint_stack(void);
uint32_t health_stack_free(void);
uint32_t health_uptime_s(void);

#endif /* INC_HEALTH_H_ */
