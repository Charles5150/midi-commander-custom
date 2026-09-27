/*
 * stm32f1xx_hal.h for the simulator
 *
 * Stands in for ST's HAL and CMSIS headers when the firmware's own sources
 * are compiled to WebAssembly (see sim/README.md). It declares only what
 * those sources use: registers become plain structs that sim.c reads and
 * writes, and the HAL calls become functions of sim.c. FLASH_BASE is a fixed
 * address in the module's memory, below its data, where sim.c keeps the
 * 256 kB of flash, so every address the firmware works out stays the same
 * arithmetic as on the chip.
 */
#ifndef SIM_STM32F1XX_HAL_H
#define SIM_STM32F1XX_HAL_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>	// newlib reaches the sources through ST's headers
#include <stdio.h>

#define SIM_FLASH_SIZE		(256U * 1024U)
#define FLASH_BASE			(0x00010000U)	// sim/build.sh puts the data above it
#define FLASHSIZE_BASE		(FLASH_BASE + SIM_FLASH_SIZE - 2U)	// not read by the sources built
#define FLASH_PAGE_SIZE		(0x800U)
#define FLASH_BANK_1		(1U)
#define FLASH_TYPEERASE_PAGES		(0U)
#define FLASH_TYPEPROGRAM_HALFWORD	(1U)

typedef enum { HAL_OK = 0, HAL_ERROR, HAL_BUSY, HAL_TIMEOUT } HAL_StatusTypeDef;

// --- Core ---------------------------------------------------------------------
extern uint32_t SystemCoreClock;
extern volatile uint32_t sim_primask;
extern volatile uint32_t sim_ipsr;

static inline uint32_t __get_PRIMASK(void){ return sim_primask; }
static inline void __set_PRIMASK(uint32_t v){ sim_primask = v; }
static inline void __disable_irq(void){ sim_primask = 1; }
static inline void __enable_irq(void){ sim_primask = 0; }
static inline uint32_t __get_IPSR(void){ return sim_ipsr; }
static inline void __NOP(void){}
static inline void __WFI(void){}
void NVIC_SystemReset(void);

typedef struct { volatile uint32_t CTRL, CYCCNT; } DWT_Type;
typedef struct { volatile uint32_t DEMCR; } CoreDebug_Type;
extern DWT_Type sim_dwt;
extern CoreDebug_Type sim_coredebug;
#define DWT					(&sim_dwt)
#define CoreDebug			(&sim_coredebug)
#define DWT_CTRL_CYCCNTENA_Msk		(1U)
#define CoreDebug_DEMCR_TRCENA_Msk	(1U << 24)
typedef struct { volatile uint32_t ICSR; } SCB_Type;
extern SCB_Type sim_scb;
#define SCB					(&sim_scb)
#define SCB_ICSR_PENDSTSET_Msk		(1U << 26)

typedef enum { TIM2_IRQn = 28, USART2_IRQn = 38 } IRQn_Type;
static inline void HAL_NVIC_SetPriority(IRQn_Type irq, uint32_t pre, uint32_t sub){ (void)irq; (void)pre; (void)sub; }
static inline void HAL_NVIC_EnableIRQ(IRQn_Type irq){ (void)irq; }

uint32_t HAL_GetTick(void);
void HAL_IncTick(void);
void HAL_Delay(uint32_t ms);

// --- Reset flags --------------------------------------------------------------
extern uint32_t sim_reset_flags;
#define RCC_FLAG_IWDGRST			(1U)
#define __HAL_RCC_GET_FLAG(f)		((sim_reset_flags & (f)) != 0)
#define __HAL_RCC_CLEAR_RESET_FLAGS()	(sim_reset_flags = 0)
#define __HAL_RCC_TIM2_CLK_ENABLE()	((void)0)

// --- GPIO ---------------------------------------------------------------------
typedef struct { volatile uint32_t CRL, CRH, IDR, ODR, BSRR, BRR, LCKR; } GPIO_TypeDef;
extern GPIO_TypeDef sim_gpio[3];
#define GPIOA				(&sim_gpio[0])
#define GPIOB				(&sim_gpio[1])
#define GPIOC				(&sim_gpio[2])

typedef enum { GPIO_PIN_RESET = 0, GPIO_PIN_SET } GPIO_PinState;
#define GPIO_PIN_0			((uint16_t)0x0001)
#define GPIO_PIN_1			((uint16_t)0x0002)
#define GPIO_PIN_2			((uint16_t)0x0004)
#define GPIO_PIN_3			((uint16_t)0x0008)
#define GPIO_PIN_4			((uint16_t)0x0010)
#define GPIO_PIN_5			((uint16_t)0x0020)
#define GPIO_PIN_6			((uint16_t)0x0040)
#define GPIO_PIN_7			((uint16_t)0x0080)
#define GPIO_PIN_8			((uint16_t)0x0100)
#define GPIO_PIN_9			((uint16_t)0x0200)
#define GPIO_PIN_10			((uint16_t)0x0400)
#define GPIO_PIN_11			((uint16_t)0x0800)
#define GPIO_PIN_12			((uint16_t)0x1000)
#define GPIO_PIN_13			((uint16_t)0x2000)
#define GPIO_PIN_14			((uint16_t)0x4000)
#define GPIO_PIN_15			((uint16_t)0x8000)

