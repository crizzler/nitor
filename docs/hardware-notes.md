# NZXT hardware notes

Everything in this document was read from the upstream `liquidctl` source and documentation
(version 1.16.0), not guessed. It is the reference the backend's capability model is built from.

Legend: **Verified upstream** means it is stated in the driver source or device guide.
**Tested here** means it has been exercised on this machine's physical hardware.

## Devices on the development machine

```
Bus 001 Device 007: ID 1e71:2010 NZXT NZXT USB Device
Bus 001 Device 009: ID 1e71:3008 NZXT NZXT KrakenZ Device
```

| USB ID       | liquidctl description             | Driver class                            | Status here   |
| :----------- | :-------------------------------- | :-------------------------------------- | :------------ |
| `1e71:2010`  | NZXT RGB & Fan Controller         | `liquidctl.driver.smart_device.SmartDevice2` | Detected, not yet tested |
| `1e71:3008`  | NZXT Kraken Z (Z53, Z63 or Z73)   | `liquidctl.driver.kraken3.KrakenZ3`     | Detected, not yet tested |

Minimum liquidctl versions: 1.11.1 for the RGB & Fan Controller, 1.14.0 for the Kraken Z.
The installed/packaged version on CachyOS is 1.16.0, which satisfies both.

## Lighting channels

| Device      | LED channels                       | Fan/pump channels (ignored by Nitor) |
| :---------- | :--------------------------------- | :----------------------------------- |
| `1e71:2010` | `led1`, `led2`, plus `sync`        | `fan1`, `fan2`, `fan3`                 |
| `1e71:3008` | `external` only                    | `pump`, `fan`                          |

**Verified upstream.**

- On the RGB & Fan Controller each `ledN` drives one physical ARGB header, with up to 6 accessories
  and 40 LEDs per channel. `sync` applies one effect to all channels at once.
- The Kraken Z's `external` channel is a HUE 2 header on the pump breakout. The **`ring` and `logo`
  channels do not exist on Z models** — those describe the X models' infinity mirror, which the Z
  replaced with an LCD. Consequently `Nitor` shows only `external` on a Kraken Z.
- LED accessory detection happens during `initialize`: liquidctl reports firmware version and, per
  channel, which accessories are connected (for example `HUE 2 LED Strip 300 mm`, `AER RGB 2 140 mm`,
  `Pump Logo LEDs`). `Nitor` uses this to decide which channels are meaningfully controllable rather
  than assuming every channel has something attached.

## Out of scope on this hardware (deliberate)

- **Kraken LCD** (`liquidctl set lcd screen …`): brightness, orientation, static images, GIFs. The
  project exists to control LED lighting, so LCD content is excluded. Documented here because the
  Kraken Z's pump face *is* an LCD, which is the single most confusing part of this hardware.
- **Fan and pump control**: liquidctl can set `pump`/`fan` duty and curves on both devices. `Nitor`
  does not, ever. See the cooling safety boundary in `development-notes.md`.
- Kraken 2023/2024 models expose *no* colour channels in liquidctl (`color_channels = {}`), so they
  cannot be supported for lighting today.

## Permissions

**Verified upstream:** lighting writes go straight to the HID device (`_write_colors()`), even when
the in-kernel `nzxt-smart2` (Smart Device V2 / RGB & Fan Controller, Linux ≥ 5.17) or
`nzxt-kraken3` (liquidtux) drivers are bound. Those kernel drivers only provide *status* and fan
duty through hwmon, so LED control is unaffected by them but still needs raw HID access.

**Verified here:** `/dev/hidraw*` nodes on this machine are `crw------- root root` and no
`71-liquidctl.rules` is installed, therefore unprivileged LED writes are impossible until the udev
rules from the `liquidctl` package are present.

`Nitor` detects this situation and reports it distinctly from "no hardware found".

**Also verified here (liquidctl 1.16.0, still without a udev rule):** *enumeration* fails too, because
reading the USB string descriptors needs the same access that LED writes do: 

```
$ liquidctl list --json
ValueError: The device has no langid (permission issue, no string descriptors supported or device error)
```

So the design cannot assume a privilege-free "list" step: before the rules are installed there is no
way to read even the product strings, and `Nitor` reports the permission problem (with the udev
instructions) rather than claiming no hardware is present. `classify_failure` keys off the
`permission issue` and `no langid` wording for exactly this reason, and a regression test pins that
verbatim output.

