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

static uint8_t  *USBD_Composite_GetUsrStrDescriptor (USBD_HandleTypeDef *pdev, uint8_t index, uint16_t *length);

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
  USBD_Composite_GetUsrStrDescriptor,
};

/* The HID keyboard, interface 2, 25 bytes: the same in both descriptors */
#define HID_INTERFACE_DESC \
  /* Interface 2: HID, one endpoint, no boot protocol (reports carry IDs) */ \
  0x09, USB_DESC_TYPE_INTERFACE, 0x02, 0x00, 0x01, 0x03, 0x00, 0x00, 0, \
  /* HID descriptor 1.11, one report descriptor */ \
  0x09, HID_DESCRIPTOR_TYPE, 0x11, 0x01, 0x00, 0x01, 0x22, HID_KEYBOARD_REPORT_DESC_SIZE, 0x00, \
  /* Interrupt IN endpoint, polled every 10 ms */ \
  0x07, USB_DESC_TYPE_ENDPOINT, HID_EPIN_ADDR, 0x03, HID_EPIN_SIZE, 0x00, 0x0A

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
  
  HID_INTERFACE_DESC
};

/*
 * Three MIDI ports (USB_Ports): 1 the pedal, 2 the DIN output, 3 the pedal
 * again, so a second program can have it while the first holds port 1 (on
 * Windows only one program opens a port). Each port is a cable: an embedded
 * and an external jack each way, the embedded ones named by a string.
 */
#define USB_COMPOSITE3_CONFIG_DESC_SIZ (190)
#define MIDI_PORT_STR(c)	(0x10 + (c))
#define MIDI_PORT_JACKS(c) \
  0x06, 0x24, 0x02, 0x01, 4 * (c) + 1, MIDI_PORT_STR(c),                   /* IN jack, embedded */ \
  0x06, 0x24, 0x02, 0x02, 4 * (c) + 2, 0x00,                               /* IN jack, external */ \
  0x09, 0x24, 0x03, 0x01, 4 * (c) + 3, 0x01, 4 * (c) + 2, 0x01, MIDI_PORT_STR(c), /* OUT jack, embedded */ \
  0x09, 0x24, 0x03, 0x02, 4 * (c) + 4, 0x01, 4 * (c) + 1, 0x01, 0x00       /* OUT jack, external */

__ALIGN_BEGIN static uint8_t USBD_Composite3_CfgDesc[USB_COMPOSITE3_CONFIG_DESC_SIZ]  __ALIGN_END =
{
  0x09, 0x02, LOBYTE(USB_COMPOSITE3_CONFIG_DESC_SIZ), HIBYTE(USB_COMPOSITE3_CONFIG_DESC_SIZ), 0x03, 0x01, 0x00, 0x80, 0x31,

  0x09, 0x04, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x00, // Standard AC Interface Descriptor
  0x09, 0x24, 0x01, 0x00, 0x01, 0x09, 0x00, 0x01, 0x01, // Class-specific AC Interface Descriptor

  0x09, 0x04, 0x01, 0x00, 0x02, 0x01, 0x03, 0x00, 0x00, // MIDIStreaming Interface Descriptors
  0x07, 0x24, 0x01, 0x00, 0x01, 0x81, 0x00,             // MS Header, 129 bytes to the end of the endpoints

  MIDI_PORT_JACKS(0),
  MIDI_PORT_JACKS(1),
  MIDI_PORT_JACKS(2),

  // OUT endpoint: cables 0, 1, 2 are embedded IN jacks 1, 5, 9
  0x09, 0x05, MIDI_OUT_EP, 0x02, 0x40, 0x00, 0x00, 0x00, 0x00,
  0x07, 0x25, 0x01, 0x03, 0x01, 0x05, 0x09,

  // IN endpoint: cables 0, 1, 2 are embedded OUT jacks 3, 7, 11
  0x09, 0x05, MIDI_IN_EP, 0x02, 0x40, 0x00, 0x00, 0x00, 0x00,
  0x07, 0x25, 0x01, 0x03, 0x03, 0x07, 0x0B,

  HID_INTERFACE_DESC
};

static uint8_t *cfg_desc = USBD_Composite_CfgDesc;
static uint16_t cfg_desc_len = sizeof(USBD_Composite_CfgDesc);

extern uint8_t USBD_FS_DeviceDesc[];
extern uint8_t USBD_StrDesc[];

// Before USB starts. Another device release too, so Windows does not reuse
// what it remembers of the other layout.
void usb_composite_ports(uint8_t ports){
  if(ports == 3){
    cfg_desc = USBD_Composite3_CfgDesc;
    cfg_desc_len = sizeof(USBD_Composite3_CfgDesc);
    USBD_FS_DeviceDesc[12] = 0x30;	// bcdDevice 2.30
  }
}

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
  *length = cfg_desc_len;
  return cfg_desc;
}

static uint8_t  *USBD_Composite_GetDeviceQualifierDesc (uint16_t *length)
{
  *length = sizeof (USBD_Composite_DeviceQualifierDesc);
  return USBD_Composite_DeviceQualifierDesc;
}

// The port names, for the jacks of the three port layout
static uint8_t  *USBD_Composite_GetUsrStrDescriptor (USBD_HandleTypeDef *pdev, uint8_t index, uint16_t *length)
{
  static const char *const names[] = {"Pedal", "DIN", "Config"};
  if(index < MIDI_PORT_STR(0) || index > MIDI_PORT_STR(2)){
    USBD_CtlError(pdev, NULL);	// as for any string it does not have
    *length = 0;
    return NULL;
  }
  USBD_GetString((uint8_t *)names[index - MIDI_PORT_STR(0)], USBD_StrDesc, length);
  return USBD_StrDesc;
}
