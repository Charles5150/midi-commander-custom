/*
 * dfu_entry.c
 *
 * A firmware update with no switches held at power on. The stock bootloader
 * in the first 12 kB is ST's DFU demo with MeloAudio's switch check added: at
 * power on it waits a moment, and it jumps to the firmware only when Bank
 * Down and D are up and the firmware's first word, its initial stack pointer
 * at 0x08003000, looks like a RAM address. Otherwise it stays in DFU. So
 * writing zero over that word and restarting brings the pedal up in DFU, and
 * the next image flashed there brings a good word back with it.
 *
 * The F1 lets a programmed halfword be written to zero without erasing its
 * page, and the firmware running has no more use for the word, as the stack
 * pointer was loaded from it at reset. The bootloader is never written. If
 * nothing is flashed afterwards the pedal keeps starting in DFU until
 * something is, which is where the switches would have put it anyway.
 */

#include "dfu_entry.h"
#include "main.h"
#include "ssd1306.h"

#define APP_START		(FLASH_BASE + 0x3000U)	// where the bootloader looks for the firmware
#define DFU_REPLY_MS	(100U)	// long enough for the answer to leave over USB
#define DFU_SCREEN_MS	(100U)	// the most the screen takes to be sent

extern volatile uint8_t display_transmit_line;	// ssd1306.c: 0 once the screen has gone out
extern const uint32_t g_pfnVectors[];	// the startup file's vector table, where the linker put it

static volatile bool pending = false;
static volatile uint32_t asked_at;

bool dfu_entry_possible(void){
	// A build linked at the start of flash has its own code at 0x08003000.
	// Asked of the linker, not of VTOR, which main() sets the same in both.
	return (uint32_t)g_pfnVectors == APP_START;
}

void dfu_entry_request(void){
	if(!dfu_entry_possible()) return;
	asked_at = HAL_GetTick();
	pending = true;
}

// Nothing in the bootloader touches the display, so this stays on it while
// the pedal is in DFU, where the stock pedal shows nothing at all
static void show_update_screen(void){
	ssd1306_SetDisplayOn(1);
	ssd1306_Fill(Black);
	ssd1306_SetCursor(20, 10);
	ssd1306_WriteString("FIRMWARE", Font_11x18, White);
	ssd1306_SetCursor(31, 32);
	ssd1306_WriteString("UPDATE", Font_11x18, White);
	ssd1306_SetCursor(40, 54);
	ssd1306_WriteString("DFU MODE", Font_6x8, White);
	ssd1306_UpdateScreen();

	uint32_t start = HAL_GetTick();
	while(display_transmit_line != 0 && HAL_GetTick() - start < DFU_SCREEN_MS){
		__NOP();
	}
}

void dfu_entry_task(void){
	if(!pending || HAL_GetTick() - asked_at < DFU_REPLY_MS) return;

	show_update_screen();

	__disable_irq();
	HAL_FLASH_Unlock();
	HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, APP_START, 0);
	HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD, APP_START + 2U, 0);
	HAL_FLASH_Lock();

	NVIC_SystemReset();
}
