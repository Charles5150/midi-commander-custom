/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; Copyright (c) 2021 STMicroelectronics.
  * All rights reserved.</center></h2>
  *
  * This software component is licensed by ST under BSD 3-Clause license,
  * the "License"; You may not use this file except in compliance with the
  * License. You may obtain a copy of the License at:
  *                        opensource.org/licenses/BSD-3-Clause
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "usb_device.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "latency.h"
#include "ssd1306.h"
#include <stdbool.h>
#include <string.h>
#include "usbd_midi_if.h"
#include "usbd_composite_midi_hid.h"
#include "midi_defines.h"
#include "midi_cmds.h"
#include "switch_router.h"
#include "display.h"
#include "expression.h"
#include "flash_midi_settings.h"
#include "state_store.h"
#include "restart_state.h"
#include "health.h"
#include "leds.h"
#include "tempo.h"
#include "sleep.h"
#include "kemper.h"
#include "gt1000.h"
#include "dfu_entry.h"

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
I2C_HandleTypeDef hi2c1;
DMA_HandleTypeDef hdma_i2c1_tx;

UART_HandleTypeDef huart2;
DMA_HandleTypeDef hdma_usart2_tx;

/* USER CODE BEGIN PV */
uint8_t f_sys_config_complete = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_I2C1_Init(void);
static void MX_ADC1_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
extern const uint32_t g_pfnVectors[];

/*
 * The HAL's I2C waits give up after so many ms of HAL_GetTick, which stands
 * still in SysTick, where the display's lines are started: a bus that hung
 * there waited for ever, and the watchdog restarted the pedal. While the
 * display starts a transfer from SysTick its clock moves a ms each 256 reads,
 * so the wait ends, in well under its real time, and the pedal carries on
 * without a screen.
 */
uint32_t HAL_GetTick(void)
{
  if(ssd1306_hal_in_tick && (SCB->ICSR & SCB_ICSR_VECTACTIVE_Msk) == 15U){
    static uint32_t reads;
    return uwTick + (++reads >> 8);
  }
  return uwTick;
}

// The table is wherever the linker put it: 0x08003000 behind the DFU
// bootloader, 0x08000000 in the ST-Link build.
static inline void RelocateVectorTable(void)
{
  SCB->VTOR = (uint32_t)g_pfnVectors;
  __DSB();
  __ISB();
}

/*
 * The independent watchdog: any lock-up restarts the pedal instead of leaving
 * it dead until switched off. It runs from its own clock (LSI, 30 to 60 kHz),
 * so with /32 and the longest reload it bites after 2.2 to 4.4 s without the
 * main loop, room enough for the 17 pages an upload erases in one go. Stopped
 * while a debugger holds the core, and gone after any reset, the one into the
 * bootloader for a firmware update included.
 */
static void watchdog_start(void)
{
  DBGMCU->CR |= DBGMCU_CR_DBG_IWDG_STOP;
  // Started first: that turns the LSI on, and PR and RLR only take a new
  // value with it running. Waiting for them before starting hung here.
  IWDG->KR = 0xCCCC;		// start
  IWDG->KR = 0x5555;		// unlock PR and RLR
  IWDG->PR = 3;				// LSI / 32
  IWDG->RLR = 0xFFF;
  uint32_t start = HAL_GetTick();
  while (IWDG->SR && HAL_GetTick() - start < 50) {}
  IWDG->KR = 0xAAAA;		// reload
}

