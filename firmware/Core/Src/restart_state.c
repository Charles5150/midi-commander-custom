/*
 * restart_state.c
 *
 * The watchdog restarts the pedal after a lock-up (see main.c), and without
 * this it would come back as though just switched on: on bank 0, toggles off,
 * the rig still on the song's sound. So the main loop keeps a copy of the live
 * state in a RAM area the startup does not clear, and a start the watchdog
 * made takes it back from there. RAM costs no flash writes and holds what the
 * pedal was doing that very moment, whatever Remember_State says.
 *
 * The area sits after our .bss, well above the RAM the bootloader uses (its
 * stack starts at 0x20000C28), so passing through it leaves the copy alone.
 * Switching off loses it, and only the watchdog's reset flag lets it be used:
 * any other start is a fresh one.
 *
 * The copy carries a word that changes with its layout and a checksum written
 * last, so one from other firmware or cut short by the lock-up is ignored.
 */

#include "restart_state.h"
#include "main.h"
#include "flash_midi_settings.h"
#include "midi_defines.h"
#include "switch_router.h"
#include "tempo.h"
#include <string.h>

#define RESTART_MAGIC	(0x5EC0DE01U)	// the last byte is the layout

typedef struct {
	uint32_t magic;
	live_state_t state;
	uint32_t check;
} copy_t;

static copy_t copy __attribute__((section(".noinit")));

static uint32_t checksum(const live_state_t *s){
	const uint32_t *w = (const uint32_t *)s;
	uint32_t sum = RESTART_MAGIC;
	for(uint32_t i = 0; i < sizeof(*s) / 4; i++){
		sum = (sum << 5 | sum >> 27) ^ w[i];
	}
	return sum;
}

bool restart_state_load(live_state_t *out){
	bool watchdog = __HAL_RCC_GET_FLAG(RCC_FLAG_IWDGRST);
	__HAL_RCC_CLEAR_RESET_FLAGS();	// so the next start reads its own reason

	bool sound = watchdog && copy.magic == RESTART_MAGIC
			&& copy.check == checksum(&copy.state)
			&& copy.state.bank < MIDI_NUM_BANKS && copy.state.slot < CONFIG_SLOTS;
	copy.magic = 0;		// used once: a later lock-up needs a fresh copy
	if(sound) *out = copy.state;
	return sound;
}

void restart_state_task(void){
	live_state_t s;
	sw_get_toggle_states(s.toggles);
	sw_get_long_toggle_states(s.long_toggles);
	s.bpm = tempo_get_bpm();
	s.bank = sw_get_home_bank();	// a page shown is left, as at power on
	s.slot = flash_settings_active_slot();

	if(copy.magic == RESTART_MAGIC && memcmp(&s, &copy.state, sizeof(s)) == 0) return;
	copy.magic = 0;		// a lock-up halfway through leaves no valid copy
	copy.state = s;
	copy.check = checksum(&s);
	copy.magic = RESTART_MAGIC;
}
