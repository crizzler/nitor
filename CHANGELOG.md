# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Discovery of supported NZXT controllers through liquidctl, with the difference between "nothing
  plugged in" and "plugged in but not permitted" reported clearly.
- Lighting control for the LED channels each device actually exposes: colours, effects, animation
  speed, direction and channel selection.
- A colour picker with hue/saturation editing, hex entry, seven presets and multiple colour slots for
  effects that take more than one colour.
- Application-level brightness, which dims the colour sent to the hardware because these controllers
  have no brightness setting of their own.
- Settings in `~/.config/nitor/config.json` with schema versioning, migrations and atomic writes.
- Optional startup restoration through a `systemd --user` oneshot unit, enabled from the settings
  page. No root daemon, nothing resident.
- Diagnostics report that can be copied into an issue without leaking personal data.
- `--mock-device` for interface development without hardware, `--apply-saved` for login, and
  `--self-test` for a headless smoke test.
- Arch/CachyOS packaging: a release PKGBUILD and a `nitor-git` PKGBUILD, desktop entry, AppStream
  metadata and an icon set.

### Fixed

- The wheel contained no QML at all, so an installed Nitor could not open a window; `package-data`
  listed the icons and the desktop files but not the interface. This was only visible from an
  installation, because a source checkout loads the QML straight from the tree. `tests/test_packaging.py`
  now checks that every runtime file is covered by `package-data`, and CI installs the built package
  into a clean environment and runs the self-test against it rather than only testing the checkout.
- The startup unit now quotes values that contain whitespace. Without this, a checkout under a path
  such as `Other Projects/nitor` produced a unit whose `PYTHONPATH` was silently truncated by
  systemd, so login restoration could never import Nitor.
- The permission classifier recognises the failure liquidctl actually reports when no udev rule is
  installed (`The device has no langid (permission issue, ...)`). Previously that fell through to the
  generic USB branch and told the user to replug the controller instead of showing the udev rule.
- A refused device listing was reported as an empty one, so the permission message was immediately
  replaced by "No compatible NZXT controller found" and the udev advice disappeared. A failed
  listing now reports only the failure.
- The status line could show the bare word `not-found`, which is systemctl's answer for a unit that
  does not exist; those answers are translated now, and the autostart check no longer talks over an
  error, since it runs moments after discovery.
- Closing the window while a hardware call was in flight destroyed a running worker thread and
  aborted the process. Shutdown now waits for the call to finish, bounded by the backend's own
  subprocess timeout.
- The recovery card no longer shows a "no controller found" message at the same time as saying the
  controller was found but denied, and the udev instructions have one source instead of two.
- Three interface defects found by Qt 6's QML linter, which the Qt 5 binary that shadows it did not
  report: a status dot sized directly inside a layout it is managed by, cross-scope property access
  in the colour wheel, and typography read through a property the tooling cannot see. All 171
  warnings are resolved and CI now fails on any new one.
- The view model is passed to QML as an initial property instead of a context property, so the
  interface is statically checkable and delegates are compiled with explicit bound behaviour.

### Notes

- The controllers are now reached on real hardware: both NZXT devices are identified by name, their
  channels and accessories are reported (the RGB & Fan Controller exposes `led1`, `led2` and `sync`;
  the Kraken Z exposes `external` only), and a Gigabyte RGB board on the same machine is correctly
  reported as unsupported rather than offered fake controls.
- Applying a colour to real LEDs has **not** been confirmed by eye. The controllers accept the writes
  and `liquidctl` reports success, including through Nitor's own `--apply-saved` path, but the
  tested/untested table in [`docs/hardware-notes.md`](docs/hardware-notes.md) deliberately keeps
  "the device accepted the command" separate from "the LEDs lit up" until someone watches them.
  Persistence across a power cycle, and the `systemd --user` unit itself, are likewise still untested.

## [0.1.0] - 2026-09-16

Development milestone, not yet tagged as a release: the backend, interface and packaging are in
place, and the behaviour of the hardware path is documented rather than assumed. Nothing in this
entry claims a physical LED was observed — see the notes above for what is still outstanding.
- the interface is usable, themed by the desktop, and never blocks on hardware
- configuration persists and can be reapplied at login
