/*
 * tiny_printf.c
 *
 * A small snprintf in place of newlib's, which brought in about 2 kB of
 * formatter, malloc and friends for a few numbers on the display. The
 * linker takes this one and never pulls the library's in.
 *
 * It knows %u %d %s %c and %%, with a width and the '-' flag ("%3d",
 * "%-8s"). Anything else is copied out as it stands. Like the real one it
 * always ends the text, cutting it to fit, and returns the length the whole
 * text would have had.
 */

#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>

typedef struct {
	char *out;
	size_t size;
	size_t len;
} sink_t;

static void put(sink_t *s, char c){
	if(s->len + 1 < s->size) s->out[s->len] = c;
	s->len++;
}

static void put_field(sink_t *s, const char *text, size_t n, int width, int left){
	int pad = width > (int)n ? width - (int)n : 0;
	if(!left) while(pad-- > 0) put(s, ' ');
	while(n--) put(s, *text++);
	if(left) while(pad-- > 0) put(s, ' ');
}

int snprintf(char *out, size_t size, const char *fmt, ...){
	sink_t s = { out, size, 0 };
	va_list ap;
	va_start(ap, fmt);

	while(*fmt){
		if(*fmt != '%'){
			put(&s, *fmt++);
			continue;
		}
		const char *start = fmt++;
		int left = 0, width = 0;
		if(*fmt == '-'){ left = 1; fmt++; }
		while(*fmt >= '0' && *fmt <= '9') width = width * 10 + (*fmt++ - '0');

		char num[11];
		const char *text = num;
		size_t n = 0;
		switch(*fmt){
		case 'd': case 'u': {
			unsigned v;
			int neg = 0;
			if(*fmt == 'd'){
				int d = va_arg(ap, int);
				neg = d < 0;
				v = neg ? 0U - (unsigned)d : (unsigned)d;
			} else {
				v = va_arg(ap, unsigned);
			}
			char *p = num + sizeof(num);
			do { *--p = (char)('0' + v % 10); v /= 10; } while(v);
			if(neg) *--p = '-';
			text = p;
			n = (size_t)(num + sizeof(num) - p);
			break;
		}
		case 's':
			text = va_arg(ap, const char *);
			while(text[n]) n++;
			break;
		case 'c':
			num[0] = (char)va_arg(ap, int);
			n = 1;
			break;
		case '%':
			num[0] = '%';
			n = 1;
			break;
		default:	// not one of ours: copy it out as it stands
			text = start;
			n = (size_t)(fmt - start) + (*fmt ? 1 : 0);
			width = 0;
			break;
		}
		if(*fmt) fmt++;
		put_field(&s, text, n, width, left);
	}
	va_end(ap);

	if(size) out[s.len < size ? s.len : size - 1] = 0;
	return (int)s.len;
}
