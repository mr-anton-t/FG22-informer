# pico_swd.py — minimal ARM SWD host for MicroPython (RP2040/Pico W).
#
# Target: EFR32FG22 (Cortex-M33) on the SE2266 tag.
# Wires (docs/pins.md): SWCLK -> Pico W GP2 (physical pin 4),
#                       SWDIO -> Pico W GP3 (physical pin 5), plus GND.
#
# Bit timing follows the ARM CMSIS-DAP reference bit-bang (SW_DP.c):
#   write bit: put SWDIO, SWCLK low, SWCLK high   (target samples on rise)
#   read bit:  SWCLK low, sample SWDIO, SWCLK high (target drives on rise)
#   SWCLK idles high between bits.
#
# A transaction:
#   8-bit request [Start=1][APnDP][RnW][A2][A3][Parity][Stop=0][Park=1]
#   turnaround (host releases SWDIO), 3-bit ACK (OK=1, WAIT=2, FAULT=4)
#   read:  32 data bits + parity, turnaround, host takes SWDIO back
#   write: turnaround, host takes SWDIO, 32 data bits + parity
#   then a few idle cycles with SWDIO low.
#
# Before the first transaction the target must see a line reset (>= 50
# clocks with SWDIO high). connect() sends JTAG-to-SWD and, if that is not
# enough, the dormant-to-SWD wake-up (SWJ-DP v2), then a line reset.
#
# AP reads are posted: an AP read returns the result of the *previous* AP
# read, so the value is fetched from DP RDBUFF.

import time

import machine

_CLK = machine.Pin(2, machine.Pin.OUT, value=1)   # GP2, physical pin 4
_DIO = machine.Pin(3, machine.Pin.OUT, value=1)   # GP3, physical pin 5
_OUT = machine.Pin.OUT
_IN = machine.Pin.IN
_PULL_UP = machine.Pin.PULL_UP

ACK_OK = 1
ACK_WAIT = 2
ACK_FAULT = 4

# DP registers
DP_IDCODE = 0x00     # read
DP_ABORT = 0x00      # write
DP_CTRL_STAT = 0x04
DP_SELECT = 0x08
DP_RDBUFF = 0x0C

# MEM-AP registers (AP bank 0)
AP_CSW = 0x00
AP_TAR = 0x04
AP_DRW = 0x0C

CARD_RAM_BLACK = 0x20001000   # tag RAM: card planes (1 = black)
CARD_RAM_RED   = 0x20002600   # tag RAM: card planes (1 = red)
REQ_FLAG       = 0x20000100   # tag RAM: nonzero = display the card
SCRATCH        = 0x20000200   # tag RAM word not used by the tag firmware
MARK           = 0x20000000   # tag RAM: 30 flag seen, 31 refreshing, 32 done

# Tag GPIO port C output register (non-secure alias). The flashed tag
# firmware parks the panel RST line (PC04) low after boot and never raises
# it again, so the panel stays in reset and ignores the frame. Raise it over
# SWD before asking for a frame.
PC_DOUT  = 0x5003C074 - 4
PIN_RST  = 1 << 4

IDLE_CYCLES = 8
WAIT_RETRIES = 100


class SWDError(RuntimeError):
    pass


# --- bit level ---------------------------------------------------------------

def _drive():
    _DIO.init(_OUT)


def _release():
    _DIO.init(_IN, _PULL_UP)


def _wbit(b):
    _DIO.value(b)
    _CLK.value(0)
    _CLK.value(1)


def _rbit():
    _CLK.value(0)
    v = _DIO.value()
    _CLK.value(1)
    return v


def _cycle():
    _CLK.value(0)
    _CLK.value(1)


def _wbits(value, n):
    for i in range(n):
        _wbit((value >> i) & 1)


def _rbits(n):
    v = 0
    for i in range(n):
        v |= _rbit() << i
    return v


def _seq(data):
    """Send a raw bit sequence, bytes LSB first (OpenOCD swd.h format)."""
    _drive()
    for i in range(len(data) * 8):
        _wbit((data[i >> 3] >> (i & 7)) & 1)


def _parity(v):
    return bin(v).count("1") & 1


