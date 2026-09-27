/* stdlib.h for the simulator */
#ifndef SIM_STDLIB_H
#define SIM_STDLIB_H
#include <stddef.h>
static inline int abs(int x){ return x < 0 ? -x : x; }
#endif