Once the rules are installed:

- `list` enumerates devices and reports product strings without privileges.
- `Nitor` additionally checks read/write access to the `address` field reported for each device (for
example `/dev/hidraw5`) to decide between "connected" and "connected but access denied".

## Effects

Colour-count limits and speed support below come from `_COLOR_MODES` in both drivers.

| Effect                        | Colours | Speed | Direction | RGB & Fan Controller | Kraken Z |
| :---------------------------- | :-----: | :---: | :-------: | :------------------: | :------: |
| `off`                         | 0       | no    | no        | ✓ | ✓ |
| `fixed`                       | 1       | no    | no        | ✓ | ✓ |
| `super-fixed`                 | 1–40    | no    | no        | ✓ | ✓ |
| `fading`                      | 1–8     | yes   | no        | ✓ | ✓ |
| `spectrum-wave`               | 0       | yes   | yes       | ✓ | ✓ |
| `marquee-3` … `marquee-6`     | 1       | yes   | yes       | ✓ | ✓ |
| `covering-marquee`            | 1–8     | yes   | yes       | ✓ | ✓ |
| `alternating-3` … `-6`        | 2       | yes   | no        | ✓ | ✓ |
| `moving-alternating-3` … `-6` | 2       | yes   | yes       | ✓ | ✓ |
| `pulse`                       | 1–8     | yes   | no        | ✓ | ✓ |
| `breathing`                   | 1–8     | yes   | no        | ✓ | ✓ |
| `super-breathing`             | 1–40    | yes   | no        | ✓ | ✓ |
| `candle`                      | 1       | no    | no        | ✓ | ✓ |
| `starry-night`                | 1       | yes   | no        | ✓ | ✓ |
| `rainbow-flow`                | 0       | yes   | yes       | ✓ | ✓ |
| `super-rainbow`               | 0       | yes   | yes       | ✓ | ✓ |
| `rainbow-pulse`               | 0       | yes   | yes       | ✓ | ✓ |
| `wings`                       | 1       | yes   | no        | ✓ | ✓ |
| `loading`                     | 1       | yes   | no        | — | ✓ |
| `tai-chi`                     | 1–2     | yes   | no        | — | ✓ |
| `water-cooler`                | 2       | yes   | no        | — | ✓ |

Speed values accepted by the device firmware: `slowest`, `slower`, `normal`, `faster`, `fastest`.
Direction: `forward`, `backward`. Upstream also keeps deprecated `backwards-*` effect names for
compatibility; `Nitor` uses the modern `--direction backward` form and does not offer the deprecated
names.

Only effects listed for the selected device are offered in the UI, and the colour picker shows
exactly the number of slots the selected effect accepts.

## Tested status

| Item                                                    | State |
| :------------------------------------------------------ | :---- |
| Backend version detection                               | **Verified** on this machine with liquidctl 1.16.0 (the version Arch ships) |
| Device enumeration and product strings                  | Attempted here: enumeration is refused until the udev rule exists, so the product strings remain unverified. Descriptions and drivers come from upstream source |
| Permission failure detected and explained               | **Verified** here: `liquidctl list` fails with the `no langid` error and Nitor reports "connected but access denied" with the udev hint |
| Channel list and accessory detection via `initialize`    | Not yet run — blocked on the udev rules |
| Setting a fixed colour on `led1` / `led2` / `sync`       | Not yet tested — blocked on the udev rules |
| Setting a fixed colour on the Kraken `external` channel  | Not yet tested — blocked on the udev rules |
| Lighting persistence across S5/reboot                   | Not yet tested (upstream states settings persist while the device keeps power) |
| Unprivileged writes after udev rules                    | Not yet tested |

This table is updated as soon as the hardware step in the checklist below is completed. Nothing is
advertised as tested until it has actually been observed.

## Hardware verification checklist

Run with `liquidctl` installed (the udev rules arrive with that package):

```bash
liquidctl list
liquidctl --match "RGB & Fan Controller" initialize
liquidctl --match "RGB & Fan Controller" set led1 color fixed 00aaff
liquidctl --match "RGB & Fan Controller" set led1 color off
liquidctl --match "Kraken" initialize
liquidctl --match "Kraken" set external color fixed 00aaff
```

Record for each command: which physical LED zone changed, whether the command needed `sudo`, and
whether the setting survived a power cycle. `Nitor` itself can perform the same steps from its UI.
