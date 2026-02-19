/*
 * usbd_composite_midi_hid.c
 *
 *  Created on: Feb 3, 2026
 *      Author: Agent
 */

#include "usbd_composite_midi_hid.h"
#include "usbd_desc.h"
#include "usbd_ctlreq.h"

static uint8_t  USBD_Composite_Init (USBD_HandleTypeDef *pdev,
                               uint8_t cfgidx);

static uint8_t  USBD_Composite_DeInit (USBD_HandleTypeDef *pdev,
                                 uint8_t cfgidx);

static uint8_t  USBD_Composite_Setup (USBD_HandleTypeDef *pdev,
                                USBD_SetupReqTypedef *req);

static uint8_t  USBD_Composite_DataIn (USBD_HandleTypeDef *pdev, uint8_t epnum);

static uint8_t  USBD_Composite_DataOut (USBD_HandleTypeDef *pdev, uint8_t epnum);

static uint8_t  *USBD_Composite_GetCfgDesc (uint16_t *length);

static uint8_t  *USBD_Composite_GetDeviceQualifierDesc (uint16_t *length);

USBD_ClassTypeDef  USBD_COMPOSITE_MIDI_HID =
{
  USBD_Composite_Init,
  USBD_Composite_DeInit,
  USBD_Composite_Setup,
  NULL, /*EP0_TxSent*/
  NULL, /*EP0_RxReady*/
  USBD_Composite_DataIn,
  USBD_Composite_DataOut,
  NULL, /*SOF */
  NULL,
  NULL,
  USBD_Composite_GetCfgDesc,
  USBD_Composite_GetCfgDesc,
  USBD_Composite_GetCfgDesc,
  USBD_Composite_GetDeviceQualifierDesc,
};

/* USB Composite Configuration Descriptor */
#define USB_COMPOSITE_CONFIG_DESC_SIZ (126)

__ALIGN_BEGIN static uint8_t USBD_Composite_CfgDesc[USB_COMPOSITE_CONFIG_DESC_SIZ]  __ALIGN_END =
{
  /* Configuration Descriptor */
  0x09, 0x02, 0x7E, 0x00, 0x03, 0x01, 0x00, 0x80, 0x31,
  
  /* --- MIDI Descriptor (92 bytes) --- */
  // The Audio Interface Collection (Interface 0)
  0x09, 0x04, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x00, // Standard AC Interface Descriptor
  0x09, 0x24, 0x01, 0x00, 0x01, 0x09, 0x00, 0x01, 0x01, // Class-specific AC Interface Descriptor
  
  // Interface 1: MIDIStreaming
  0x09, 0x04, 0x01, 0x00, 0x02, 0x01, 0x03, 0x00, 0x00, // MIDIStreaming Interface Descriptors
  0x07, 0x24, 0x01, 0x00, 0x01, 0x41, 0x00,             // Class-Specific MS Interface Header Descriptor

  // MIDI IN JACKS
  0x06, 0x24, 0x02, 0x01, 0x01, 0x00,
  0x06, 0x24, 0x02, 0x02, 0x02, 0x00,

  // MIDI OUT JACKS
  0x09, 0x24, 0x03, 0x01, 0x03, 0x01, 0x02, 0x01, 0x00,
  0x09, 0x24, 0x03, 0x02, 0x06, 0x01, 0x01, 0x01, 0x00,

  // OUT endpoint descriptor
  0x09, 0x05, MIDI_OUT_EP, 0x02, 0x40, 0x00, 0x00, 0x00, 0x00,
  0x05, 0x25, 0x01, 0x01, 0x01,

  // IN endpoint descriptor
  0x09, 0x05, MIDI_IN_EP, 0x02, 0x40, 0x00, 0x00, 0x00, 0x00,
  0x05, 0x25, 0x01, 0x01, 0x03,
  
  /* --- HID Descriptor (25 bytes) --- */
  /* Interface 2 */
  0x09,         /*bLength: Interface Descriptor size*/
  USB_DESC_TYPE_INTERFACE,/*bDescriptorType: Interface descriptor type*/
  0x02,         /*bInterfaceNumber: Number of Interface*/ /* CHANGED TO 0x02 */
  0x00,         /*bAlternateSetting: Alternate setting*/
  0x01,         /*bNumEndpoints*/
  0x03,         /*bInterfaceClass: HID*/
  0x01,         /*bInterfaceSubClass : 1=BOOT, 0=no boot*/
  0x01,         /*nInterfaceProtocol : 0=none, 1=keyboard, 2=mouse*/
  0,            /*iInterface: Index of string descriptor*/

  /******************** Descriptor of Joystick Mouse HID ********************/
  /* 18 */
  0x09,         /*bLength: HID Descriptor size*/
  HID_DESCRIPTOR_TYPE, /*bDescriptorType: HID*/
  0x11,         /*bcdHID: HID Class Spec release number*/
  0x01,
  0x00,         /*bCountryCode: Hardware target country*/
  0x01,         /*bNumDescriptors: Number of HID class descriptors to follow*/
  0x22,         /*bDescriptorType*/
  HID_KEYBOARD_REPORT_DESC_SIZE,/*wItemLength: Total length of Report descriptor*/
  0x00,
  /******************** Descriptor of Mouse endpoint ********************/
  /* 27 */
  0x07,          /*bLength: Endpoint Descriptor size*/
  USB_DESC_TYPE_ENDPOINT, /*bDescriptorType:*/

  HID_EPIN_ADDR,     /*bEndpointAddress: Endpoint Address (IN)*/
  0x03,          /*bmAttributes: Interrupt endpoint*/
  HID_EPIN_SIZE, /*wMaxPacketSize: 4 Byte max */
  0x00,
  0x0A,          /*bInterval: Polling Interval (10 ms)*/
};

