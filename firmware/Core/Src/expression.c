/*
 * expression.c
 *
 * Expression pedal sampling and MIDI forwarding.
 *
 * Each pedal is read through ADC1 with the pin switched to pull-down between
 * readings (prevents crosstalk and charge-up between the two inputs), passed
 * through an adaptive EMA filter and a small hysteresis, then mapped to a
 * 7-bit CC through the per-pedal calibration stored in the configuration:
 *
 *   min/max ADC   calibrated end points (heel / toe)
 *   curve         0 linear, 1 log (fast at the start), 2 exp (slow at the start)
 *   invert        swap heel and toe
 *   channel       0 = global MIDI channel, 1-16 = fixed channel
 *
 * The CC numbers come from the global settings (Exp1_CC / Exp2_CC).
 *
 * A pedal can also act as a switch: crossing up through the toe threshold, or
 * back down through the heel threshold, taps a button of the current bank. Each
 * direction re-arms only once the pedal has moved back out of the threshold by
 * a margin, so resting on the edge does not retrigger.
 */

#include "expression.h"

#include <stdbool.h>
#include "flash_midi_settings.h"
#include "midi_cmds.h"
#include "midi_defines.h"
#include "main.h"
#include "switch_router.h"
#include "sleep.h"

// --- Configuration ---
#define ENABLE_EXP_PEDAL_1     (1U)
#define ENABLE_EXP_PEDAL_2     (1U)

// Adaptive filter: strong smoothing when still, fast response when moving
#define EXP_ADAPTIVE_MIN_ALPHA (5U)   // 0-100
#define EXP_ADAPTIVE_MAX_ALPHA (90U)  // 0-100
#define EXP_FAST_MOVE_THRESHOLD (50U) // ADC counts

#define EXP_HYSTERESIS         (16U)  // ADC counts
#define EXP_PROCESS_INTERVAL_MS (1U)

// Defaults used when the calibration table is blank or invalid
#define EXP_DEFAULT_MIN        (80U)
#define EXP_DEFAULT_MAX        (3900U)
// --- End Configuration ---

#define EXP_PEDAL_COUNT        (2U)
#define ADC_FULL_SCALE         (4095U)

extern ADC_HandleTypeDef hadc1;
#define EXP_ADC_HANDLE (&hadc1)
extern uint8_t f_sys_config_complete;

static const uint32_t kExpChannels[EXP_PEDAL_COUNT] = {ADC_CHANNEL_7, ADC_CHANNEL_8};
static const uint8_t kEnabled[EXP_PEDAL_COUNT] = {ENABLE_EXP_PEDAL_1, ENABLE_EXP_PEDAL_2};

#define SWITCH_MARGIN     (8U)    // 7-bit units the pedal must back off to re-arm
#define TOE_DEFAULT       (120U)
#define HEEL_DEFAULT      (7U)
#define NO_BUTTON         (0xFFU)

typedef struct {
  uint16_t min_adc;
  uint16_t max_adc;
  uint8_t curve;
  uint8_t invert;
  uint8_t channel;      // 0 = global
  uint8_t cc_number;
  uint8_t toe_button;   // NO_BUTTON when unused
  uint8_t heel_button;
  uint8_t toe_level;
  uint8_t heel_level;
} exp_cal_t;

typedef struct {
  exp_cal_t cal;
  uint8_t last_sent_midi;
  uint32_t last_stable_adc;
  uint32_t ema_adc_value;
  bool initialised;
  bool toe_armed;       // false while sitting past the threshold
  bool heel_armed;
} exp_pedal_t;

static exp_pedal_t pedals[EXP_PEDAL_COUNT];
static uint32_t next_process_tick = 0U;

// --- Pin handling -----------------------------------------------------------
// PA7 (EXP1) -> ADC12_IN7, PB0 (EXP2) -> ADC12_IN8
static void set_pin_analog(uint32_t channel) {
    if (channel == ADC_CHANNEL_7) {
        GPIOA->CRL &= ~(0xF << 28);         // PA7: MODE=00 CNF=00 (analog)
    } else if (channel == ADC_CHANNEL_8) {
        GPIOB->CRL &= ~(0xF << 0);          // PB0
    }
}

