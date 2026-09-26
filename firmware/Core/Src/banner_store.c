/*
 * banner_store.c
 *
 * One flash page at FLASH_BANNER_ADDR holds the banner's own text:
 *   [0]      length, 1 to BANNER_TEXT_MAX
 *   [1]      check byte: the text's bytes summed, plus the length, xor 0xA5
 *   [2..3]   marker, written last so a torn write leaves no text
 *   [4..]    the text, printable ASCII
 *
 * The page starts out erased, and a blank or damaged one reads as no text.
 */

#include "banner_store.h"
#include "main.h"
#include "flash_midi_settings.h"

#define BANNER_MARKER	(0xB47EU)
#define BANNER_TEXT_OFF	(4U)

static const uint8_t *page(void){
	return (const uint8_t*)FLASH_BANNER_ADDR;
}

static uint8_t check_byte(const uint8_t *text, uint8_t len){
	uint8_t sum = len;
	for(uint8_t i=0; i<len; i++) sum += text[i];
	return sum ^ 0xA5U;
}

static bool printable(const uint8_t *text, uint8_t len){
	for(uint8_t i=0; i<len; i++){
		if(text[i] < 32 || text[i] > 126) return false;
	}
	return true;
}

uint8_t banner_store_get(const char **text){
	const uint8_t *p = page();
	uint8_t len = p[0];
	if((p[2] | (p[3] << 8)) != BANNER_MARKER || len == 0 || len > BANNER_TEXT_MAX
			|| !printable(p + BANNER_TEXT_OFF, len)
			|| p[1] != check_byte(p + BANNER_TEXT_OFF, len)){
		return 0;
	}
	*text = (const char*)(p + BANNER_TEXT_OFF);
	return len;
}

bool banner_store_set(const uint8_t *text, uint8_t len){
	if(len > BANNER_TEXT_MAX || !printable(text, len)) return false;

	uint32_t pageError;
	FLASH_EraseInitTypeDef eraseInit = {
			.TypeErase = FLASH_TYPEERASE_PAGES,
			.Banks = FLASH_BANK_1,
			.PageAddress = FLASH_BANNER_ADDR,
			.NbPages = 1
	};

	// Called from the USB interrupt, like the other flash writes; with
	// interrupts off nothing else can reach the HAL flash lock meanwhile
	__disable_irq();
	HAL_FLASH_Unlock();
	HAL_StatusTypeDef status = HAL_FLASHEx_Erase(&eraseInit, &pageError);
	for(uint8_t i=0; i<len && status == HAL_OK; i+=2){
		uint16_t half = text[i] | ((i+1 < len ? text[i+1] : 0xFF) << 8);
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, FLASH_BANNER_ADDR + BANNER_TEXT_OFF + i, half);
	}
	if(len && status == HAL_OK){
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, FLASH_BANNER_ADDR,
				len | (check_byte(text, len) << 8));
	}
	if(len && status == HAL_OK){
		status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, FLASH_BANNER_ADDR + 2, BANNER_MARKER);
	}
	HAL_FLASH_Lock();
	__enable_irq();
	return status == HAL_OK;
}
