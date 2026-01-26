#include "expression.h"

#include <stdbool.h>
#include "flash_midi_settings.h"
#include "midi_cmds.h"
#include "midi_defines.h"
#include "main.h"

// --- Configuration ---
// Set these to 1 to enable the pedal, 0 to disable
#define ENABLE_EXP_PEDAL_1     (1U)
#define ENABLE_EXP_PEDAL_2     (1U)

// Adaptive Filter Configuration
#define EXP_ADAPTIVE_MIN_ALPHA (5U)   // Strong smoothing when still (0-100)
#define EXP_ADAPTIVE_MAX_ALPHA (90U)  // Fast response when moving (0-100)
#define EXP_FAST_MOVE_THRESHOLD (50U) // Threshold to switch to fast mode

// Hysteresis
#define EXP_HYSTERESIS         (16U)  // Reduced hysteresis because adaptive filter handles noise better

// --- End Configuration ---

#define EXP_PEDAL_COUNT        (2U)
#define EXP_PROCESS_INTERVAL_MS (1U)  // 1ms interval (1kHz) for high resolution
#define EXP_DEADZONE_COUNTS    (15U)

extern ADC_HandleTypeDef hadc1;
#define EXP_ADC_HANDLE (&hadc1)

static const uint32_t kExpChannels[EXP_PEDAL_COUNT] = {ADC_CHANNEL_7, ADC_CHANNEL_8};
extern uint8_t f_sys_config_complete;
static uint8_t gExpCcNumbers[EXP_PEDAL_COUNT] = {11U, 4U};

static uint8_t last_sent_midi[EXP_PEDAL_COUNT];
static uint32_t last_stable_adc[EXP_PEDAL_COUNT];
static uint32_t ema_adc_value[EXP_PEDAL_COUNT]; 
static uint32_t next_process_tick = 0U;

// Helper to switch GPIO mode efficiently
// PA7 (EXP1) -> ADC12_IN7
// PB0 (EXP2) -> ADC12_IN8
static void set_pin_analog(uint32_t channel) {
    if (channel == ADC_CHANNEL_7) {
        // PA7: CRL bits 28-31. Clear to 0000 (Analog)
        GPIOA->CRL &= ~(0xF << 28);
    } else if (channel == ADC_CHANNEL_8) {
        // PB0: CRL bits 0-3. Clear to 0000 (Analog)
        GPIOB->CRL &= ~(0xF << 0);
    }
}

static void set_pin_pulldown(uint32_t channel) {
    if (channel == ADC_CHANNEL_7) {
        // PA7: Input with Pull-up/down (1000 -> 0x8)
        // MODE=00 (Input), CNF=10 (PushPull/PullUp-Down)
        GPIOA->CRL &= ~(0xF << 28); // Clear
        GPIOA->CRL |=  (0x8 << 28); // Set CNF=10
        GPIOA->ODR &= ~GPIO_PIN_7;  // ODR=0 -> Pull Down
    } else if (channel == ADC_CHANNEL_8) {
        // PB0
        GPIOB->CRL &= ~(0xF << 0);
        GPIOB->CRL |=  (0x8 << 0);
        GPIOB->ODR &= ~GPIO_PIN_0;  // ODR=0 -> Pull Down
    }
}

static void delay_cycles(uint32_t cycles) {
    volatile uint32_t c = cycles;
    while(c--) { __asm("nop"); }
}

static uint32_t read_adc_channel_pro(uint32_t channel)
{
  // 1. Switch Pin to Analog Mode (Connect to ADC)
  set_pin_analog(channel);

  ADC_ChannelConfTypeDef sConfig = {0};
  sConfig.Channel = channel;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SamplingTime = ADC_SAMPLETIME_239CYCLES_5; 

  if (HAL_ADC_ConfigChannel(EXP_ADC_HANDLE, &sConfig) != HAL_OK) return 0;
  
  // Wait for pin voltage to settle after switching from Pull-Down
  // Pull-down might have drained the capacitor, so we need recovery time.
  // Increased delay drastically to 50000 (approx 1ms) to ensure full rise
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

  // 2. Switch Pin back to Pull-Down (Discharge / Prevent Float)
  set_pin_pulldown(channel);

  return accumulator / 16;
}

static uint8_t expression_adc_to_midi(uint32_t sample)
{
  // Expanded Deadzones [ADJUSTED: Lowered top threshold to stop chatter]
  if (sample <= 80U) return 0U;      
  if (sample >= 3900U) return 127U;  // Aggressively lowered to snap to 127

  // Scale (80..3900) -> (0..127)
  // Input Range: 3900 - 80 = 3820
  
  uint32_t input_val = sample - 80U;
  uint32_t scaled = (input_val * 127U) / 3820U;
  
  if (scaled > 127U) scaled = 127U;
  return (uint8_t)scaled;
}

void expression_init(void)
{
  // Load CC numbers from Global Settings if available (Offset 2 and 3)
  if (pGlobalSettings != NULL) {
      if (pGlobalSettings[2] != 0 && pGlobalSettings[2] <= 127) {
          gExpCcNumbers[0] = pGlobalSettings[2];
      }
      if (pGlobalSettings[3] != 0 && pGlobalSettings[3] <= 127) {
          gExpCcNumbers[1] = pGlobalSettings[3];
      }
  }

  for (uint32_t i = 0; i < EXP_PEDAL_COUNT; i++) {
    last_sent_midi[i] = 0xFFU;
    last_stable_adc[i] = 0;
    ema_adc_value[i] = 0;
    
    // Init pins to Pull-Down to prevent floating
    set_pin_pulldown(kExpChannels[i]); 
  }
  next_process_tick = 0U;
}

