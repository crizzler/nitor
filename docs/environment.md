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
| `liquidctl` on `PATH`                        | **not installed**                                   |
| `liquidctl` in repos                         | `extra/liquidctl 1.16.0-1` (also `cachyos-extra-v3`) |
| `/usr/lib/udev/rules.d/71-liquidctl.rules`   | absent                                              |
| `/etc/udev/rules.d/71-liquidctl.rules`       | absent                                              |
| `/dev/hidraw*` permissions                   | `crw------- root root` — **root-only**              |

**Consequence:** unprivileged HID access to the controllers is not possible yet, so the physical
LED milestone cannot be completed until `liquidctl` (which ships `71-liquidctl.rules`) is installed
by a user with sudo rights. Everything else in the project is developed against the mock backend,
which exercises the same code paths as the real backend.

Required hand-off command (one line, run by the user):

```bash
sudo pacman -S liquidctl
```