static void set_pin_pulldown(uint32_t channel) {
    if (channel == ADC_CHANNEL_7) {
        GPIOA->CRL &= ~(0xF << 28);
        GPIOA->CRL |=  (0x8 << 28);         // Input with pull-up/down
        GPIOA->ODR &= ~GPIO_PIN_7;          // ODR=0 -> pull down
    } else if (channel == ADC_CHANNEL_8) {
        GPIOB->CRL &= ~(0xF << 0);
        GPIOB->CRL |=  (0x8 << 0);
        GPIOB->ODR &= ~GPIO_PIN_0;
    }
}

static void delay_cycles(uint32_t cycles) {
    volatile uint32_t c = cycles;
    while(c--) { __asm("nop"); }
}

static uint32_t read_adc_channel(uint32_t channel)
{
  set_pin_analog(channel);

  ADC_ChannelConfTypeDef sConfig = {0};
  sConfig.Channel = channel;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SamplingTime = ADC_SAMPLETIME_239CYCLES_5;
  if (HAL_ADC_ConfigChannel(EXP_ADC_HANDLE, &sConfig) != HAL_OK) return 0;

  // Let the pin recover from the pull-down before sampling (~1 ms)
  delay_cycles(50000);

  HAL_ADC_Start(EXP_ADC_HANDLE);
  HAL_ADC_PollForConversion(EXP_ADC_HANDLE, 2);
  __HAL_ADC_CLEAR_FLAG(EXP_ADC_HANDLE, ADC_FLAG_EOC);

  uint32_t accumulator = 0;
  for (uint32_t i = 0; i < 16; i++) {
      HAL_ADC_Start(EXP_ADC_HANDLE);
      if (HAL_ADC_PollForConversion(EXP_ADC_HANDLE, 2) == HAL_OK) {
          accumulator += HAL_ADC_GetValue(EXP_ADC_HANDLE);
      }
  }
  HAL_ADC_Stop(EXP_ADC_HANDLE);

  set_pin_pulldown(channel);
  return accumulator / 16;
}

// --- Calibration ------------------------------------------------------------
static void load_calibration(uint32_t i)
{
  exp_cal_t *c = &pedals[i].cal;
  const uint8_t *p = pExpSettings + i * EXP_SETTINGS_STRIDE;

  uint16_t min_adc = p[0] | (p[1] << 8);
  uint16_t max_adc = p[2] | (p[3] << 8);
  if (min_adc > ADC_FULL_SCALE || max_adc > ADC_FULL_SCALE || min_adc + 100 > max_adc) {
      min_adc = EXP_DEFAULT_MIN;   // blank flash or nonsense: use defaults
      max_adc = EXP_DEFAULT_MAX;
  }
  c->min_adc = min_adc;
  c->max_adc = max_adc;
  c->curve = (p[4] <= EXP_CURVE_EXP) ? p[4] : EXP_CURVE_LINEAR;
  c->invert = (p[5] == 1);
  c->channel = (p[6] >= 1 && p[6] <= 16) ? p[6] : 0;

  uint8_t cc = pGlobalSettings[GLOBAL_SETTINGS_EXP1_CC + i];
  c->cc_number = (cc != 0 && cc <= 127) ? cc : (i == 0 ? 11U : 4U);

  // Switch behaviour: a button index per direction, plus the levels
  c->toe_button  = (p[7] < MIDI_NUM_SWITCHES) ? p[7] : NO_BUTTON;
  c->heel_button = (p[8] < MIDI_NUM_SWITCHES) ? p[8] : NO_BUTTON;
  c->toe_level  = (p[9]  <= 127) ? p[9]  : TOE_DEFAULT;
  c->heel_level = (p[10] <= 127) ? p[10] : HEEL_DEFAULT;
  if(c->toe_level == 0) c->toe_level = TOE_DEFAULT;
}

static uint8_t adc_to_midi(const exp_cal_t *c, uint32_t sample)
{
  if (sample <= c->min_adc) return c->invert ? 127U : 0U;
  if (sample >= c->max_adc) return c->invert ? 0U : 127U;

  // Position in the calibrated range, 0..1024
  uint32_t span = c->max_adc - c->min_adc;
  uint32_t n = ((sample - c->min_adc) * 1024U) / span;
  if (c->invert) n = 1024U - n;

  uint32_t v;
  switch (c->curve) {
  case EXP_CURVE_EXP:       // slow start: n^2
      v = (n * n * 127U) / (1024U * 1024U);
      break;
  case EXP_CURVE_LOG: {     // fast start: 1 - (1-n)^2
      uint32_t m = 1024U - n;
      v = 127U - (m * m * 127U) / (1024U * 1024U);
      break;
  }
  default:                  // linear
      v = (n * 127U) / 1024U;
      break;
  }
  return (uint8_t)(v > 127U ? 127U : v);
}

