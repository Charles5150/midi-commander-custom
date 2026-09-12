/*
 * usbd_hid_custom.h
 *
 *  Created on: Feb 3, 2026
 *      Author: Agent
 */

#ifndef __USBD_HID_CUSTOM_H
#define __USBD_HID_CUSTOM_H

#ifdef __cplusplus
 extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include  "usbd_ioreq.h"

#define HID_EPIN_ADDR                 0x82
#define HID_EPIN_SIZE                 0x10

// Report IDs: the interface carries a keyboard and a consumer control report
#define HID_REPORT_ID_KEYBOARD        0x01   // 8 bytes: modifiers, reserved, 6 keys
#define HID_REPORT_ID_CONSUMER        0x02   // 2 bytes: 16-bit consumer usage (0 = release)

#define USB_HID_CONFIG_DESC_SIZ       34
#define USB_HID_DESC_SIZ              9
#define HID_KEYBOARD_REPORT_DESC_SIZE 90

#define HID_DESCRIPTOR_TYPE           0x21
#define HID_REPORT_DESC               0x22

#define HID_REQ_SET_PROTOCOL          0x0B
#define HID_REQ_GET_PROTOCOL          0x03

#define HID_REQ_SET_IDLE              0x0A
#define HID_REQ_GET_IDLE              0x02

#define HID_REQ_SET_REPORT            0x09
#define HID_REQ_GET_REPORT            0x01

typedef enum
{
  HID_IDLE = 0,
  HID_BUSY,
}
HID_StateTypeDef;


typedef struct
{
  uint32_t             Protocol;
  uint32_t             IdleState;
  uint32_t             AltSetting;
  HID_StateTypeDef     state;
}
USBD_HID_HandleTypeDef;


extern USBD_ClassTypeDef  USBD_HID_CUSTOM;
#define USBD_HID_CUSTOM_CLASS    &USBD_HID_CUSTOM

uint8_t USBD_HID_SendReport (USBD_HandleTypeDef *pdev,
                                 uint8_t *report,
                                 uint16_t len);

uint8_t HID_SendReport_FS(uint8_t *report, uint16_t len);

uint32_t USBD_HID_GetPollingInterval (USBD_HandleTypeDef *pdev);

#ifdef __cplusplus
}
#endif

#endif /* __USBD_HID_CUSTOM_H */
