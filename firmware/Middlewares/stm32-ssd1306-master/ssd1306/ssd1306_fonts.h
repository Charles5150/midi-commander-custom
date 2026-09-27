#include <stdint.h>

#ifndef __SSD1306_FONTS_H__
#define __SSD1306_FONTS_H__

#include "ssd1306_conf.h"

// A font: its characters from the space to Last, each FontHeight rows of
// FontWidth bits packed one after the other, the leftmost pixel first, every
// character from a byte boundary. tools/pack_fonts.py makes the tables from
// the pictures in fonts/, and ssd1306_Glyph unpacks a character.
typedef struct {
	uint8_t FontWidth;    /*!< Font width in pixels */
	uint8_t FontHeight;   /*!< Font height in pixels */
	uint8_t Last;         /*!< Last character in data, from 32 */
	const uint8_t *data;  /*!< The packed rows */
} FontDef;

// Rows of the tallest font: the size of the buffer ssd1306_Glyph unpacks into
#define SSD1306_FONT_MAX_HEIGHT 18

#ifdef SSD1306_INCLUDE_FONT_6x8
extern const FontDef Font_6x8;
#endif
#ifdef SSD1306_INCLUDE_FONT_7x10
extern const FontDef Font_7x10;
#endif
#ifdef SSD1306_INCLUDE_FONT_11x18
extern const FontDef Font_11x18;
#endif
#endif // __SSD1306_FONTS_H__
