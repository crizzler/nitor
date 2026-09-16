# Contributing

Thanks for considering it. This is a small project with a deliberately narrow scope, and the most
useful contributions are hardware reports, honest bug reports and small, focused changes.

## Scope

**In scope:** controlling NZXT LED lighting on Linux — colours, effects, channels, per-device
capabilities, persistence and startup restoration.

**Out of scope**, and not up for debate in a pull request: pump speed, pump and fan curves, fan
control, cooling modes, thermal thresholds, firmware updates, the Kraken LCD, motherboard/GPU/RAM or
peripheral RGB, other vendors' hardware, accounts, telemetry and cloud services.

The cooling boundary is not documentation, it is code: `src/nitor/backend/commands.py` validates
every command before a process is started. Changes that would widen it will be declined.

## Getting started

```bash
git clone https://github.com/crizzler/nitor
cd nitor

# Run it against a fake controller; no hardware and no permissions needed
PYTHONPATH=src python -m nitor --mock-device

# Tests (no hardware required)
PYTHONPATH=src pytest

# Lint and formatting
ruff check .
ruff format --check .

# QML (Qt 6's linter; -W0 makes any warning an error)
find src -name '*.qml' -exec qmllint -W0 {} \;
```

Use Qt 6's `qmllint`, not Qt 5's. On Arch and CachyOS the Qt 6 binary is
`/usr/lib/qt6/bin/qmllint` while `/usr/bin/qmllint` still belongs to Qt 5 (`qt5-declarative`), and the
Qt 5 linter will happily report nothing while missing real problems.

`ruff` and `pytest` are the only development dependencies. Install them with
`python -m pip install --user pytest ruff` or your distribution's packages.

If you have a real controller, please also read [`docs/hardware-notes.md`](docs/hardware-notes.md)
and help fill in the tested/untested table.

## How the code is organised

```
src/nitor/
├── domain/     pure logic: colours, effects, capabilities, errors. No Qt, no system calls
├── backend/    the hardware contract, the liquidctl backend, a mock backend, and the safety gate
├── services/   settings, write scheduling, diagnostics, startup restoration
├── ui/         QML interface and the view model that exposes the rest to it
├── app.py      window bootstrap
└── cli.py      argument parsing and the headless paths
```

Three rules keep this maintainable, and pull requests are expected to respect them:

1. **The domain stays pure.** No Qt, no I/O, no subprocess. It is what makes the test suite fast and
   exhaustive.
2. **The interface never waits for hardware.** Everything that touches a device goes through the
   worker thread in `ui/viewmodel.py`, and writes are debounced and coalesced by
   `services/scheduling.py`.
3. **Nothing but `backend/liquidctl_cli.py` starts a liquidctl process**, and it validates every
   command line first. `services/autostart.py` is the only other module that runs a program
   (`systemctl`), and it is isolated for the same reason.

## Tests

Tests must not need hardware, a display or root. Use `MockBackend`, and inject clocks and process
runners rather than sleeping or shelling out: `tests/test_scheduling.py` and
`tests/test_liquidctl_backend.py` show both patterns.

If you add behaviour, add a test that fails without it. If you fix a bug, add the test that would
have caught it.

## Commits and pull requests

Conventional commit subjects (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`) with a body
that explains *why* rather than restating the diff. Keep a pull request to one logical change.

Please make sure `ruff check .`, `ruff format --check .` and `pytest` are clean before opening a pull
request; CI runs exactly those, plus `qmllint` and PKGBUILD validation on Arch.

## Reporting hardware behaviour

The hardware support issue template asks for:

```bash
lsusb | grep -iE "NZXT|1e71"
liquidctl list
liquidctl initialize
```

plus Nitor's own diagnostics report (**Settings → Copy diagnostics**). Together those say which model
you have, which liquidctl version sees it, which LED channels exist and whether Nitor is allowed to
write to them. Please state plainly whether something was actually tested on the hardware or only
expected to work; the documentation distinguishes the two, and it should stay that way.

## Licence

Contributions are accepted under the MIT licence, the same as the project. By opening a pull request
you confirm you have the right to submit the work under those terms.
