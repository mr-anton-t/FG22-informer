/* Test image for the SE2266 on this board.
 * Flex count starts at the bottom of the connector.
 * Chip pin 6 is not driven: its net is still unknown.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;

#include "card.h"

/* Autonomous card delivery: the Pico W writes the card planes into the tag's
 * RAM, then sets REQ_FLAG; the tag clears the flag and displays the card. */
#define REQ_FLAG       ((volatile uint32_t *)0x20000100u)
#define CARD_RAM_BLACK 0x20001000u                     /* CARD_SIZE bytes, 1 = black */
#define CARD_RAM_RED   (CARD_RAM_BLACK + 5624u + 8u)   /* CARD_SIZE bytes, 1 = red */

/* Non-secure aliases. This chip faults on the 0x40000000 map. */
#define GPIO_BASE 0x5003C000u
#define CMU_BASE  0x50008000u

#define CMU_LOCK  (CMU_BASE + 0x010u)
#define CMU_CLKEN0 (CMU_BASE + 0x064u)
#define CMU_UNLOCK     0x93F7u
#define CMU_GPIO_BIT   (1u << 26)

#define GPIO_LOCK (GPIO_BASE + 0x300u)
#define GPIO_UNLOCK 0xA534u

/* Port C is the third port, 0x30 bytes each. */
#define PC_MODEL (GPIO_BASE + 0x064u)
#define PC_DOUT  (GPIO_BASE + 0x070u)
#define PC_DIN   (GPIO_BASE + 0x074u)

#define PIN_SDA  0u /* flex 14, chip pin 1, PC00 */
#define PIN_SCL  1u /* flex 13, chip pin 2, PC01 */
#define PIN_CS   2u /* flex 12, chip pin 3, PC02 */
#define PIN_DC   3u /* flex 11, chip pin 4, PC03 */
#define PIN_RST  4u /* flex 10, chip pin 5, PC04 */
/* flex 9, chip pin 7, PC06. Treated as the panel power gate for this test. */
#define PIN_ON   6u

#ifndef ENABLE_PORT
#define ENABLE_PORT 2u /* port C */
#define ENABLE_PIN  7u /* chip pin 8, PC07 */
#endif

#define MODE_INPUT     1u
#define MODE_INPUTPULL 2u
#define MODE_PUSHPULL  4u

#define WIDTH 152u
#define HEIGHT 296u
#define STRIDE (WIDTH / 8u)
extern uint32_t _estack;

static void reset_handler(void);
void Reset_Handler(void);
void HardFault_Handler(void);

__attribute__((section(".isr_vector"), used))
const void *vectors[] = {
  (void *)&_estack,
  (void *)Reset_Handler,
  (void *)HardFault_Handler,
  (void *)HardFault_Handler,
};

#define MARK ((volatile uint32_t *)0x20000000u)

static volatile uint32_t *reg(uint32_t address)
{
  return (volatile uint32_t *)address;
}

static void delay(uint32_t loops)
{
  while (loops--) {
    __asm__ volatile("nop");
  }
}

/* Chip pin 6, PC05. Unknown net; test whether it is the panel's BUSY. */
#define PIN_MAYBE_BUSY 5u

#define BUSY_EDGES ((volatile uint32_t *)0x20000010u)
#define BUSY_LOW   ((volatile uint32_t *)0x20000014u)
#define BUSY_TOTAL ((volatile uint32_t *)0x20000018u)
#define BUSY_LEVEL ((volatile uint32_t *)0x2000001Cu)

/* Sampling wait: same wall clock as the fixed wait, but also watches PC05. */
static void wait_refresh(void)
{
  uint32_t second;
  uint32_t chunk;
  uint32_t prev = 1u;
  uint32_t edges = 0u;
  uint32_t low = 0u;
  uint32_t total = 0u;
  for (second = 0u; second < 40u; second++) {
    for (chunk = 0u; chunk < 8000u; chunk++) {
      uint32_t v = (*reg(PC_DIN) >> PIN_MAYBE_BUSY) & 1u;
      if (v != prev) {
        edges++;
        prev = v;
      }
      if (v == 0u) {
        low++;
      }
      total++;
      delay(1000u);
    }
    *BUSY_EDGES = edges;
    *BUSY_LOW = low;
    *BUSY_TOTAL = total;
    *BUSY_LEVEL = prev;
  }
}

static void pin_mode(uint32_t pin, uint32_t mode)
{
  uint32_t shift = pin * 4u;
  uint32_t model = *reg(PC_MODEL);
  model &= ~(0xFu << shift);
  model |= mode << shift;
  *reg(PC_MODEL) = model;
}

static void pin_set(uint32_t pin, uint32_t high)
{
  uint32_t dout = *reg(PC_DOUT);
  if (high) {
    dout |= 1u << pin;
  } else {
    dout &= ~(1u << pin);
  }
  *reg(PC_DOUT) = dout;
}

static void spi_byte(uint8_t value)
{
  uint32_t bit;
  for (bit = 0x80u; bit != 0u; bit >>= 1) {
    pin_set(PIN_SDA, (value & bit) != 0u);
    delay(20);
    pin_set(PIN_SCL, 1u);
    delay(20);
    pin_set(PIN_SCL, 0u);
  }
}

