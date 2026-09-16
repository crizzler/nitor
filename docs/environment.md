# Development environment record

Captured on the primary development machine (2026-09-16). This is the machine the project is
being written and tested against.

## Host

| Item                        | Value                                        |
| :-------------------------- | :------------------------------------------- |
| Distribution                | CachyOS Linux (`ID=cachyos`)                 |
| Desktop                     | KDE Plasma (Wayland session is the norm)     |
| Interactive shell           | fish                                         |
| Python                      | 3.14.7 (system)                               |
| PySide6                     | 6.11.2 (installed system-wide)               |
| pytest / ruff               | `/usr/bin/pytest`; ruff available            |
| qmllint                     | Qt 6 at `/usr/lib/qt6/bin/qmllint`; `/usr/bin/qmllint` is Qt 5's |
| makepkg                     | present                                      |

## Tooling preflight

| Check                       | Result                                                     |
| :-------------------------- | :--------------------------------------------------------- |
| `git config --get user.name`  | unset globally — repository-local identity used instead  |
| `git config --get user.email` | unset globally — repository-local identity used instead |
| `ssh -T git@github.com`     | authenticated (`Hi crizzler!`)                             |
| `gh` CLI                    | present and authenticated as **crizzler** (scopes: `gist`, `read:org`, `repo`) |
| `sudo -n true`              | **password required** — non-interactive privilege escalation is unavailable |

## Hardware

```
Bus 001 Device 007: ID 1e71:2010 NZXT NZXT USB Device
Bus 001 Device 009: ID 1e71:3008 NZXT NZXT KrakenZ Device
```

## Backend state

| Check                                        | Result                                              |
| :------------------------------------------- | :-------------------------------------------------- |
| `liquidctl` on `PATH`                        | **installed**: 1.16.0 (`liquidctl 1.16.0-1`)         |
| `liquidctl` in repos                         | `extra/liquidctl 1.16.0-1` (also `cachyos-extra-v3`) |
| `/usr/lib/udev/rules.d/71-liquidctl.rules`   | **present**, shipped by that package                |
| `/etc/udev/rules.d/71-liquidctl.rules`       | absent, and not needed                              |
| `/dev/hidraw*` permissions                   | granted to the console user by that rule             |

**Consequence:** the controllers are reachable without root, so the hardware steps can be run. This
was the blocker described earlier in this document, and it has since been removed by installing the
packaged `liquidctl`.

## Backend validation without root

While the controllers were still unreachable, the failure paths were validated without installing
anything system-wide: liquidctl 1.16.0 (the exact version in the repositories) was installed into a
throwaway virtual environment and Nitor was pointed at it by putting that environment's `bin`
directory first on `PATH`:

```bash
python3 -m venv /tmp/lcvenv
/tmp/lcvenv/bin/pip install liquidctl
PATH="/tmp/lcvenv/bin:$PATH" PYTHONPATH=src python -m nitor --diagnostics
```

What that did and did not establish:

- **Established:** Nitor detects the backend and reads its version (1.16.0) from real output, and
  classifies the real failure correctly. Without the udev rule, even `liquidctl list` fails, with
  `ValueError: The device has no langid (permission issue, no string descriptors supported or device
  error)`; Nitor reports "The controller was found, but Linux denied access to it" with the udev
  hint, and a regression test pins that verbatim string.
- **Not established:** anything about LEDs. Enumeration, `initialize` and every write require the
  udev rules, which need root to install. The device descriptions, channel names and effect tables
  therefore still come from upstream source rather than from this hardware.

Required hand-off command (one line, run by the user):

```bash
sudo pacman -S liquidctl
```
