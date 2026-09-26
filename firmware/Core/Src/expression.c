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
 *   out min/max   the values sent at the heel and at the toe
 *
 * The CC numbers come from the global settings (Exp1_CC / Exp2_CC). A bank can
 * give a pedal another CC, channel and output range, or silence it (see
 * pedal_target), and an Exp command on a button can change it again until the
 * next bank change (see expression_set_target).
 *
 * Instead of its own 7-bit CC a pedal can send Pitch Bend, or a 14-bit CC pair
 * (MSB on its CC, LSB on CC + 32), for finer steps than 0-127 (see
 * send_kind). A pedal sent to another CC by its bank or an Exp command sends
 * that CC: 14-bit when the pedal is set to 14-bit CC and the CC has an LSB
 * partner, 7-bit otherwise.
 *
 * A pedal can also act as a switch: crossing up through the toe threshold, or
 * back down through the heel threshold, taps a button of the current bank. Each
 * direction re-arms only once the pedal has moved back out of the threshold by
 * a margin, so resting on the edge does not retrigger.
 *
 * And a pedal can switch a wah on and off by itself (auto-engage): leaving the
 * heel switches its button on, resting at the heel for a moment switches it
 * off. See auto_engage.
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
// Finer steps need a smaller dead band; the averaging and the EMA keep a pedal
// at rest quiet with it
#define EXP_HYSTERESIS_FINE    (4U)
// How long a pin is left analog before it is sampled: what the busy wait
// before 0.64 came to, so the pedals read as they always have
#define EXP_SETTLE_MS          (12U)

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
/*
 * How far the pedal must move, in 7-bit units, before it counts as somebody
 * playing rather than ADC noise. A connected pedal sitting still was measured
 * drifting one unit either side of its resting value, several times a minute,
 * which was enough to hold off idle sleep for ever. The CC itself is still
 * sent on every change; only the activity marker is filtered.
 */
#define EXP_ACTIVITY_MOVE (4U)
#define TOE_DEFAULT       (120U)
#define HEEL_DEFAULT      (7U)
#define NO_BUTTON         (0xFFU)
#define AUTO_OFF_DEFAULT_MS (500U)
#define AUTO_OFF_UNIT_MS    (10U)   // byte 14 counts in these

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
  uint8_t out_min;      // value sent at the heel
  uint8_t out_max;      // value sent at the toe
  uint8_t auto_button;  // auto-engage button, NO_BUTTON when unused
  uint16_t auto_off_ms; // rest at the heel before switching it off
  uint8_t out_mode;     // EXP_OUT_CC, EXP_OUT_PITCHBEND or EXP_OUT_CC14
} exp_cal_t;

// What a pedal sends at the moment
typedef enum { SEND_CC7, SEND_CC14, SEND_PB } send_kind_t;

typedef struct {
  exp_cal_t cal;
  uint8_t last_sent_midi;    // 7-bit view of the last value sent, 0xFF before the first
  uint16_t last_sent_value;  // the last value sent, in the resolution of target_kind
  uint8_t activity_ref;      // value the last real movement settled on
  bool activity_ref_set;
  uint32_t last_stable_adc;
  uint32_t ema_adc_value;
  bool initialised;
  bool toe_armed;       // false while sitting past the threshold
  bool heel_armed;
  bool switches_primed; // toe/heel armed from a real reading yet
  uint8_t target_cc;      // CC in use (BANK_EXP_CC_OFF when silent), 0xFF before the first reading
  uint8_t target_channel;
  uint8_t target_min;
  uint8_t target_max;
  uint8_t target_kind;   // send_kind_t
  bool auto_primed;      // auto-engage has seen a first reading
  bool auto_at_heel;     // at or below the heel level
  bool auto_off_done;    // this rest at the heel has been dealt with
  uint32_t auto_heel_tick; // when the pedal came to rest at the heel
} exp_pedal_t;

static exp_pedal_t pedals[EXP_PEDAL_COUNT];

