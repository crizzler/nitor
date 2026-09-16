# Development notes

Decisions taken during discovery, and the reasoning behind them. Anything here is fair game to
revisit, but the reason for the original choice is recorded so the discussion can start from facts.

## Project name

**Chosen: `Nitor`.**

`nitor` is Latin (and Swedish/Danish/Norwegian) for *shine, brightness, brilliance, splendour* —
which is exactly what the application does, without borrowing anyone's trademark.

Requirements it satisfies:

- short (5 characters), lowercase, unambiguous to type and say
- independent of NZXT/HUE/Kraken branding — no implied affiliation
- not a "gaming" name and not childish
- absent from the AUR (checked via the AUR RPC API for `nitor`, `nitora`, `lucerna`, `lumora`,
  `fulgor`)
- no dominant software namesake. The nearest namesakes are a Nordic IT consultancy
  (*Nitor Creations*, which owns many GitHub repositories) and *NitorInc*, a Touhou fan project.
  Neither is a Linux lighting tool, so confusion risk is low.

Rejected candidates and why:

| Candidate   | Reason for rejection                                                                 |
| :---------- | :----------------------------------------------------------------------------------- |
| `Glint`     | 2,255 repository-name matches and several active projects (`typed-ember/glint`, `brigand/glint`, `TanklesXL/glint`, `general-works/Glint`) |
| `Lucerna`   | Crowded, including a Minecraft launcher, a libc implementation and a language project |
| `Lumen`     | Lumen (PHP framework), Lumen Technologies — significant conflict                     |
| `Prism`     | Prism Launcher, Prism.js                                                             |
| `Aurora`    | Aurora MySQL, Aurora Editor, and many others                                          |
| `Nyx`       | Tor's Nyx, NyxOS                                                                      |
| `HUE*`      | Philips Hue and NZXT HUE trademarks — deliberately avoided                            |
| `Nitora`    | Kept as a fallback; 18 repository matches, one being a small macOS brightness CLI     |

Derived identifiers: repository `nitor`, PyPI/package `nitor`, binary `nitor`,
config `~/.config/nitor/`, systemd user unit `nitor.service`,
AppStream/desktop ID `io.github.crizzler.Nitor`.

## Implementation stack

**Python 3.11+ with PySide6 and Qt Quick/QML** (no Kirigami requirement, no Electron, no embedded
web view).

- `pyside6` and `qqc2-desktop-style` are packaged for Arch/CachyOS, so the PKGBUILD needs no
  compilation step and the runtime cost is a single package dependency.
- Qt Quick Controls pick up the Plasma style (`qqc2-desktop-style`) automatically, which gives
  correct KDE light/dark appearance and system accent colours without hardcoding a palette.
- Kirigami is a C++/QML framework; using it from Python adds friction for no day-one benefit. It
  remains an option later if a specific control is worth it.
- C++/Qt 6 would shave some binary size, but roughly doubles the work for a utility of this size and
  makes casual contribution harder.

## Hardware backend

**Drive the `liquidctl` CLI as a subprocess; never import `liquidctl` into this process.**

- liquidctl is GPL-3.0-or-later. This project is MIT. Executing a program as a separate process is
  aggregation, not derivation, so the MIT licence stays valid and unambiguous. Importing the library
  into the same process would raise a combined-work question that a small project does not need.
- liquidctl's own README recommends the CLI *and* the Python API; the CLI is scriptable by design
  (non-zero exit codes, functional output on stdout, diagnostics on stderr, `--json` for
  `list`/`initialize`/`status`).
- Process start-up cost is real (roughly a few hundred milliseconds per call), so the UI never calls
  it synchronously: writes are debounced, coalesced and rate limited. See
  `src/nitor/services/scheduling.py`.
- If profiling ever shows this is not good enough, the fallback is a long-lived helper process that
  imports liquidctl (faster, but reopens the licence question) rather than writing HID packets
  ourselves.

## What the hardware actually supports

Recorded in full in [`hardware-notes.md`](hardware-notes.md). Two consequences shaped the UI:

1. **Brightness is not a device feature here.** liquidctl exposes no brightness command for HUE 2 or
   Kraken lighting channels, so `Nitor` implements brightness as dimming of the RGB values it sends.
   The UI says so plainly instead of pretending a device register exists.
2. **The Kraken Z has exactly one controllable LED channel** (`external`, for a HUE 2 chain). Its
   pump face is an LCD, and the `ring`/`logo` channels exist only on the X models. The UI shows no
   pump-LED controls on `1e71:3008` because the hardware does not have them.

## Cooling safety boundary

The application never touches pump speed, fan speed, fan/pump curves or firmware. This is enforced
in code rather than by convention: `src/nitor/backend/liquidctl_cli.py` is the only module that
starts a liquidctl process, and it validates every argv against a lighting-only grammar before
executing. `set fan1 speed 90`, `set pump speed 90`, `initialize --unsafe` and anything mentioning
firmware raise `SafetyViolationError`. `tests/test_safety_allowlist.py` asserts this.

## Deliberately out of scope for 0.1.0

Tray icon, per-LED `super-*` editors (the domain model supports them; there is no UI yet), Flatpak,
AppImage, AUR publication, OpenRGB integration, and every item on the project's out-of-scope list
(pump/fan/cooling, motherboard/GPU/RAM/keyboard/mouse RGB, other vendors, firmware, accounts,
telemetry).
