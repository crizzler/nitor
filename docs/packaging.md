# Packaging

Primary target: **Arch Linux and CachyOS**. Anything else is future work.

## Building from trunk

There is no tagged release yet, so use the VCS package:

```bash
git clone https://github.com/crizzler/nitor
cd nitor/packaging/arch/nitor-git
makepkg -si
```

That installs `nitor-git`, which:

- builds a wheel from the checkout with `python -m build --wheel --no-isolation`
- runs the test suite as a `check()` step
- installs the console script, the package, the desktop entry, the AppStream metadata, the hicolor
  icons (16px through 512px plus a scalable SVG) and a ready-to-use `systemd --user` unit

`liquidctl` is a hard dependency, because without it Nitor cannot reach any hardware. It is also
what provides the udev rules that grant unprivileged access to the controllers.

`qqc2-desktop-style` is an optional dependency: it supplies the Plasma look and feel for Qt Quick
Controls. Plasma installs it already; without it Nitor falls back to Qt's default style.

## Building a release package

`packaging/arch/nitor/PKGBUILD` builds the tagged release tarball. Its checksum is intentionally
`SKIP` until a tag exists:

```bash
# after tagging v0.1.0 on GitHub
cd packaging/arch/nitor
updpkgsums          # fills sha256sums from pacman-contrib
makepkg --printsrcinfo > .SRCINFO
makepkg -si
```

`.SRCINFO` is generated, not committed, because it must match the final checksums.

## Layout

One directory per package, which is what the AUR expects and what PKGBUILD scanners require in
order to inspect everything next to a PKGBUILD:

```
packaging/arch/
├── nitor/       release package, source is the tagged tarball
└── nitor-git/   development package, source is the git repository
```

## If a PKGBUILD scanner blocks the build

Tools that audit PKGBUILDs will flag two things here, both correctly and both unavoidable:

- the release package's `sha256sums=('SKIP')`, because the tarball does not exist until a tag is
  pushed
- the VCS package's `sha256sums=('SKIP')`, because a moving branch cannot be checksummed

Neither is a defect, but a scanner may refuse to build. In that case install without building a
package, using a virtual environment that borrows the system Qt:

```bash
git clone https://github.com/crizzler/nitor
cd nitor
python -m venv --system-site-packages ~/.local/share/nitor/venv
~/.local/share/nitor/venv/bin/pip install --no-deps .
```

The console script then lives in `~/.local/share/nitor/venv/bin/nitor`. `--no-deps` is deliberate:
PySide6 comes from the system package, and `liquidctl` stays the distribution's job so that its udev
rules are installed in the normal place.

A virtual environment is not on `PATH`, and installing the package that way does not put anything in
`~/.local/share/applications` either, so add the two pieces of desktop integration by hand:

```bash
# Let the desktop entry's `Exec=nitor` and your shell find it
ln -sf ~/.local/share/nitor/venv/bin/nitor ~/.local/bin/nitor

# Launcher entry, AppStream metadata and icons, from a checkout
install -Dm644 src/nitor/data/io.github.crizzler.Nitor.desktop \
  ~/.local/share/applications/io.github.crizzler.Nitor.desktop
install -Dm644 src/nitor/data/io.github.crizzler.Nitor.metainfo.xml \
  ~/.local/share/metainfo/io.github.crizzler.Nitor.metainfo.xml
cp -r src/nitor/assets/icons/hicolor ~/.local/share/icons/
install -Dm644 src/nitor/assets/icon.svg \
  ~/.local/share/icons/hicolor/scalable/apps/io.github.crizzler.Nitor.svg

# Let KDE notice, and check the entry is well-formed
desktop-file-validate ~/.local/share/applications/io.github.crizzler.Nitor.desktop
update-desktop-database ~/.local/share/applications
kbuildsycoca6 --noincremental
```

Omitting the icon copy is the usual reason a userspace install shows a generic question-mark icon in
the launcher: the desktop entry names `io.github.crizzler.Nitor`, so that is the file name the icon
theme looks for.

## Publishing to the AUR

**Not done, and not to be done without an explicit instruction.** When the time comes:

1. Tag a release and push the tag.
2. Fill in `sha256sums` with `updpkgsums`.
3. Generate `.SRCINFO` and push only `PKGBUILD` and `.SRCINFO` to a new `nitor` AUR repository.
4. Publish `packaging/arch/nitor-git/PKGBUILD` separately as `nitor-git`.

## What gets installed

| Path | Contents |
| :--- | :--- |
| `/usr/bin/nitor` | Console script entry point |
| `/usr/lib/python3.*/site-packages/nitor/` | Python package, QML interface, icons, unit template |
| `/usr/share/applications/io.github.crizzler.Nitor.desktop` | Launcher entry |
| `/usr/share/metainfo/io.github.crizzler.Nitor.metainfo.xml` | AppStream metadata |
| `/usr/share/icons/hicolor/*/apps/io.github.crizzler.Nitor.{png,svg}` | Icons |
| `/usr/lib/systemd/user/nitor.service` | User unit for startup restoration |
| `/usr/share/licenses/nitor/LICENSE` | Licence |
| `/usr/share/doc/nitor/` | Documentation |

The application writes its own copy of the unit to `~/.config/systemd/user/nitor.service` when the
startup setting is enabled, so a user unit always takes precedence over the packaged one. That copy
is what exists when Nitor is run from a source checkout, where `ExecStart` must point at the
checkout's interpreter.

## Verifying a built package

```bash
namcap PKGBUILD
namcap nitor-0.1.0-1-any.pkg.tar.zst
```

CI also validates both PKGBUILDs with `makepkg --printsrcinfo` inside an `archlinux:latest`
container, and lints every QML file with `qmllint`.

## Future distributions

Flatpak and AppImage are deliberately not attempted yet: the first working CachyOS/Arch release
comes first. The architecture does not stand in the way — the application is a normal PySide6 program
that talks to a separate `liquidctl` process, so the main work for either format is bundling Qt and
deciding how the sandbox reaches `/dev/hidraw*`.