// Safe mode: the first reading after boot is taken as already sent
static bool quiet_start[EXP_PEDAL_COUNT];

// Set by Exp commands: a CC (or EXP_TARGET_OFF) and channel that win over the
// bank's. Kept by expression_init, which runs at boot after the saved button
// states have set them.
typedef struct {
  bool active;
  uint8_t cc;
  uint8_t channel;      // 1-16, 0 = keep the pedal's own
} exp_override_t;

static exp_override_t overrides[EXP_PEDAL_COUNT];
// The pedal whose pin is settling, and since when; EXP_PEDAL_COUNT for none
static uint32_t settling = EXP_PEDAL_COUNT;
static uint32_t settle_tick = 0U;

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

/*
 * A reading is taken in two steps, so nothing waits for it. The pin, held
 * down between readings so an empty jack reads as zero, goes analog first,
 * and the samples are taken EXP_SETTLE_MS later, when it has recovered. The
 * main loop runs meanwhile: the wait used to be a busy loop, 11.7 ms per
 * pedal on every pass, and every press waited behind it.
 */
static void begin_adc_channel(uint32_t channel)
{
  set_pin_analog(channel);
}

static uint32_t read_adc_channel(uint32_t channel)
{
  ADC_ChannelConfTypeDef sConfig = {0};
  sConfig.Channel = channel;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SamplingTime = ADC_SAMPLETIME_239CYCLES_5;
  if (HAL_ADC_ConfigChannel(EXP_ADC_HANDLE, &sConfig) != HAL_OK) {
      set_pin_pulldown(channel);
      return 0;
  }

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

  // Output range; zeros after byte 10 were written by older tools
  c->out_min = (p[11] <= 127) ? p[11] : 0U;
  c->out_max = (p[12] <= 127) ? p[12] : 127U;
  if(p[11] == 0 && p[12] == 0) c->out_max = 127U;

  // Auto-engage: button + 1, so the zeros older tools wrote here mean none
  c->auto_button = (p[13] >= 1 && p[13] <= MIDI_NUM_SWITCHES) ? p[13] - 1U : NO_BUTTON;
  c->auto_off_ms = (p[14] != 0 && p[14] != 0xFF) ? p[14] * AUTO_OFF_UNIT_MS : AUTO_OFF_DEFAULT_MS;

  c->out_mode = (p[15] == EXP_OUT_PITCHBEND || p[15] == EXP_OUT_CC14) ? p[15] : EXP_OUT_CC;
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

/*
 * The same with 14 bits, 0..16383, for Pitch Bend and 14-bit CCs.
 */
static uint16_t adc_to_fine(const exp_cal_t *c, uint32_t sample)
{
  if (sample <= c->min_adc) return c->invert ? 16383U : 0U;
  if (sample >= c->max_adc) return c->invert ? 0U : 16383U;

  uint32_t span = c->max_adc - c->min_adc;
  uint32_t n = ((sample - c->min_adc) * 16384U) / span;   // 0..16384
  if (c->invert) n = 16384U - n;

  uint32_t v;
  switch (c->curve) {
  case EXP_CURVE_EXP:
      v = (n * n) >> 14;
      break;
  case EXP_CURVE_LOG: {
      uint32_t m = 16384U - n;
      v = 16384U - ((m * m) >> 14);
      break;
  }
  default:
      v = n;
      break;
  }
  return (uint16_t)(v > 16383U ? 16383U : v);
}

// A 7-bit range end in 14 bits: 64 is the middle (8192) and 127 the top
static int32_t fine_end(uint8_t v)
{
  return (v >= 127U) ? 16383 : (int32_t)v << 7;
}

static uint16_t scale_fine(uint16_t v, uint8_t lo, uint8_t hi)
{
  if (lo == 0U && hi == 127U) return v;
  int32_t flo = fine_end(lo);
  int32_t span = fine_end(hi) - flo;
  int32_t num = (int32_t)v * span;
  num += (num >= 0) ? 8191 : -8191;
  return (uint16_t)(flo + num / 16383);
}

/*
 * Map a 7-bit pedal position into [lo, hi]. hi may be below lo, which turns
 * the pedal round. The ends map exactly, the rest is rounded.
 */
static uint8_t scale_output(uint8_t v, uint8_t lo, uint8_t hi)
{
  if (lo == 0U && hi == 127U) return v;
  int32_t span = (int32_t)hi - (int32_t)lo;
  int32_t num = (int32_t)v * span;
  num += (num >= 0) ? 63 : -63;
  return (uint8_t)((int32_t)lo + num / 127);
}

static uint8_t midi_channel(const exp_cal_t *c)
{
  if (c->channel) return c->channel - 1;
  return pGlobalSettings[GLOBAL_SETTINGS_CHANNEL] & 0x0FU;
}

/*
 * Where a pedal sends in the current bank. A bank can give each pedal its own
 * CC, channel and output range, or turn it off; erased flash keeps the pedal's
 * own settings. Returns false when the pedal is silent in this bank. Its toe
 * and heel switches are not affected.
 */
static bool pedal_target(uint32_t i, uint8_t *cc, uint8_t *channel,
                         uint8_t *lo, uint8_t *hi, bool *own)
{
  const exp_cal_t *c = &pedals[i].cal;
  uint8_t page = sw_get_home_bank();	// a page keeps its bank's pedals
  const uint8_t *b = pBankExpSettings + page * CFG_BANK_EXP_STRIDE + i * 2U;
  const uint8_t *r = pBankExpRange + page * CFG_BANK_EXP_RANGE_STRIDE + i * 2U;
  *cc = c->cc_number;
  *channel = midi_channel(c);
  *lo = (r[0] <= 127U) ? r[0] : c->out_min;
  *hi = (r[1] <= 127U) ? r[1] : c->out_max;
  bool enabled = (b[0] != BANK_EXP_CC_OFF);
  *own = true;
  if (b[0] <= 127U && b[0] != c->cc_number) {
      *cc = b[0];
      *own = false;
  }
  if (b[1] >= 1U && b[1] <= 16U) *channel = b[1] - 1U;

  // An Exp command wins over the bank, even over a pedal the bank silenced;
  // the output range stays the bank's
  const exp_override_t *o = &overrides[i];
  if (o->active) {
      if (o->cc == EXP_TARGET_OFF) return false;
      *own = (o->cc == c->cc_number);
      *cc = o->cc;
      if (o->channel >= 1U && o->channel <= 16U) *channel = o->channel - 1U;
      return true;
  }
  return enabled;
}

/*
 * What goes out: Pitch Bend replaces the pedal's own CC only, and a 14-bit CC
 * needs a CC below 32, whose LSB partner is CC + 32.
 */
static send_kind_t send_kind(const exp_cal_t *c, uint8_t cc, bool own)
{
  if (c->out_mode == EXP_OUT_PITCHBEND && own) return SEND_PB;
  if (c->out_mode == EXP_OUT_CC14 && cc < 32U) return SEND_CC14;
  return SEND_CC7;
}

/*
 * Exp commands. The pedal switches over on its next movement, like on a bank
 * change: the new target is not sent the position it was left at, so a pedal
 * moved from the wah to the volume does not jump the volume.
 */
void expression_set_target(uint8_t pedal, uint8_t cc, uint8_t channel)
{
  if (pedal >= EXP_PEDAL_COUNT) return;
  exp_override_t *o = &overrides[pedal];
  if (cc == EXP_TARGET_RESET || cc > EXP_TARGET_OFF) {
      o->active = false;
      return;
  }
  o->active = true;
  o->cc = cc;
  o->channel = (channel <= 16U) ? channel : 0U;
}

void expression_clear_targets(void)
{
  for (uint32_t i = 0; i < EXP_PEDAL_COUNT; i++) overrides[i].active = false;
}

// --- Public API --------------------------------------------------------------
void expression_init(void)
{
  for (uint32_t i = 0; i < EXP_PEDAL_COUNT; i++) {
    load_calibration(i);
    pedals[i].last_sent_midi = 0xFFU;
    pedals[i].last_sent_value = 0xFFFFU;
    pedals[i].target_kind = SEND_CC7;
    pedals[i].activity_ref = 0;
    pedals[i].activity_ref_set = false;
    pedals[i].last_stable_adc = 0;
    pedals[i].ema_adc_value = 0;
    pedals[i].initialised = false;
    // Armed from the first real reading, see process_pedal
    pedals[i].toe_armed = false;
    pedals[i].heel_armed = false;
    pedals[i].switches_primed = false;
    pedals[i].target_cc = 0xFFU;
    pedals[i].target_channel = 0xFFU;
    pedals[i].target_min = 0xFFU;
    pedals[i].target_max = 0xFFU;
    pedals[i].auto_primed = false;
    set_pin_pulldown(kExpChannels[i]);   // never leave the pin floating
  }
  settling = EXP_PEDAL_COUNT;
}

void expression_quiet_start(void)
{
  for (uint32_t i = 0; i < EXP_PEDAL_COUNT; i++) quiet_start[i] = true;
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
  return (v == 0xFFU) ? 0 : (v & 0x7FU);
}

/*
 * Auto-engage, like the auto-engage wahs of Fractal and Line 6: moving the
 * pedal up from the heel switches its button on, and resting at or below the
 * heel level for auto_off_ms switches it off. The button must be a toggle in
 * the current bank; it is pressed as if by foot, so its own on and off
 * commands, LED and display cell follow, and it can still be pressed by hand.
 *
 * Both work on edges, not levels: the button is only switched on as the pedal
 * leaves the heel and only switched off once per rest at the heel, so a wah
 * switched off by hand with the pedal up, or on by hand at the heel, stays as
 * it was left. Nothing fires on the first reading.
 *
 * While an Exp command has the pedal somewhere else it leaves the button
 * alone: the pedal is not driving the wah then. It only follows the edges, so
 * getting the pedal back does not fire anything either.
 */
static void auto_engage(exp_pedal_t *p, bool redirected, uint8_t midi_value)
{
  const exp_cal_t *c = &p->cal;
  if (c->auto_button == NO_BUTTON) return;

  bool at_heel = (midi_value <= c->heel_level);
  uint32_t now = HAL_GetTick();
  if (!p->auto_primed) {
      p->auto_primed = true;
      p->auto_at_heel = at_heel;
      p->auto_off_done = false;
      p->auto_heel_tick = now;
      return;
  }

  if (redirected) {
      p->auto_at_heel = at_heel;
      p->auto_off_done = true;
      return;
  }

  uint8_t page = sw_get_current_page();
  bool usable = sw_button_is_toggle(page, c->auto_button);
  bool on = usable && sw_get_toggle_state(page, c->auto_button);

  if (!at_heel) {
      if (p->auto_at_heel && usable && !on) {
          sw_trigger_button(c->auto_button);
      }
      p->auto_at_heel = false;
      return;
  }

  if (!p->auto_at_heel) {
      p->auto_at_heel = true;
      p->auto_off_done = false;
      p->auto_heel_tick = now;
  }
  if (!p->auto_off_done && now - p->auto_heel_tick >= c->auto_off_ms) {
      p->auto_off_done = true;
      if (on) sw_trigger_button(c->auto_button);
  }
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
  uint32_t hysteresis = (p->cal.out_mode == EXP_OUT_CC) ? EXP_HYSTERESIS : EXP_HYSTERESIS_FINE;
  if (diff >= hysteresis || at_end) {
      p->last_stable_adc = filtered;
  } else {
      filtered = p->last_stable_adc;
  }

  // Pedal position, 0 at the heel and 127 at the toe. The switches and the
  // activity marker follow it; the value sent is scaled into the output range.
  uint8_t midi_value = adc_to_midi(&p->cal, filtered);
  uint16_t fine_value = adc_to_fine(&p->cal, filtered);

  // Only a real move counts as activity; noise must not hold off sleep
  if (!p->activity_ref_set) {
      p->activity_ref = midi_value;
      p->activity_ref_set = true;
  } else {
      uint8_t moved = (midi_value > p->activity_ref)
                    ? (uint8_t)(midi_value - p->activity_ref)
                    : (uint8_t)(p->activity_ref - midi_value);
      if (moved >= EXP_ACTIVITY_MOVE) {
          p->activity_ref = midi_value;
          sleep_note_activity();
      }
  }

  // The wah goes on before the first position reaches it
  auto_engage(p, overrides[i].active, midi_value);

  // A bank change can move the pedal to another CC, channel or range, or
  // silence it. The new target is not sent the old position: it follows the
  // next movement.
  uint8_t cc, channel, lo, hi;
  bool own;
  bool enabled = pedal_target(i, &cc, &channel, &lo, &hi, &own);
  send_kind_t kind = send_kind(&p->cal, cc, own);
  uint16_t out_value = (kind == SEND_CC7) ? scale_output(midi_value, lo, hi)
                                          : scale_fine(fine_value, lo, hi);
  uint8_t out_midi = (kind == SEND_CC7) ? (uint8_t)out_value : (uint8_t)(out_value >> 7);
  uint8_t target = enabled ? cc : BANK_EXP_CC_OFF;
  if (target != p->target_cc || channel != p->target_channel
      || lo != p->target_min || hi != p->target_max || kind != p->target_kind) {
      if (p->target_cc != 0xFFU || quiet_start[i]) {
          p->last_sent_value = out_value;
          p->last_sent_midi = out_midi;
      }
      p->target_cc = target;
      p->target_channel = channel;
      p->target_min = lo;
      p->target_max = hi;
      p->target_kind = kind;
  }

  quiet_start[i] = false;

  if (p->last_sent_value != out_value) {
      int8_t sent = 0;
      if (enabled) {                        // else silent in this bank
          if (kind == SEND_PB) sent = midiCmd_send_pb(channel, out_value);
          else if (kind == SEND_CC14) sent = midiCmd_send_cc14(channel, cc, out_value);
          else sent = midiCmd_send_cc(channel, cc, (uint8_t)out_value);
      }
      if (sent != ERROR_BUFFERS_FULL) {
          p->last_sent_value = out_value;
          p->last_sent_midi = out_midi;
      }
  }

  /*
   * Arm the toe and heel switches from where the pedal actually is, and never
   * fire on that first reading. They used to start armed as if the pedal sat
   * at the heel, so a pedal resting past the toe threshold, typically an
   * inverted pedal left at rest or unplugged, pressed its toe button the
   * moment the pedals were initialised: at boot on batteries, and whenever a
   * configuration was switched. A switch now only fires on a real crossing.
   */
  if (!p->switches_primed) {
      p->toe_armed  = (midi_value + SWITCH_MARGIN < p->cal.toe_level);
      p->heel_armed = (midi_value > p->cal.heel_level + SWITCH_MARGIN);
      p->switches_primed = true;
      return;
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
  if (settling < EXP_PEDAL_COUNT) {
    if (now - settle_tick < EXP_SETTLE_MS) return;
    process_pedal(settling);
  }

  // The next enabled pedal starts settling, in turn
  uint32_t next = (settling < EXP_PEDAL_COUNT) ? settling + 1U : 0U;
  settling = EXP_PEDAL_COUNT;
  for (uint32_t n = 0; n < EXP_PEDAL_COUNT; n++, next++) {
    uint32_t i = next % EXP_PEDAL_COUNT;
    if (kEnabled[i]) {
      begin_adc_channel(kExpChannels[i]);
      settling = i;
      settle_tick = now;
      return;
    }
  }
}