# Sequences from OpenOCD src/jtag/swd.h.
_LINE_RESET = bytes([0xFF] * 7 + [0x00])                   # 56 high + 8 low
_JTAG_TO_SWD = bytes([0xFF] * 7 + [0x9E, 0xE7] + [0xFF] * 7 + [0x00])
_DORMANT_TO_SWD = bytes([
    0xFF,
    0x92, 0xF3, 0x09, 0x62, 0x95, 0x2D, 0x85, 0x86,
    0xE9, 0xAF, 0xDD, 0xE3, 0xA2, 0x0E, 0xBC, 0x19,
    0xA0, 0xF1, 0xFF,
])
_SWD_TO_DORMANT = bytes([0xFF] * 7 + [0xBC, 0xE3])     # line reset + 0xE3BC


# --- transaction level -------------------------------------------------------

def _trans_once(apn_dp, rn_w, reg, value=0):
    """One SWD transaction. Returns (ack, data)."""
    a2 = (reg >> 2) & 1
    a3 = (reg >> 3) & 1
    req = (1 | (apn_dp << 1) | (rn_w << 2) | (a2 << 3) | (a3 << 4)
           | (((apn_dp + rn_w + a2 + a3) & 1) << 5) | (1 << 7))
    _drive()
    _wbits(req, 8)
    _release()
    _cycle()                       # turnaround
    ack = _rbits(3)

    if ack == ACK_OK:
        data = None
        if rn_w:
            data = _rbits(32)
            par = _rbit()
            _cycle()               # turnaround
            _drive()
            if _parity(data) != par:
                _idle()
                raise SWDError("read parity error")
        else:
            _cycle()               # turnaround
            _drive()
            _wbits(value, 32)
            _wbit(_parity(value))
        _idle()
        return ack, data

    if ack in (ACK_WAIT, ACK_FAULT):
        _cycle()                   # turnaround (no data phase)
        _drive()
        _DIO.value(1)
        return ack, None

    # No response or protocol error: clock out a whole data phase, take the
    # line back. The caller should line-reset before trying again.
    for _ in range(33 + 1):
        _cycle()
    _drive()
    _DIO.value(1)
    return ack, None


def _idle():
    _DIO.value(0)
    for _ in range(IDLE_CYCLES):
        _cycle()
    _DIO.value(1)


def swd_trans(apn_dp, rn_w, reg, value=0):
    """One transaction with WAIT retries. Raises SWDError on FAULT/no ACK."""
    for _ in range(WAIT_RETRIES):
        ack, data = _trans_once(apn_dp, rn_w, reg, value)
        if ack == ACK_OK:
            return data
        if ack != ACK_WAIT:
            break
    if ack == ACK_FAULT:
        # Clear sticky errors so the next transaction can work.
        _trans_once(0, 0, DP_ABORT, 0x1E)
        raise SWDError("SWD FAULT (sticky error cleared)")
    if ack == ACK_WAIT:
        raise SWDError("SWD WAIT: target busy")
    raise SWDError("SWD ack 0x%X: no answer from the tag "
                   "(check wires, GND, tag power)" % ack)


def dp_read(reg):
    return swd_trans(0, 1, reg)


def dp_write(reg, value):
    swd_trans(0, 0, reg, value)


def ap_read(reg):
    swd_trans(1, 1, reg)           # posted: result goes to RDBUFF
    return dp_read(DP_RDBUFF)


def ap_write(reg, value):
    swd_trans(1, 0, reg, value)


# --- connect -----------------------------------------------------------------

def _try_idcode():
    ack, data = _trans_once(0, 1, DP_IDCODE)
    return data if ack == ACK_OK else None


