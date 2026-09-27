/*
 * sim_libc.c: the handful of C library functions the firmware's sources call,
 * for the simulator, which builds for WebAssembly without a C library.
 * snprintf is the firmware's own, Core/Src/tiny_printf.c.
 */
#include <string.h>
#include <stdint.h>

void *memcpy(void *dst, const void *src, size_t n){
	uint8_t *d = dst;
	const uint8_t *s = src;
	while(n--) *d++ = *s++;
	return dst;
}

void *memmove(void *dst, const void *src, size_t n){
	uint8_t *d = dst;
	const uint8_t *s = src;
	if(d < s){
		while(n--) *d++ = *s++;
	} else {
		while(n--) d[n] = s[n];
	}
	return dst;
}

void *memset(void *dst, int c, size_t n){
	uint8_t *d = dst;
	while(n--) *d++ = (uint8_t)c;
	return dst;
}

int memcmp(const void *a, const void *b, size_t n){
	const uint8_t *x = a, *y = b;
	for(; n; n--, x++, y++){
		if(*x != *y) return *x - *y;
	}
	return 0;
}

size_t strlen(const char *s){
	size_t n = 0;
	while(s[n]) n++;
	return n;
}

int strcmp(const char *a, const char *b){
	while(*a && *a == *b){ a++; b++; }
	return (uint8_t)*a - (uint8_t)*b;
}

char *strcpy(char *dst, const char *src){
	char *d = dst;
	while((*d++ = *src++)) {}
	return dst;
}