static inline GPIO_PinState HAL_GPIO_ReadPin(GPIO_TypeDef *port, uint16_t pin){
	return (port->IDR & pin) ? GPIO_PIN_SET : GPIO_PIN_RESET;
}
static inline void HAL_GPIO_WritePin(GPIO_TypeDef *port, uint16_t pin, GPIO_PinState s){
	if(s) port->ODR |= pin; else port->ODR &= ~(uint32_t)pin;
}

// --- TIM2, the LED refresh ----------------------------------------------------
typedef struct { volatile uint32_t CR1, DIER, SR, EGR, PSC, ARR, CNT; } TIM_TypeDef;
extern TIM_TypeDef sim_tim2;
#define TIM2				(&sim_tim2)
#define TIM_SR_UIF			(1U)
#define TIM_EGR_UG			(1U)
#define TIM_DIER_UIE		(1U)
#define TIM_CR1_CEN			(1U)

// --- Flash --------------------------------------------------------------------
typedef struct {
	uint32_t TypeErase;
	uint32_t Banks;
	uint32_t PageAddress;
	uint32_t NbPages;
} FLASH_EraseInitTypeDef;

HAL_StatusTypeDef HAL_FLASH_Unlock(void);
HAL_StatusTypeDef HAL_FLASH_Lock(void);
HAL_StatusTypeDef HAL_FLASH_Program(uint32_t type, uint32_t address, uint64_t data);
HAL_StatusTypeDef HAL_FLASHEx_Erase(FLASH_EraseInitTypeDef *init, uint32_t *page_error);

// --- DMA, I2C (the display), UART (DIN), ADC (the expression pedals) ----------
typedef struct { uint32_t Instance; } DMA_HandleTypeDef;

typedef enum { HAL_I2C_STATE_RESET = 0, HAL_I2C_STATE_READY = 0x20, HAL_I2C_STATE_BUSY = 0x24 } HAL_I2C_StateTypeDef;
typedef struct {
	uint32_t Instance;
	DMA_HandleTypeDef *hdmatx;
	volatile HAL_I2C_StateTypeDef State;
} I2C_HandleTypeDef;

HAL_StatusTypeDef HAL_I2C_Init(I2C_HandleTypeDef *h);
HAL_I2C_StateTypeDef HAL_I2C_GetState(I2C_HandleTypeDef *h);
HAL_StatusTypeDef HAL_I2C_Mem_Write_DMA(I2C_HandleTypeDef *h, uint16_t dev, uint16_t reg,
		uint16_t reg_size, uint8_t *data, uint16_t size);
HAL_StatusTypeDef HAL_DMA_Abort(DMA_HandleTypeDef *h);
void HAL_I2C_MemTxCpltCallback(I2C_HandleTypeDef *h);
void HAL_I2C_ErrorCallback(I2C_HandleTypeDef *h);

typedef enum { HAL_UART_STATE_RESET = 0, HAL_UART_STATE_READY = 0x20, HAL_UART_STATE_BUSY_TX = 0x21 } HAL_UART_StateTypeDef;
typedef struct {
	uint32_t Instance;
	volatile HAL_UART_StateTypeDef gState;
} UART_HandleTypeDef;

HAL_StatusTypeDef HAL_UART_Transmit_DMA(UART_HandleTypeDef *h, uint8_t *data, uint16_t size);
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h);

#define ADC_CHANNEL_7				(7U)
#define ADC_CHANNEL_8				(8U)
#define ADC_REGULAR_RANK_1			(1U)
#define ADC_SAMPLETIME_239CYCLES_5	(7U)
#define ADC_FLAG_EOC				(2U)
typedef struct { uint32_t Channel, Rank, SamplingTime; } ADC_ChannelConfTypeDef;
typedef struct { uint32_t Instance; uint32_t channel; } ADC_HandleTypeDef;
#define __HAL_ADC_CLEAR_FLAG(h, f)	((void)(h), (void)(f))

HAL_StatusTypeDef HAL_ADC_ConfigChannel(ADC_HandleTypeDef *h, ADC_ChannelConfTypeDef *c);
HAL_StatusTypeDef HAL_ADC_Start(ADC_HandleTypeDef *h);
HAL_StatusTypeDef HAL_ADC_Stop(ADC_HandleTypeDef *h);
HAL_StatusTypeDef HAL_ADC_PollForConversion(ADC_HandleTypeDef *h, uint32_t timeout);
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *h);

#endif
