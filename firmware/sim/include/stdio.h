/* stdio.h for the simulator: the firmware's own snprintf, tiny_printf.c */
#ifndef SIM_STDIO_H
#define SIM_STDIO_H
#include <stddef.h>
int snprintf(char *out, size_t size, const char *fmt, ...);
#endif
