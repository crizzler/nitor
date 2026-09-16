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

### Notes

- Physical LED output has not yet been verified on the development hardware because `liquidctl` and
  its udev rules are not installed on that machine yet. The tested/untested table in
  [`docs/hardware-notes.md`](docs/hardware-notes.md) states exactly what has and has not been
  observed, and it is kept honest until the hardware step is completed.

## [0.1.0] - 2026-09-16

Development milestone, not yet tagged as a release:

- supported controllers are detected
- fixed colours can be applied to a real LED channel
- the interface is usable, themed by the desktop, and never blocks on hardware
- configuration persists and can be reapplied at login