static uint8_t midi_channel(void)
{
  if (pGlobalSettings == NULL) return 0U;
  return pGlobalSettings[GLOBAL_SETTINGS_CHANNEL] & 0x0FU;
}

void expression_task(void)
{
  if (!f_sys_config_complete) return;

  uint32_t now = HAL_GetTick();
  if (now < next_process_tick) return;
  next_process_tick = now + EXP_PROCESS_INTERVAL_MS;
  uint8_t channel = midi_channel();

  // --- Rank 1 Processing (EXP1) ---
  #if (ENABLE_EXP_PEDAL_1 == 1)
  {
      uint32_t i = 0;
      uint32_t raw_avg = read_adc_channel_pro(kExpChannels[i]);
      
      // Init
      if (last_sent_midi[i] == 0xFFU) {
          ema_adc_value[i] = raw_avg; 
      }

      // --- Adaptive Filter Logic ---
      uint32_t diff_raw;
      if (raw_avg > ema_adc_value[i]) diff_raw = raw_avg - ema_adc_value[i];
      else diff_raw = ema_adc_value[i] - raw_avg;

      // Determine Alpha based on movement speed
      uint32_t alpha;
      if (diff_raw > EXP_FAST_MOVE_THRESHOLD) {
          // Fast movement -> High Alpha (Quick response)
          // Map diff to alpha? Or just jump to max.
          // Let's map dynamically: 
          // If diff is HUGE (e.g. 500), alpha = MAX.
          // If diff is just above threshold (50), alpha = intermediate.
          // Simple linear map:
          alpha = EXP_ADAPTIVE_MAX_ALPHA; 
      } else {
          // Slow/Still -> Low Alpha (High Stability)
          alpha = EXP_ADAPTIVE_MIN_ALPHA;
      }

      // Apply EMA
      ema_adc_value[i] = (uint32_t)((alpha * raw_avg + (100 - alpha) * ema_adc_value[i]) / 100);
      
      // Hysteresis
      uint32_t filtered = ema_adc_value[i];
      uint32_t diff = (filtered > last_stable_adc[i]) ? (filtered - last_stable_adc[i]) : (last_stable_adc[i] - filtered);
      
      // Match deadzones with map function (with slight safe margin)
      bool at_min = (filtered < 90U); 
      bool at_max = (filtered > 3890U); 

      if (diff >= EXP_HYSTERESIS || at_min || at_max) {
          last_stable_adc[i] = filtered;
      } else {
          filtered = last_stable_adc[i];
      }

      uint8_t midi_value = expression_adc_to_midi(filtered);
      
      if (last_sent_midi[i] != midi_value) {
          if (midiCmd_send_cc(channel, gExpCcNumbers[i], midi_value) != ERROR_BUFFERS_FULL) {
              last_sent_midi[i] = midi_value;
          }
      }
  }
  #endif

  // --- Rank 2 Processing (EXP2) ---
  #if (ENABLE_EXP_PEDAL_2 == 1)
  {
      uint32_t i = 1;
      uint32_t raw_avg = read_adc_channel_pro(kExpChannels[i]);
      
      // Init
      if (last_sent_midi[i] == 0xFFU) {
          ema_adc_value[i] = raw_avg; 
      }

      // --- Adaptive Filter Logic ---
      uint32_t diff_raw;
      if (raw_avg > ema_adc_value[i]) diff_raw = raw_avg - ema_adc_value[i];
      else diff_raw = ema_adc_value[i] - raw_avg;

      // Determine Alpha based on movement speed
      uint32_t alpha;
      if (diff_raw > EXP_FAST_MOVE_THRESHOLD) {
          alpha = EXP_ADAPTIVE_MAX_ALPHA; 
      } else {
          alpha = EXP_ADAPTIVE_MIN_ALPHA;
      }

      // Apply EMA
      ema_adc_value[i] = (uint32_t)((alpha * raw_avg + (100 - alpha) * ema_adc_value[i]) / 100);
      
      // Hysteresis
      uint32_t filtered = ema_adc_value[i];
      uint32_t diff = (filtered > last_stable_adc[i]) ? (filtered - last_stable_adc[i]) : (last_stable_adc[i] - filtered);
      
      // Match deadzones with map function (with slight safe margin)
      bool at_min = (filtered < 90U); 
      bool at_max = (filtered > 3890U); 

      if (diff >= EXP_HYSTERESIS || at_min || at_max) {
          last_stable_adc[i] = filtered;
      } else {
          filtered = last_stable_adc[i];
      }

      uint8_t midi_value = expression_adc_to_midi(filtered);
      
      if (last_sent_midi[i] != midi_value) {
          if (midiCmd_send_cc(channel, gExpCcNumbers[i], midi_value) != ERROR_BUFFERS_FULL) {
              last_sent_midi[i] = midi_value;
          }
      }
  }
  #endif
}