def connect():
    """Wake the SW-DP, power up the debug domain, set up the MEM-AP.
    Returns the DPIDR. Raises SWDError if the tag does not answer."""
    idcode = None
    # 1) plain SWJ-DP: JTAG -> SWD; 2) SWJ-DP v2 that may sit in dormant
    #    state: go to dormant from any state, then wake into SWD.
    for seqs in ((_JTAG_TO_SWD,),
                 (_JTAG_TO_SWD, _SWD_TO_DORMANT, _DORMANT_TO_SWD)):
        for s in seqs:
            _seq(s)
        _seq(_LINE_RESET)
        idcode = _try_idcode()
        if idcode is not None:
            break
    if idcode is None:
        raise SWDError("SWD ack 0x7: no answer from the tag after line reset "
                       "(check wires, GND, tag power)")

    dp_write(DP_ABORT, 0x1E)       # clear sticky errors
    dp_write(DP_SELECT, 0)         # AP 0, bank 0
    dp_write(DP_CTRL_STAT, 0x50000000)   # CSYSPWRUPREQ | CDBGPWRUPREQ
    for _ in range(100):
        if dp_read(DP_CTRL_STAT) & 0xA0000000 == 0xA0000000:
            break
        time.sleep_ms(1)
    else:
        raise SWDError("debug power-up not acknowledged (CTRL/STAT 0x%08X)"
                       % dp_read(DP_CTRL_STAT))

    # The FG22 AP is an AHB5-AP; its reset CSW (0x43800052) has HNONSEC=1,
    # and a non-secure access to the (secure) RAM faults. Use OpenOCD's
    # CSW_AHB_DEFAULT: DbgSwEnable | MasterType=debug | HPROT1 (privileged),
    # HNONSEC=0 (secure), 32-bit transfers, auto-increment single.
    ap_write(AP_CSW, 0xA2000012)
    return idcode


def attach():
    """Kept for old callers: same as connect()."""
    return connect()


# --- memory access -----------------------------------------------------------

def swd_mem_write(addr, value):
    ap_write(AP_TAR, addr)
    ap_write(AP_DRW, value)


def swd_mem_read(addr):
    ap_write(AP_TAR, addr)
    return ap_read(AP_DRW)


def write_block(addr, buf):
    """Write a byte buffer (length multiple of 4) as little-endian words.
    TAR auto-increment is only guaranteed inside 1 KB, so TAR is set again
    at each 1 KB boundary."""
    mv = memoryview(buf)
    for i in range(0, len(buf), 4):
        a = addr + i
        if i == 0 or (a & 0x3FF) == 0:
            ap_write(AP_TAR, a)
        ap_write(AP_DRW, mv[i] | (mv[i + 1] << 8) | (mv[i + 2] << 16)
                 | (mv[i + 3] << 24))


def send_card(black, red, verify=True):
    """Write the two card planes into the tag's RAM, then set REQ_FLAG so the
    tag displays the card. `black`/`red`: bytearrays of CARD_SIZE (5624)."""
    connect()
    # A refresh takes ~40 s and reads the planes from RAM: wait for a running
    # one to finish before overwriting them.
    for _ in range(70):
        if swd_mem_read(MARK) not in (30, 31):
            break
        time.sleep(1)
    else:
        raise SWDError("tag is still drawing the previous card")
    write_block(CARD_RAM_BLACK, black)
    write_block(CARD_RAM_RED, red)
    if verify:
        for plane, addr in ((black, CARD_RAM_BLACK), (red, CARD_RAM_RED)):
            for off in (0, len(plane) - 4):
                v = swd_mem_read(addr + off)
                if v != int.from_bytes(plane[off:off + 4], "little"):
                    raise SWDError("card write verification failed at 0x%X"
                                   % (addr + off))
    dout = swd_mem_read(PC_DOUT)
    if not dout & PIN_RST:
        swd_mem_write(PC_DOUT, dout | PIN_RST)   # release the panel reset
        time.sleep_ms(50)
    swd_mem_write(REQ_FLAG, 0xDEADBEEF)
    return True


def selftest():
    """Connect, print DPIDR, write/read a scratch word and restore it."""
    print("DPIDR: 0x%08X" % connect())
    print("MARK  0x20000000: 0x%08X" % swd_mem_read(0x20000000))
    print("REQ   0x%08X: 0x%08X" % (REQ_FLAG, swd_mem_read(REQ_FLAG)))
    old = swd_mem_read(SCRATCH)
    swd_mem_write(SCRATCH, 0xDEADBEEF)
    v = swd_mem_read(SCRATCH)
    swd_mem_write(SCRATCH, old)
    ok = v == 0xDEADBEEF
    print("RAM 0x%08X round-trip: 0x%08X %s" % (SCRATCH, v, "OK" if ok else "FAIL"))
    return ok
