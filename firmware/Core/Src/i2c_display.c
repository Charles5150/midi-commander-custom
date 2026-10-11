/*
 * The I2C to the display, register by register: what the display library
 * needs and nothing else, where the HAL's I2C and DMA drivers took four and a
 * half kilobytes.
 *
 * A transfer is one write to the display, its control byte first. It starts
 * as the HAL's did: the START and the address are waited for, some 30 us,
 * and the DMA sends the rest. At the end of the DMA the last byte is still
 * going out, so its interrupt waits for BTF in the event interrupt, which
 * sends the STOP and tells the library (ssd1306_TxDone). A NACK or a bus
 * error ends it in the error interrupt (ssd1306_TxFailed). No wait is
 * endless: a bus that stays busy is reset, and so is a transfer that never
 * ends (i2c_display_stuck).
 */
#include "main.h"
#include "ssd1306.h"

#define I2C_SPIN_MAX		(20000U)	// over 1 ms at 72 MHz
#define I2C_STUCK_MS		(50U)		// a whole line takes about 3.5 ms

static volatile uint8_t busy = 0;
static volatile uint32_t started = 0;

// 400 kHz from APB1's 36 MHz, as HAL_I2C_Init set it: duty 2, CCR 30
static void configure(void)
{
	I2C1->CR1 = I2C_CR1_SWRST;
	I2C1->CR1 = 0;
	I2C1->CR2 = 36U;			// FREQ: APB1 in MHz
	I2C1->TRISE = 36U * 300U / 1000U + 1U;
	I2C1->CCR = I2C_CCR_FS | 30U;
	I2C1->OAR1 = 0x4000U;			// bit 14 kept at 1, as the manual asks
	I2C1->CR1 = I2C_CR1_PE;
}

void i2c_display_init(void)
{
	__HAL_RCC_GPIOB_CLK_ENABLE();
	gpio_config(GPIOB, GPIO_PIN_6|GPIO_PIN_7, PIN_AF_OD);	// SCL, SDA
	__HAL_RCC_I2C1_CLK_ENABLE();
	configure();
	HAL_NVIC_SetPriority(I2C1_EV_IRQn, 0, 0);
	HAL_NVIC_EnableIRQ(I2C1_EV_IRQn);
	HAL_NVIC_SetPriority(I2C1_ER_IRQn, 0, 0);
	HAL_NVIC_EnableIRQ(I2C1_ER_IRQn);
	// DMA1 channel 6 and its interrupt are set up with the DMA, in main.c
}

static void dma_off(void)
{
	DMA1_Channel6->CCR = 0;
	DMA1->IFCR = DMA_IFCR_CGIF6;
	I2C1->CR2 &= ~(I2C_CR2_DMAEN | I2C_CR2_ITEVTEN | I2C_CR2_ITERREN);
}

// Drop whatever is going out and start the I2C again
void i2c_display_reset(void)
{
	uint32_t primask = __get_PRIMASK();
	__disable_irq();
	dma_off();
	configure();
	busy = 0;
	if(!primask) __enable_irq();
}

uint8_t i2c_display_busy(void)
{
	return busy;
}

// A transfer that has gone on far longer than a line takes
uint8_t i2c_display_stuck(void)
{
	return busy && HAL_GetTick() - started > I2C_STUCK_MS;
}

static uint8_t wait_flag(uint32_t flag)
{
	for(uint32_t n = 0; !(I2C1->SR1 & flag); n++){
		if(n > I2C_SPIN_MAX || (I2C1->SR1 & I2C_SR1_AF)) return 0;
	}
	return 1;
}

/*
 * Start writing len bytes to the display, the control byte first. False when
 * it could not start: the bus stayed busy (it is reset), or the display did
 * not answer its address.
 */
uint8_t i2c_display_write(const uint8_t *data, uint16_t len)
{
	if(busy) return 0;
	// The STOP of the last transfer may still be going out: a few us
	for(uint32_t n = 0; (I2C1->SR2 & I2C_SR2_BUSY) || (I2C1->CR1 & I2C_CR1_STOP); n++){
		if(n > I2C_SPIN_MAX){
			i2c_display_reset();
			return 0;
		}
	}

	DMA1_Channel6->CCR = 0;
	DMA1->IFCR = DMA_IFCR_CGIF6;
	DMA1_Channel6->CPAR = (uint32_t)&I2C1->DR;
	DMA1_Channel6->CMAR = (uint32_t)data;
	DMA1_Channel6->CNDTR = len;
	DMA1_Channel6->CCR = DMA_CCR_MINC | DMA_CCR_DIR | DMA_CCR_TCIE | DMA_CCR_TEIE | DMA_CCR_EN;

	I2C1->CR1 &= ~I2C_CR1_POS;
	I2C1->CR1 |= I2C_CR1_START;
	if(!wait_flag(I2C_SR1_SB)) goto failed;
	I2C1->DR = SSD1306_I2C_ADDR;
	if(!wait_flag(I2C_SR1_ADDR)) goto failed;

	started = HAL_GetTick();
	busy = 1;
	(void)I2C1->SR2;			// after SR1, clears ADDR
	I2C1->CR2 |= I2C_CR2_ITERREN | I2C_CR2_DMAEN;
	return 1;

failed:
	dma_off();
	I2C1->SR1 = 0;				// AF, if that was it
	I2C1->CR1 |= I2C_CR1_STOP;
	return 0;
}

static void failed(void)
{
	dma_off();
	I2C1->SR1 = 0;				// the error flags
	I2C1->CR1 |= I2C_CR1_STOP;
	busy = 0;
	ssd1306_TxFailed();
}

// The DMA has handed the last byte over: BTF says when it has gone out
void DMA1_Channel6_IRQHandler(void)
{
	uint32_t isr = DMA1->ISR;
	DMA1->IFCR = DMA_IFCR_CGIF6;
	DMA1_Channel6->CCR = 0;
	I2C1->CR2 &= ~I2C_CR2_DMAEN;
	if(!busy) return;
	if(isr & DMA_ISR_TEIF6){
		failed();
	} else if(isr & DMA_ISR_TCIF6){
		I2C1->CR2 |= I2C_CR2_ITEVTEN;
	}
}

void I2C1_EV_IRQHandler(void)
{
	// BTF is the only event asked for
	if(busy && (I2C1->SR1 & I2C_SR1_BTF)){
		I2C1->CR1 |= I2C_CR1_STOP;
		I2C1->CR2 &= ~(I2C_CR2_ITEVTEN | I2C_CR2_ITERREN);
		busy = 0;
		ssd1306_TxDone();
	} else if(!busy){
		I2C1->CR2 &= ~I2C_CR2_ITEVTEN;
	}
}

// A NACK, a bus error or a lost arbitration
void I2C1_ER_IRQHandler(void)
{
	if(busy){
		failed();
	} else {
		I2C1->SR1 = 0;
		I2C1->CR2 &= ~I2C_CR2_ITERREN;
	}
}