// The waits of the boot, with the power on banner moving meanwhile
static void boot_wait(uint32_t ms)
{
  uint32_t start = HAL_GetTick();
  while (HAL_GetTick() - start < ms)
  {
    display_banner_task();
  }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  RelocateVectorTable();

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */
  health_paint_stack();	// before the stack grows: see health.c

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART2_UART_Init();
  MX_I2C1_Init();
  MX_ADC1_Init();
  MX_USB_DEVICE_Init();
  /* USER CODE BEGIN 2 */

  // Reset the USB interface in case it's still plugged in.
  HAL_GPIO_WritePin(USB_ID_GPIO_Port, USB_ID_Pin, GPIO_PIN_RESET);

  latency_init();	// the cycle counter that times presses

  display_init();

  // Check we've got a 256kB device, in case Melo switch to a smaller device at some point
  uint16_t flash_size = (*(uint16_t*)FLASHSIZE_BASE);
  uint16_t min_size = 256;
  if(flash_size < min_size) {
	  char msg[25];
	  snprintf(msg, sizeof(msg), "Mem %3dkb < %3dkb", flash_size, min_size);
	  Error(msg);
  }

  // A page the on-pedal editor was rewriting when the power went: finish it
  flash_settings_recover();

  // Come back on the configuration slot the pedal was left on, if it still
  // holds one. Every configuration pointer follows from here. After the
  // watchdog restarted it, the state it had that moment wins over the saved
  // one: see restart_state.c
  uint8_t saved_bank = 0, saved_slot = 0;
  uint32_t saved_toggles[8] = {0}, saved_long[8] = {0}, saved_double[8] = {0};
  bool have_state = state_store_load(&saved_bank, saved_toggles, saved_long, saved_double, &saved_slot);
  live_state_t live;
  bool restarted = restart_state_load(&live);
  if(restarted){
	  saved_bank = live.bank;
	  saved_slot = live.slot;
	  memcpy(saved_toggles, live.toggles, sizeof(saved_toggles));
	  memcpy(saved_long, live.long_toggles, sizeof(saved_long));
	  memcpy(saved_double, live.double_toggles, sizeof(saved_double));
  }
  if((have_state || restarted) && saved_slot != 0 && flash_settings_slot_valid(saved_slot)){
	  flash_settings_select(saved_slot);
  }

  display_setConfigName();

  leds_init();
  sw_init();
  sw_led_init();

  // One MIDI port or three, as this configuration says, until the next start
  usb_ports_latch();
  usb_composite_ports(usb_ports);

  boot_wait(1000);
  HAL_GPIO_WritePin(USB_ID_GPIO_Port, USB_ID_Pin, GPIO_PIN_SET);

  boot_wait(200);
  // A footswitch held now is safe mode, see switch_router.c
  bool safe_mode = sw_check_safe_mode();
  f_sys_config_complete = 1; // Don't scan switch changes until everything is init'd

  // Restore the last bank and toggle states if this configuration asks for
  // it, and only if they were saved while this same configuration was active
  if(!safe_mode && (restarted || (pGlobalSettings[GLOBAL_SETTINGS_REMEMBER_STATE] == 1
		  && have_state)) && saved_slot == flash_settings_active_slot()){
    sw_restore_state(saved_bank, saved_toggles, saved_long, saved_double);
  }
  display_setBankName(sw_get_current_page());

  expression_init();
  if(safe_mode){
	  expression_quiet_start();
	  display_show_safe_mode();
  } else if(restarted){
	  display_show_restarted();	// so a lock-up does not go unnoticed
  }
  tempo_init();
  if(restarted && !safe_mode) tempo_set_bpm(live.bpm);
  sleep_init();
  watchdog_start();

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
      sysex_flash_task();
      if(sysex_upload_paused()){
    	  // The running configuration is being rewritten: nothing may read it
    	  // until the tool restarts the pedal
    	  IWDG->KR = 0xAAAA;
    	  __WFI();
    	  continue;
      }
	  handle_switches();
      expression_task();
      state_store_task();
      restart_state_task();
      tempo_task();
      display_task();
      sleep_task();
      kemper_task();
      gt1000_task();
      dfu_entry_task();
      IWDG->KR = 0xAAAA;	// feed the watchdog

      /*
       * Nothing here spins waiting for anything, so sleep until the next
       * interrupt. SysTick alone wakes us every millisecond, which is far
       * more often than any task needs, and the CPU spends the rest of the
       * time stopped instead of looping for nothing.
       */
      __WFI();

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

// Wait up to 100 ms, as the HAL did, for a clock bit to read as wanted
static void clock_wait(volatile uint32_t *reg, uint32_t mask, uint32_t want)
{
  uint32_t start = HAL_GetTick();
  while ((*reg & mask) != want)
  {
    if (HAL_GetTick() - start > 100U)
    {
      Error_Handler();
    }
  }
}

/**
  * @brief System Clock Configuration
  * 72 MHz from the 12 MHz crystal times 6; AHB and APB2 at 72, APB1 at 36;
  * the ADC at 72/6 = 12 MHz, under the F103's 14 MHz; USB at 72/1.5 = 48.
  * Register by register rather than through the HAL, which took a kilobyte.
  * The bootloader may have left the PLL running the core, so the core goes
  * to the HSI first: the PLL can only be set while it is off.
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC->CR |= RCC_CR_HSION;
  clock_wait(&RCC->CR, RCC_CR_HSIRDY, RCC_CR_HSIRDY);
  RCC->CFGR &= ~RCC_CFGR_SW;
  clock_wait(&RCC->CFGR, RCC_CFGR_SWS, RCC_CFGR_SWS_HSI);
  RCC->CR &= ~RCC_CR_PLLON;
  clock_wait(&RCC->CR, RCC_CR_PLLRDY, 0);

  RCC->CR |= RCC_CR_HSEON;
  clock_wait(&RCC->CR, RCC_CR_HSERDY, RCC_CR_HSERDY);

  // USBPRE 0 is /1.5, PLLXTPRE 0 the crystal undivided
  RCC->CFGR = RCC_CFGR_PLLSRC | RCC_CFGR_PLLMULL6 | RCC_CFGR_ADCPRE_DIV6
            | RCC_CFGR_PPRE1_DIV2;
  RCC->CR |= RCC_CR_PLLON;
  clock_wait(&RCC->CR, RCC_CR_PLLRDY, RCC_CR_PLLRDY);

  FLASH->ACR = (FLASH->ACR & ~FLASH_ACR_LATENCY) | FLASH_LATENCY_2;
  RCC->CFGR |= RCC_CFGR_SW_PLL;
  clock_wait(&RCC->CFGR, RCC_CFGR_SWS, RCC_CFGR_SWS_PLL);

  SystemCoreClock = 72000000U;
  HAL_InitTick(TICK_INT_PRIORITY);
}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.ClockSpeed = 400000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 31250;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * Enable DMA controller clock
  */
static void MX_DMA_Init(void)
{

  /* DMA controller clock enable */
  __HAL_RCC_DMA1_CLK_ENABLE();

  /* DMA interrupt init */
  /* DMA1_Channel6_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA1_Channel6_IRQn, 1, 0);
  HAL_NVIC_EnableIRQ(DMA1_Channel6_IRQn);
  /* DMA1_Channel7_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA1_Channel7_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(DMA1_Channel7_IRQn);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
/*
 * Set the pins of a port to one configuration, PIN_OUT and the like.
 * Register by register rather than through HAL_GPIO_Init, which took half a
 * kilobyte.
 */
void gpio_config(GPIO_TypeDef *port, uint16_t pins, uint32_t config)
{
  for (uint32_t i = 0; i < 16U; i++)
  {
    if (pins & (1U << i))
    {
      volatile uint32_t *cr = (i < 8U) ? &port->CRL : &port->CRH;
      uint32_t shift = (i & 7U) * 4U;
      *cr = (*cr & ~(0xFU << shift)) | (config << shift);
    }
  }
}

static void MX_GPIO_Init(void)
{
  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOF_CLK_ENABLE();

  // The LEDs and USB_ID low, the switches pulled up
  GPIOC->BRR = LED_C_Pin|LED_B_Pin|USB_ID_Pin;
  GPIOA->BRR = LED_D_Pin|LED_2_Pin;
  GPIOB->BRR = LED_E_Pin|LED_5_Pin|LED_4_Pin|LED_3_Pin|LED_1_Pin|LED_A_Pin;
  SW_B_GPIO_Port->BSRR = SW_B_Pin;
  GPIOA->BSRR = SW_C_Pin|SW_D_Pin|SW_E_Pin|SW_2_Pin|SW_1_Pin;
  GPIOB->BSRR = SW_5_Pin|SW_4_Pin|SW_3_Pin|SW_A_Pin;

  gpio_config(GPIOC, LED_C_Pin|LED_B_Pin|USB_ID_Pin, PIN_OUT);
  gpio_config(SW_B_GPIO_Port, SW_B_Pin, PIN_IN_PULL);
  gpio_config(GPIOA, SW_C_Pin|SW_D_Pin|SW_E_Pin|SW_2_Pin|SW_1_Pin, PIN_IN_PULL);
  gpio_config(GPIOA, LED_D_Pin|LED_2_Pin, PIN_OUT);
  gpio_config(GPIOB, LED_E_Pin|LED_5_Pin|LED_4_Pin|LED_3_Pin|LED_1_Pin|LED_A_Pin, PIN_OUT);
  gpio_config(GPIOB, SW_5_Pin|SW_4_Pin|SW_3_Pin|SW_A_Pin, PIN_IN_PULL);
  gpio_config(EXP1_GPIO_Port, EXP1_Pin, PIN_ANALOG);
  gpio_config(EXP2_GPIO_Port, EXP2_Pin, PIN_ANALOG);
}

// A wait of a few microseconds, for the ADC to wake up and to calibrate
static void adc_delay(void)
{
  for (volatile uint32_t n = 0; n < 100U; n++) {
  }
}

// Wait for an ADC bit to clear, false after about 10 ms as the HAL did
static bool adc_wait_clear(uint32_t mask)
{
  uint32_t start = HAL_GetTick();
  while (ADC1->CR2 & mask) {
    if (HAL_GetTick() - start > 10U) {
      return false;
    }
  }
  return true;
}

static void adc_on(void)
{
  if (!(ADC1->CR2 & ADC_CR2_ADON)) {
    ADC1->CR2 |= ADC_CR2_ADON;	// once off, the first ADON only wakes it up
    adc_delay();
  }
}

/*
 * The ADC, one conversion at a time on the channel the expression pedals ask
 * for, started by software. Register by register rather than through the HAL,
 * which took a kilobyte and a half. Calibrated once here, and off between
 * readings, as it always was.
 */
static void MX_ADC1_Init(void)
{
  __HAL_RCC_ADC1_CLK_ENABLE();
  ADC1->CR1 = 0;
  ADC1->CR2 = ADC_CR2_EXTSEL | ADC_CR2_EXTTRIG;	// EXTSEL 111: SWSTART
  ADC1->SQR1 = 0;	// a single conversion
  adc_on();
  ADC1->CR2 |= ADC_CR2_RSTCAL;
  if (!adc_wait_clear(ADC_CR2_RSTCAL))
  {
    Error_Handler();
  }
  ADC1->CR2 |= ADC_CR2_CAL;
  if (!adc_wait_clear(ADC_CR2_CAL))
  {
    Error_Handler();
  }
  adc_stop();
}

// One conversion of channel 7 or 8, sampled for 239.5 cycles; false if it
// did not finish within 2 ms
bool adc_sample(uint32_t channel, uint32_t *value)
{
  uint32_t shift = 3U * (channel - 10U * (channel >= 10U));
  volatile uint32_t *smpr = (channel >= 10U) ? &ADC1->SMPR1 : &ADC1->SMPR2;
  *smpr |= 7U << shift;
  ADC1->SQR3 = channel;
  adc_on();
  ADC1->CR2 |= ADC_CR2_SWSTART;
  uint32_t start = HAL_GetTick();
  while (!(ADC1->SR & ADC_SR_EOC)) {
    if (HAL_GetTick() - start > 2U) {
      return false;
    }
  }
  *value = ADC1->DR;	// which clears EOC
  return true;
}

void adc_stop(void)
{
  ADC1->CR2 &= ~ADC_CR2_ADON;
}

/* USER CODE BEGIN 4 */

/*
 * @brief Show an error message on the screen, if the display is on, then call
 * Error_Handler() to stop all operations, until the watchdog restarts the
 * pedal. The screen goes out a line at a
 * time from SysTick, so it waits for that, up to a moment, before stopping:
 * Error_Handler switches interrupts off, which used to leave it unsent.
 */
void Error(char *msg) {
	if (ssd1306_GetDisplayOn()) {
		ssd1306_Fill(Black);
		ssd1306_SetCursor(2, 0);
		ssd1306_WriteString("Error:", Font_6x8, White);
		ssd1306_SetCursor(2, 9);
		ssd1306_WriteString(msg, Font_6x8, White);
		ssd1306_UpdateScreen();
		uint32_t start = HAL_GetTick();
		while (ssd1306_Busy() && HAL_GetTick() - start < 200) {
		}
	}

	Error_Handler();
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
