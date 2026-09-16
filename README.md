<h1 align="center">Nitor</h1>

<p align="center">
  Simple, reliable control of NZXT RGB/LED lighting on Linux — without NZXT CAM.
</p>

<p align="center">
  <em>nitor</em> — Latin: shine, brightness, brilliance.
</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Platform: Linux" src="https://img.shields.io/badge/platform-Linux-informational.svg">
  <img alt="Built with Qt 6 and QML" src="https://img.shields.io/badge/UI-Qt%206%20%2F%20QML-41cd52.svg">
</p>

<!-- Screenshots are added once the lighting page is confirmed against real hardware. -->

## What this is

`Nitor` is a small, native Linux desktop application for controlling **NZXT LED lighting** and
nothing else. It detects supported controllers, shows what the hardware can actually do, and lets you
set a colour, an effect and a channel. That is the whole program.

It is built for CachyOS / Arch with KDE Plasma on Wayland, and it uses the system theme: no
hardcoded neon gradients, no embedded web page, no vendor account.

## What this is not

`Nitor` is not NZXT CAM for Linux, not an OpenRGB replacement, not a monitoring suite and not a fan
controller. It deliberately does **not** touch:

pump speed · pump curves · fan speed · fan curves · cooling modes · thermal thresholds · firmware ·
the Kraken LCD · motherboard, GPU or RAM RGB · keyboards · mice · other vendors' lighting ·
overclocking · telemetry · accounts · cloud services

The cooling boundary is enforced in code, not just documented: every command sent to the hardware
backend is checked against a lighting-only allowlist before it runs.

## Hardware support

| Device                             | USB ID       | Lighting channels        | State |
| :--------------------------------- | :----------- | :----------------------- | :---- |
| NZXT RGB & Fan Controller          | `1e71:2010`  | `led1`, `led2`, `sync`   | Detected, hardware verification pending |
| NZXT Kraken Z53 / Z63 / Z73        | `1e71:3008`  | `external` (HUE 2 chain) | Detected, hardware verification pending |

`Tested` is only claimed once a device has physically been driven by this project. See
[`docs/hardware-notes.md`](docs/hardware-notes.md) for the current, honest status table along with
everything else that was read from the upstream drivers.

On a Kraken Z, the pump face is an LCD rather than an RGB ring, so the only controllable LEDs are the
ones on the `external` HUE 2 header — and the LCD itself is out of scope.

## Installation (CachyOS / Arch)

`Nitor` talks to the hardware through [`liquidctl`](https://github.com/liquidctl/liquidctl), which
ships the udev rules that grant unprivileged access to the controllers:

```bash
sudo pacman -S liquidctl
```

Then install `Nitor` from the packaging directory in this repository:

```bash
git clone https://github.com/crizzler/nitor
cd nitor/packaging/arch
makepkg -si
```

`makepkg` is used rather than a published AUR package: this project is not on the AUR yet.

### Running from a source checkout

```bash
git clone https://github.com/crizzler/nitor
cd nitor
PYTHONPATH=src python -m nitor
```

There is a development mode that never touches USB devices, for UI work on machines without the
hardware:

```bash
PYTHONPATH=src python -m nitor --mock-device
```

## Usage

1. Launch `Nitor` from the application launcher.
2. If a compatible controller is connected, it is selected automatically.
3. Pick a channel, an effect and a colour. Changes are applied as you go.

Only effects the selected controller supports are offered, and the number of colour slots follows
the chosen effect. If a channel has no accessories detected on it, `Nitor` says so instead of
pretending to control it.

**Brightness** dims the colour `Nitor` sends. Neither the HUE 2 protocol nor the Kraken drivers expose
a device-level brightness setting for these channels, so this is honest software dimming rather than
a hardware register.

## Startup restoration

Settings can be reapplied automatically at login without leaving the window open. Enable
*Apply my lighting settings when I log in* in Settings; `Nitor` installs a `systemd --user` unit and
enables it:

```bash
systemctl --user status nitor.service
```

No root daemon is involved, and nothing runs in the background afterwards — the unit is a one-shot
that applies the saved lighting and exits.

## Troubleshooting

**"Lighting backend not installed"** — install liquidctl: `sudo pacman -S liquidctl`. `Nitor` will
never run `sudo` for you or ask for your root password.

**"controller detected, but Linux denied access"** — the udev rules are missing. They are part of the
liquidctl package; if you installed liquidctl another way (pip, venv), install
[`71-liquidctl.rules`](https://github.com/liquidctl/liquidctl/blob/main/extra/linux/71-liquidctl.rules)
into `/etc/udev/rules.d/` and reload:

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

**No compatible hardware found** — check that the controller shows up in `lsusb | grep -iE "NZXT|1e71"`
and that nothing else (for example OpenRGB) is holding the device open.

**Something else** — Settings → Diagnostics → *Copy diagnostics* produces a report with versions,
detected USB IDs, channels and permission status but no usernames, hostnames or serial numbers. That
is the right thing to paste into an issue.

## Development

```bash
git clone https://github.com/crizzler/nitor
cd nitor

# Run the test suite (no hardware required)
PYTHONPATH=src pytest

# Lint and format check
ruff check . && ruff format --check .

# Run against a fake device
PYTHONPATH=src python -m nitor --mock-device

# Check the QML
qmllint src/nitor/ui/**/*.qml
```

Useful flags: `--verbose` for structured debug logging, `--backend mock|liquidctl` to force a backend,
`--self-test` for a headless smoke test, `--apply-saved` for the headless startup path.

The architecture keeps three layers apart — QML user interface, application services, and a hardware
backend behind a narrow interface — so that everything except the backend is testable without a
controller plugged in. See [`docs/development-notes.md`](docs/development-notes.md) for the design
decisions and [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to help.

## License

MIT — see [`LICENSE`](LICENSE).

## Non-affiliation

This project is **not affiliated with, endorsed by, or supported by NZXT**. NZXT, Kraken and HUE are
trademarks of their respective owners and are used here only to describe hardware compatibility.
