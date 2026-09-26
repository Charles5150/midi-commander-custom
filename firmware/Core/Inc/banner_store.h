/*
 * banner_store.h
 *
 * The power on banner's own text, kept in a flash page of its own outside
 * the configuration slots, so it stays whatever configuration is loaded and
 * through firmware updates.
 */

#ifndef INC_BANNER_STORE_H_
#define INC_BANNER_STORE_H_

#include <stdint.h>
#include <stdbool.h>

#define BANNER_TEXT_MAX	(60)

// The stored text, not terminated. Returns its length, 0 when there is none.
uint8_t banner_store_get(const char **text);

// Store a text of printable ASCII, at most BANNER_TEXT_MAX characters; an
// empty one clears it. Returns false for a text it refuses or a failed write.
bool banner_store_set(const uint8_t *text, uint8_t len);

#endif /* INC_BANNER_STORE_H_ */