static void write_cmd(uint8_t command)
{
  pin_set(PIN_DC, 0u);
  pin_set(PIN_CS, 0u);
  spi_byte(command);
  pin_set(PIN_CS, 1u);
}

static void write_data(uint8_t value)
{
  pin_set(PIN_DC, 1u);
  pin_set(PIN_CS, 0u);
  spi_byte(value);
  pin_set(PIN_CS, 1u);
}

static void write_cmd_bytes(uint8_t command, const uint8_t *data, uint32_t count)
{
  uint32_t i;
  pin_set(PIN_DC, 0u);
  pin_set(PIN_CS, 0u);
  spi_byte(command);
  pin_set(PIN_DC, 1u);
  for (i = 0u; i < count; i++) {
    spi_byte(data[i]);
  }
  pin_set(PIN_CS, 1u);
}

static void send_plane(uint8_t command, const uint8_t *data)
{
  uint32_t n = STRIDE * HEIGHT;
  const uint8_t *p = data;
  pin_set(PIN_DC, 0u);
  pin_set(PIN_CS, 0u);
  spi_byte(command);
  pin_set(PIN_DC, 1u);
  while (n--) {
    spi_byte(*p++);
  }
  pin_set(PIN_CS, 1u);
}

/* Panel-native: 1 in the black plane is black, 1 in the red plane is red. */
static void send_frame(const uint8_t *black, const uint8_t *red)
{
  write_cmd(0x00);
  write_data(0x0E);
  delay(200000);
  write_cmd(0xE5);
  /* Panel OTP wave temperature, 0x10 = 20 °C ... 0x2E = 45 °C. */
  write_data(45);
  write_cmd(0xE0);
  write_data(0x02);
  {
    const uint8_t psr[2] = {0xCFu, 0x8Du};
    write_cmd_bytes(0x00, psr, 2u);
  }
  send_plane(0x10, black);
  send_plane(0x13, red);
  write_cmd(0x04);
  delay(800000);
}

void HardFault_Handler(void)
{
  *((volatile uint32_t *)0x20000004u) = 0xEEu;
  for (;;) {
  }
}

void Reset_Handler(void)
{
  *MARK = 1u;
  reset_handler();
}

static void reset_handler(void)
{
  *MARK = 2u;
  *reg(CMU_LOCK) = CMU_UNLOCK;
  *MARK = 3u;
  *reg(CMU_CLKEN0) = *reg(CMU_CLKEN0) | CMU_GPIO_BIT;
  *MARK = 4u;
  *reg(GPIO_LOCK) = GPIO_UNLOCK;
  *MARK = 5u;

  pin_set(PIN_CS, 1u);
  pin_set(PIN_RST, 1u);
  pin_set(PIN_DC, 0u);
  pin_set(PIN_SCL, 0u);
  pin_set(PIN_SDA, 0u);

  pin_mode(PIN_SDA, MODE_PUSHPULL);
  pin_mode(PIN_SCL, MODE_PUSHPULL);
  pin_mode(PIN_CS, MODE_PUSHPULL);
  pin_mode(PIN_DC, MODE_PUSHPULL);
  pin_mode(PIN_RST, MODE_PUSHPULL);
  /* Chip pin 6, watch only: input with pull-up, never driven. */
  pin_set(PIN_MAYBE_BUSY, 1u);
  pin_mode(PIN_MAYBE_BUSY, MODE_INPUTPULL);

  /* Assume the panel power MOSFET gate sits on this line: low = panel on. */
  pin_set(PIN_ON, 0u);
  pin_mode(PIN_ON, MODE_PUSHPULL);
  *MARK = 6u;

  /* Panel reset: high, low, high, then CS released. */
  pin_set(PIN_RST, 1u);
  delay(200000);
  pin_set(PIN_RST, 0u);
  delay(400000);
  pin_set(PIN_RST, 1u);
  delay(200000);
  pin_set(PIN_CS, 1u);
  delay(200000);

  /* Park the lines low so nothing back-powers the panel. */
  pin_set(PIN_CS, 0u);
  pin_set(PIN_SCL, 0u);
  pin_set(PIN_SDA, 0u);
  pin_set(PIN_DC, 0u);
  pin_set(PIN_RST, 0u);

  /* Wait for the Pico W to push a new card: it writes the two card planes
   * into the tag's RAM, then sets REQ_FLAG.  We clear the flag and display. */
  for (;;) {
    if (*REQ_FLAG != 0u) {
      *REQ_FLAG = 0u;
      *MARK = 30u;
      /* The lines were parked low above, RST included, which holds the
       * panel in reset. Pulse RST and leave it high while drawing. */
      pin_set(PIN_CS, 1u);
      pin_set(PIN_RST, 1u);
      delay(200000);
      pin_set(PIN_RST, 0u);
      delay(400000);
      pin_set(PIN_RST, 1u);
      delay(200000);
      send_frame((const uint8_t *)CARD_RAM_BLACK, (const uint8_t *)CARD_RAM_RED);
      write_cmd(0x12);
      *MARK = 31u;
      wait_refresh();
      *MARK = 32u;
    } else {
      delay(500000u);
    }
  }
}
