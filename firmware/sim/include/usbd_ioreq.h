/* usbd_ioreq.h for the simulator: the device types the headers mention */
#ifndef SIM_USBD_IOREQ_H
#define SIM_USBD_IOREQ_H

#include <stdint.h>

typedef enum { USBD_OK = 0, USBD_BUSY, USBD_FAIL } USBD_StatusTypeDef;
typedef struct { uint8_t unused; } USBD_HandleTypeDef;
typedef struct { uint8_t unused; } USBD_ClassTypeDef;

#endif
