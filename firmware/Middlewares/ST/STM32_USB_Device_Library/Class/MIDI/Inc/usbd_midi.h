/**
  ******************************************************************************
  * @file    usbd_midi.h
  ******************************************************************************

  (CC at)2016 by D.F.Mac. @TripArts Music

*/ 
 
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __USB_MIDI_H
#define __USB_MIDI_H

#ifdef __cplusplus
 extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include  "usbd_ioreq.h"

#define MIDI_IN_EP                                   0x81  /* EP1 for data IN */
#define MIDI_OUT_EP                                  0x01  /* EP1 for data OUT */
// #define MIDI_DATA_HS_MAX_PACKET_SIZE                 512  /* Endpoint IN & OUT Packet size */
#define MIDI_DATA_FS_MAX_PACKET_SIZE                 64  /* Endpoint IN & OUT Packet size */
#define MIDI_CMD_PACKET_SIZE                         8  /* Control Endpoint Packet size */ 

#define USB_MIDI_CONFIG_DESC_SIZ                    101
#define MIDI_DATA_IN_PACKET_SIZE                    MIDI_DATA_FS_MAX_PACKET_SIZE
#define MIDI_DATA_OUT_PACKET_SIZE                   MIDI_DATA_FS_MAX_PACKET_SIZE
#define APP_RX_DATA_SIZE               				((MIDI_DATA_FS_MAX_PACKET_SIZE) * 4) //2048->256

#define MIDI_IN_FRAME_INTERVAL		1

typedef struct _USBD_MIDI_ItfTypeDef{
  uint16_t (*pIf_MidiRx)    (uint8_t *msg, uint16_t length);
  uint16_t (*pIf_MidiTx)    (uint8_t *msg, uint16_t length);
}USBD_MIDI_ItfTypeDef;

extern uint8_t APP_Rx_Buffer   [APP_RX_DATA_SIZE];
extern uint32_t APP_Rx_ptr_in;
extern uint32_t APP_Rx_ptr_out;
extern uint32_t APP_Rx_length;
extern volatile uint8_t  USB_Tx_State;

// Called by the composite class (usbd_composite_midi_hid.c), which alone
// describes the device: MIDI has no class table or descriptor of its own
uint8_t USBD_MIDI_Init(USBD_HandleTypeDef *pdev, uint8_t cfgidx);
uint8_t USBD_MIDI_DeInit(USBD_HandleTypeDef *pdev, uint8_t cfgidx);
uint8_t USBD_MIDI_DataIn(USBD_HandleTypeDef *pdev, uint8_t epnum);
uint8_t USBD_MIDI_DataOut(USBD_HandleTypeDef *pdev, uint8_t epnum);

uint8_t  USBD_MIDI_RegisterInterface  (USBD_HandleTypeDef   *pdev, 
                                      USBD_MIDI_ItfTypeDef *fops);

#ifdef __cplusplus
}
#endif

#endif  /* __USB_MIDI_H */