/* USB Device Qualifier Descriptor */
__ALIGN_BEGIN static uint8_t USBD_Composite_DeviceQualifierDesc[USB_LEN_DEV_QUALIFIER_DESC]  __ALIGN_END =
{
  USB_LEN_DEV_QUALIFIER_DESC,
  USB_DESC_TYPE_DEVICE_QUALIFIER,
  0x00,
  0x02,
  0x00,
  0x00,
  0x00,
  0x40,
  0x01,
  0x00,
};

static uint8_t  USBD_Composite_Init (USBD_HandleTypeDef *pdev,
                               uint8_t cfgidx)
{
    // Init MIDI
    if(USBD_MIDI.Init(pdev, cfgidx) != USBD_OK) return USBD_FAIL;
    
    // Init HID
    if(USBD_HID_CUSTOM.Init(pdev, cfgidx) != USBD_OK) return USBD_FAIL;
    
    return USBD_OK;
}

static uint8_t  USBD_Composite_DeInit (USBD_HandleTypeDef *pdev,
                                 uint8_t cfgidx)
{
    USBD_MIDI.DeInit(pdev, cfgidx);
    USBD_HID_CUSTOM.DeInit(pdev, cfgidx);
    return USBD_OK;
}

static uint8_t  USBD_Composite_Setup (USBD_HandleTypeDef *pdev,
                                USBD_SetupReqTypedef *req)
{
    // Check Interface Number
    // Standard Requests with Interface Recipient or Class Requests with Interface Recipient
    
    if(((req->bmRequest & USB_REQ_TYPE_MASK) == USB_REQ_TYPE_CLASS) || 
       ((req->bmRequest & USB_REQ_TYPE_MASK) == USB_REQ_TYPE_STANDARD)) {
           
       if(req->wIndex >= 2) {
           // HID Interface
           return USBD_HID_CUSTOM.Setup(pdev, req);
       } else {
           // MIDI Interfaces (0 or 1)
           if(USBD_MIDI.Setup != NULL) {
               return USBD_MIDI.Setup(pdev, req);
           }
       }
    }
    
    return USBD_OK;
}

static uint8_t  USBD_Composite_DataIn (USBD_HandleTypeDef *pdev, uint8_t epnum)
{
    if(epnum == (MIDI_IN_EP & 0x7F)) {
        return USBD_MIDI.DataIn(pdev, epnum);
    } else if(epnum == (HID_EPIN_ADDR & 0x7F)) {
        return USBD_HID_CUSTOM.DataIn(pdev, epnum);
    }
    return USBD_OK;
}

static uint8_t  USBD_Composite_DataOut (USBD_HandleTypeDef *pdev, uint8_t epnum)
{
    if(epnum == (MIDI_OUT_EP & 0x7F)) {
        return USBD_MIDI.DataOut(pdev, epnum);
    }
    return USBD_OK;
}

static uint8_t  *USBD_Composite_GetCfgDesc (uint16_t *length)
{
  *length = sizeof (USBD_Composite_CfgDesc);
  return USBD_Composite_CfgDesc;
}

static uint8_t  *USBD_Composite_GetDeviceQualifierDesc (uint16_t *length)
{
  *length = sizeof (USBD_Composite_DeviceQualifierDesc);
  return USBD_Composite_DeviceQualifierDesc;
}