static uint8_t midi_channel(const exp_cal_t *c)
{
  if (c->channel) return c->channel - 1;
  return pGlobalSettings[GLOBAL_SETTINGS_CHANNEL] & 0x0FU;
}

// --- Public API --------------------------------------------------------------
void expression_init(void)
{
  for (uint32_t i = 0; i < EXP_PEDAL_COUNT; i++) {
    load_calibration(i);
    pedals[i].last_sent_midi = 0xFFU;
    pedals[i].last_stable_adc = 0;
    pedals[i].ema_adc_value = 0;
    pedals[i].initialised = false;
    pedals[i].toe_armed = true;
    pedals[i].heel_armed = false;        // starts at the heel: needs to leave first
    set_pin_pulldown(kExpChannels[i]);   // never leave the pin floating
  }
  next_process_tick = 0U;
}

uint16_t expression_get_raw(uint8_t pedal)
{
  if (pedal >= EXP_PEDAL_COUNT) return 0;
  return (uint16_t)pedals[pedal].ema_adc_value;
}

uint8_t expression_get_midi(uint8_t pedal)
{
  if (pedal >= EXP_PEDAL_COUNT) return 0;
  uint8_t v = pedals[pedal].last_sent_midi;
  return (v == 0xFFU) ? 0 : v;
}

static void process_pedal(uint32_t i)
{
  exp_pedal_t *p = &pedals[i];
  uint32_t raw_avg = read_adc_channel(kExpChannels[i]);

  if (!p->initialised) {
      p->ema_adc_value = raw_avg;
      p->initialised = true;
  }

  // Adaptive EMA: big jumps track fast, small ones are smoothed hard
  uint32_t diff_raw = (raw_avg > p->ema_adc_value) ? raw_avg - p->ema_adc_value
                                                   : p->ema_adc_value - raw_avg;
  uint32_t alpha = (diff_raw > EXP_FAST_MOVE_THRESHOLD) ? EXP_ADAPTIVE_MAX_ALPHA
                                                        : EXP_ADAPTIVE_MIN_ALPHA;
  p->ema_adc_value = (alpha * raw_avg + (100U - alpha) * p->ema_adc_value) / 100U;

  // Hysteresis, released at the calibrated end points so they are always reached
  uint32_t filtered = p->ema_adc_value;
  uint32_t diff = (filtered > p->last_stable_adc) ? filtered - p->last_stable_adc
                                                  : p->last_stable_adc - filtered;
  bool at_end = (filtered <= p->cal.min_adc) || (filtered >= p->cal.max_adc);
  if (diff >= EXP_HYSTERESIS || at_end) {
      p->last_stable_adc = filtered;
  } else {
      filtered = p->last_stable_adc;
  }

  uint8_t midi_value = adc_to_midi(&p->cal, filtered);
  if (p->last_sent_midi != midi_value) {
      sleep_note_activity();
      if (midiCmd_send_cc(midi_channel(&p->cal), p->cal.cc_number, midi_value) != ERROR_BUFFERS_FULL) {
          p->last_sent_midi = midi_value;
      }
  }

  // Toe: fires on the way up, re-arms once the pedal backs off by the margin
  if (p->cal.toe_button != NO_BUTTON) {
      if (p->toe_armed && midi_value >= p->cal.toe_level) {
          p->toe_armed = false;
          sw_trigger_button(p->cal.toe_button);
      } else if (!p->toe_armed && midi_value + SWITCH_MARGIN < p->cal.toe_level) {
          p->toe_armed = true;
      }
  }

  // Heel: fires on the way down
  if (p->cal.heel_button != NO_BUTTON) {
      if (p->heel_armed && midi_value <= p->cal.heel_level) {
          p->heel_armed = false;
          sw_trigger_button(p->cal.heel_button);
      } else if (!p->heel_armed && midi_value > p->cal.heel_level + SWITCH_MARGIN) {
          p->heel_armed = true;
      }
  }
}

void expression_task(void)
{
  if (!f_sys_config_complete) return;

  uint32_t now = HAL_GetTick();
  if (now < next_process_tick) return;
  next_process_tick = now + EXP_PROCESS_INTERVAL_MS;

  for (uint32_t i = 0; i < EXP_PEDAL_COUNT; i++) {
    if (kEnabled[i]) {
      process_pedal(i);
    }
  }
}
