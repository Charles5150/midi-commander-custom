#include "sleep.h"
#include "main.h"
#include "midi_defines.h"
#include "flash_midi_settings.h"
#include "switch_router.h"
#include "display.h"
#include "ssd1306.h"

#define SLEEP_MAX_MINUTES	(60U)
// How recent activity has to be to count as "wake up now"
#define SLEEP_WAKE_WINDOW_MS	(250U)

static volatile uint32_t last_activity = 0;
static uint8_t asleep = 0;

void sleep_init(void){
	last_activity = HAL_GetTick();
	asleep = 0;
}

void sleep_note_activity(void){
	last_activity = HAL_GetTick();
}

uint8_t sleep_is_asleep(void){
	return asleep;
}

/* 0 or 0xFF (erased flash) means the feature is off. */
static uint32_t timeout_ms(void){
	uint8_t minutes = pGlobalSettings[GLOBAL_SETTINGS_SLEEP_AFTER_MIN];
	if(minutes == 0 || minutes == 0xFF) return 0;
	if(minutes > SLEEP_MAX_MINUTES) minutes = SLEEP_MAX_MINUTES;
	return (uint32_t)minutes * 60000U;
}

static void go_to_sleep(void){
	asleep = 1;
	set_all_leds(0);
	ssd1306_SetDisplayOn(0);
}

static void wake_up(void){
	asleep = 0;
	ssd1306_SetDisplayOn(1);
	update_leds_on_bank_change();
	display_request_refresh();
}

void sleep_task(void){
	uint32_t now = HAL_GetTick();

	if(asleep){
		// Something happened while we were out
		if((now - last_activity) < SLEEP_WAKE_WINDOW_MS){
			wake_up();
		}
		return;
	}

	uint32_t timeout = timeout_ms();
	if(timeout == 0) return;

	if((now - last_activity) >= timeout){
		go_to_sleep();
	}
}
