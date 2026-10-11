/*
 * The DIN output's UART, register by register: it only sends, 31250 baud, a
 * block at a time by DMA, where the HAL's UART driver took about a kilobyte.
 * At the end of the DMA the last byte is still going out, so its interrupt
 * waits for TC, the line gone quiet, before saying the UART is free again
 * (din_uart_done in midi_cmds.c), as the HAL's TxCpltCallback did.
 */
#include "main.h"

static volatile uint8_t busy = 0;

void din_uart_init(void)
{
	__HAL_RCC_USART2_CLK_ENABLE();
	__HAL_RCC_GPIOA_CLK_ENABLE();
	gpio_config(GPIOA, GPIO_PIN_2, PIN_AF_PP);	// TX
	gpio_config(GPIOA, GPIO_PIN_3, PIN_IN);		// RX, not used
	USART2->CR1 = 0;
	USART2->CR2 = 0;				// 1 stop bit
	USART2->CR3 = 0;
	USART2->BRR = 36000000U / 31250U;		// APB1 at 36 MHz: 72.0
	USART2->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
	HAL_NVIC_SetPriority(USART2_IRQn, 0, 0);
	HAL_NVIC_EnableIRQ(USART2_IRQn);
	// DMA1 channel 7 and its interrupt are set up with the DMA, in main.c
}

uint8_t din_uart_ready(void)
{
	return !busy;
}

// Start sending len bytes, which must stay put until it is done; false if
// the UART is still busy
uint8_t din_uart_send(const uint8_t *data, uint16_t len)
{
	if(busy || !len) return 0;
	busy = 1;
	DMA1_Channel7->CCR = 0;
	DMA1->IFCR = DMA_IFCR_CGIF7;
	DMA1_Channel7->CPAR = (uint32_t)&USART2->DR;
	DMA1_Channel7->CMAR = (uint32_t)data;
	DMA1_Channel7->CNDTR = len;
	DMA1_Channel7->CCR = DMA_CCR_MINC | DMA_CCR_DIR | DMA_CCR_TCIE | DMA_CCR_TEIE | DMA_CCR_EN;
	USART2->SR = ~USART_SR_TC;			// TC is cleared by writing 0
	USART2->CR3 |= USART_CR3_DMAT;
	return 1;
}

// The DMA has handed the last byte over: TC says when it has gone out
void DMA1_Channel7_IRQHandler(void)
{
	DMA1->IFCR = DMA_IFCR_CGIF7;
	DMA1_Channel7->CCR = 0;
	USART2->CR3 &= ~USART_CR3_DMAT;
	if(busy) USART2->CR1 |= USART_CR1_TCIE;
}

void USART2_IRQHandler(void)
{
	if((USART2->CR1 & USART_CR1_TCIE) && (USART2->SR & USART_SR_TC)){
		USART2->CR1 &= ~USART_CR1_TCIE;
		busy = 0;
		din_uart_done();
	}
}
