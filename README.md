# FG22-informer

[Русский](README.ru.md) · **English**

> This is a translation. The main version of this README is in Russian: [README.ru.md](README.ru.md). If the two differ, the Russian one is correct.

Custom firmware for FG22 modules with an e-paper screen, built on **Silicon Labs EFR32FG22** (Flex Gecko 2, Cortex-M33, 2.4 GHz radio), and instructions for flashing it with nothing but a **Raspberry Pi Pico** and three wires.

The path is the same for the whole family:

1. **Reset the chip.** The factory firmware is erased and debug access is opened.
2. **Flash the bootloader.**
3. **Flash the firmware**, compatible with [OpenEPaperLink](https://github.com/OpenEPaperLink) (OEPL): the tag goes on air over 802.15.4 by itself and fetches its image from an OEPL access point.

> **Status.** Reset and flash writing through the Pico are tested on hardware. The OEPL bootloader and firmware for these boards are **in development**: steps 5–6 describe how to flash them once the images appear in `firmware/`. For now a placeholder, `firmware/bootloader/stub.hex`, is flashed to test the chain.

## Chip

| | |
| --- | --- |
| Part number (OPN) | **EFR32FG22C121F512GM40** |
| Family | Silicon Labs EFR32 Flex Gecko 2 (FG22), Series 2 |
| Core | ARM Cortex-M33, up to 38.4 MHz |
| Flash | 512 KB, from address `0x00000000`, 8 KB pages |
| RAM | 32 KB, from address `0x20000000` |
| GPIO | 26 |
| Radio | 2.4 GHz, per the datasheet: proprietary protocols (Proprietary), up to +6 dBm |
| Package | QFN40, 5×5 mm, 10 pins per side |
| SWD | SWCLK — PA01 (pin 22), SWDIO — PA02 (pin 23) |
| Package marking | `FG22` / `C121G6` / lot code / date code. The date code is 4 digits in YYWW format: year and week of manufacture, e.g. `2150` — 2021, week 50. The full OPN is not printed on the package; `C121GG` on other boards is a different code from the same QFN40 line |
| Debug from the factory | usually locked (secure debug): flash can't be read and can only be opened by erasing (step 4) |
| DPIDR over SWD | `0x6BA02477` |

Datasheet: [docs/efr32fg22-datasheet.pdf](docs/efr32fg22-datasheet.pdf), original at [silabs.com](https://www.silabs.com/documents/public/data-sheets/efr32fg22-datasheet.pdf). QFN40 pin numbers follow its table 6.1 (pp. 70–71). The flash page size (8 KB) is not in the datasheet; it comes from the EFR32xG22 reference manual.

## Tested devices

| Device | Chip | Screen | Status |
| --- | --- | --- | --- |
| FG22 module with a 2.6" screen, battery powered | EFR32FG22C121F512GM40 (QFN40, 512 KB flash, 32 KB RAM), marking `FG22 / C121G6` | e-paper 2.66", 296×152, black / white / red | reset and flashing tested, screen pins found |

Other FG22 boards go through the same steps. What differs is the screen and power pinout and the exact chip part number (see "Another FG22 chip" below).

> **Don't flash ready-made OEPL images built for other boards** onto a "similar" device. They use different screen and power pins, and the panel can be left in a bad state. The firmware has to be built for your board.

## What you need

- **Raspberry Pi Pico or Pico W** — it becomes the debugger (SWD).
- **3 wires** (clock, data, ground) and a **4th** for 3.3 V power if the batteries are removed from the device.
- **Windows** and the tools in `tools/`. They are not in git; download and unpack them to these paths:

| What | Where | From |
| --- | --- | --- |
| debugprobe for Pico | `tools/debugprobe_on_pico.uf2` | [raspberrypi/debugprobe, releases](https://github.com/raspberrypi/debugprobe/releases) — the file `debugprobe_on_pico.uf2` (not `…pico2.uf2`) |
| OpenOCD 0.12.0-7 (xPack) | `tools/openocd/xpack-openocd-0.12.0-7/` | [xpack-dev-tools/openocd-xpack, releases](https://github.com/xpack-dev-tools/openocd-xpack/releases) |
| probe-rs | `tools/probe-rs/probe-rs.exe` | [probe-rs, releases](https://github.com/probe-rs/probe-rs/releases) |

## 1. Pico → debugger

1. Hold the **BOOTSEL** button on the Pico and plug in USB. A drive named **RPI-RP2** appears.
2. Drag `tools\debugprobe_on_pico.uf2` onto it. The Pico reboots as a CMSIS-DAP debugger.
3. On a Pico W the LED won't blink: that's normal.

## 2. Wiring

On the EFR32FG22 in QFN40 the SWD pins are **PA01 (SWCLK)** and **PA02 (SWDIO)**: pins 22 and 23. The device board usually has test pads wired to these pins. The pads on the edge of the Pico itself are its own SWD; don't connect to them.

| Chip signal | QFN40 pin | Pico | Wire (as we used) |
| --- | --- | --- | --- |
| PA01, SWCLK | 22 | GP2, pin 4 | green |
| PA02, SWDIO | 23 | GP3, pin 5 | yellow |
| GND (battery minus) | — | any GND: 3, 8, 13, 18, 23, 28, 33, 38 | black |
| 3.3 V power, **only with the batteries removed** | — | pin 36, `3V3` | red |
| RESETn, reset | 11 | not connected: briefly shorted to GND by hand in steps 3–5, see below | — |

Don't touch Pico pins 39 (`VSYS`) and 40 (`VBUS`): they carry 5 V. Chip pin diagram with photo: [docs/pins.md](docs/pins.md).

**Power from the Pico (red wire):** remove the batteries first — a CR2450 is not rechargeable, and the Pico would push 3.3 V into it. Connect **black (ground) first, then red (power)**. The Pico supplies enough current to talk to the chip over SWD. During a screen refresh the panel's converter may pull the 3.3 V down — that doesn't matter for reset and flashing.

### Pin 11 (RESETn): a short to ground, until the bootloader is written

Until the bootloader is fully written — that is, in steps 3 (link check), 4 (reset) and 5 (bootloader) — **briefly short pin 11, RESETn, to GND** and release it before each attempt: the chip restarts and the script connects right after it starts. Without this, connecting didn't work. Once the bootloader is written, you no longer need to touch pin 11: step 6 runs without it.

- **Where the pin is:** bottom edge of the package, first from the left, with the pin-1 dot at top left and the `FG22` text upright. Next to it is pin 14, the antenna — don't touch it.
- **What to short with:** a thin wire or needle from GND; touch pin 11 (or the trace leaving it) for a second and pull away. Per the datasheet RESETn is pulled up internally, so shorting it to ground is safe for the chip. **Don't hold** pin 11 at ground: while it is low the chip stays in reset, and neither erase nor writing will go through.
- **The red wire instead of pin 11.** If the device is powered from the Pico, you get the same reset by **breaking the red wire for a second and reconnecting it**: the chip restarts on power-up. Handy when pin 11 is hard to reach. This doesn't work on batteries.
- **When:** the scripts in steps 4 and 5 play a **beep** before each of their **5 attempts**. The beep is your cue: touch pin 11 with ground and release. The pin is tiny and hitting the right moment is hard, so there are five attempts, 5 s apart. The script stops after the first success.
- **In step 3** there is no beep and no retry: touch pin 11 with ground as you press Enter, then release. If it didn't work, run the command again.

## 3. Link check

```powershell
tools\probe-rs\probe-rs.exe list
```

The Pico should show up as `Debugprobe on Pico (CMSIS-DAP)`. If it doesn't, repeat step 1.

Chip response, without writing or erasing. As you run the command, briefly short pin 11 (RESETn) to GND (see step 2):

```powershell
tools\openocd\xpack-openocd-0.12.0-7\bin\openocd.exe -s tools\openocd\xpack-openocd-0.12.0-7\openocd\scripts -f tools\efr32_connect.cfg
```

If the output contains `STATE`, the link works. If not, repeat, hitting pin 11 at the moment you start it. If the chip stays silent or the log says `locked`, debug is locked by the factory firmware: go to step 4.

## 4. Chip reset (erase + unlock)

> ⚠️ **Irreversible.** All of main flash is erased together with the factory firmware. It almost certainly can't be read beforehand (secure debug), and it can't be restored afterwards. The device will stop working with the factory system.

```powershell
tools\erase-unlock.cmd
```

The script sends the official EFR32 Series 2 **device erase** command over DCI (`tools/efr32_dci.cfg`): it erases flash and opens debug access. It doesn't write anything itself. It makes up to 5 attempts, 5 s apart, and stops after `RESULT ERASE_OK`.

**At every beep**, briefly short pin 11 (RESETn) to GND and release it (see step 2).

If all attempts fail: check ground, device power and the wires, then run the script again and hit the beep.

## 5. Bootloader

The image is written with probe-rs, with verification:

```powershell
tools\flash-probe.cmd -Image firmware\bootloader\stub.hex
```

- **For now** `firmware/bootloader/` contains only `stub.hex`. It isn't a bootloader but a 16-byte placeholder (stack, interrupts disabled, endless loop): it checks that writing to flash works. It doesn't touch the screen or radio pins.
- **The OEPL bootloader** for these boards is in development. Once it appears in `firmware/bootloader/`, it is flashed with the same command, with its file in `-Image`.
- `flash-probe.cmd` takes **Intel HEX**. If your build produced `.s37` or `.elf`, convert it to hex: `tools\gcc\...\bin\arm-none-eabi-objcopy -O ihex in.elf out.hex`.
- A fallback without probe-rs, for `stub.hex` only, through the flash controller (MSC) in OpenOCD: `tools\flash-btl.cmd`.

Both scripts make up to 5 attempts and stop after a successful write. **At every beep**, briefly short pin 11 (RESETn) to GND, as in step 4. They don't unlock the chip and don't mass-erase flash.

## 6. Firmware

```powershell
tools\flash-probe.cmd -Image firmware\<path to image>.hex
```

You no longer need to short pin 11 (RESETn) here: the bootloader is written. The script still beeps before its attempts; you can ignore it.

- **The OEPL-compatible firmware is in development.** Once the image is available, its path will be here.
- After writing, the device restarts by itself. Disconnect the Pico and put the batteries back (if you powered it from the Pico, remove the red wire first).
- For the tag to receive images you need an **OEPL access point**: a separate ESP32-based device with its own 802.15.4 radio. A reflashed tag alone can't pull an image out of the air.

## Another FG22 chip

- **Reset** (step 4) is the same for all of EFR32 Series 2.
- **Writing** (`tools/flash-probe.ps1`) calls probe-rs with `--chip EFR32FG22C121F512`. For another FG22 variant (different flash size or package), put in its name. List: `tools\probe-rs\probe-rs.exe chip list | findstr FG22`.
- **SWD** in the QFN40 package is pins 22/23 (PA01/PA02). Other packages have other pin numbers, but the signals are the same: PA01 and PA02.
- **Map the screen and power pinout** for your own board. Other people's diagrams are only a hint.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `No debug probes were found` | The Pico isn't running debugprobe (e.g. it has MicroPython). Repeat step 1 |
| reset or bootloader write: all 5 attempts fail | Most often pin 11 missed the beep (RESETn → GND). Run again and touch right on the beep. If that doesn't help, check GND, SWCLK/SWDIO (not swapped?) and device power |
| flash-probe: write errors after reset | Run `tools\erase-unlock.cmd` again, then write |
| The chip answered, then stopped | The device batteries are flat. Power it from the Pico 3V3 with the batteries removed |

## Example without radio: weather over the same SWD

While the OEPL firmware is in development, the repository has a working example. A Pico W (running MicroPython instead of debugprobe) fetches the weather from wttr.in and a temperature from Home Assistant, draws a card and writes it over the SWD wires into the device's RAM. The device puts it on screen: at :00 and :30, at power-up and from a button on a web page. The whole demo is in [demo/](demo/): how it works and how to flash it — [demo/README.md](demo/README.md) (in Russian).

## Directories

| Path | Contents |
| --- | --- |
| `firmware/bootloader/` | bootloader (for now the `stub.hex` placeholder) |
| `demo/` | the weather example: Pico W firmware (`pico/`), informer firmware (`tag/`), MicroPython, scripts |
| `tools/` | reset, unlock and flashing scripts, OpenOCD configs |
| `docs/` | hardware, pinout, notes (in Russian) |
| `hardware/photos/` | photos of the tested unit |

Don't put factory firmware dumps in git: `dumps/` and `stock/` are in `.gitignore`. The Wi-Fi password and Home Assistant token live in `demo/pico/secrets.py`, which is in `.gitignore` too. Template: `secrets_example.py`.

No license has been chosen yet. If you build on OEPL: the OEPL tag firmware is distributed under CC BY-NC-SA 4.0 (non-commercial use only).
