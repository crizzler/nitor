# Troubleshooting

Most problems are one of four things. Check the status line at the bottom of the window first: it
says what happened in normal language, without asking you to read a traceback.

## "Lighting backend not installed"

Nitor talks to supported controllers through [liquidctl](https://github.com/liquidctl/liquidctl),
which is a separate program. Install it:

```bash
sudo pacman -S liquidctl
```

Nitor never runs `sudo` for you and never asks for your root password. Use **Check again** after
installing.

If you installed liquidctl with `pip` or in a virtual environment instead, the program works but its
udev rules are missing — see the next section.

## "The controller was found, but Linux denied access to it"

The device node exists but your user cannot write to it. Nitor tells this apart from *not plugged in*
because the two need completely different things from you, and the difference is visible in the
error text: a permission failure is reported, rather than "no hardware found".

If you run liquidctl by hand without the rules installed, the symptom is usually this, which does not
read like a permission problem at all:

```
$ liquidctl list
ValueError: The device has no langid (permission issue, no string descriptors supported or device error)
```

Nitor recognises that wording and shows this message instead.

`/dev/hidraw*` is normally owned by root. The liquidctl package ships a udev rule that grants access
to supported devices. Check whether it is present:

```bash
ls /usr/lib/udev/rules.d/71-liquidctl.rules /etc/udev/rules.d/71-liquidctl.rules
```

If it is missing, copy
[71-liquidctl.rules](https://github.com/liquidctl/liquidctl/blob/main/extra/linux/71-liquidctl.rules)
into `/etc/udev/rules.d/` and reload udev:

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then unplug and reconnect the controller, and choose **Check again**.

## "No compatible NZXT controller found"

1. Confirm the hardware is visible at all:

   ```bash
   lsusb | grep -iE "NZXT|1e71"
   ```

   Expected output for the controllers this project supports looks like:

   ```
   Bus 001 Device 007: ID 1e71:2010 NZXT NZXT USB Device
   Bus 001 Device 009: ID 1e71:3008 NZXT NZXT KrakenZ Device
   ```

2. Confirm liquidctl recognises it:

   ```bash
   liquidctl list
   ```

3. Check nothing else is holding the device open. OpenRGB and NZXT CAM both claim these
   controllers; only one program can talk to a device at a time.

## "No accessories detected on …"

The controller was initialised, but nothing answered on that channel. Check the LED strip or fan is
plugged into the channel you selected, and that it is on the same channel the device reports.

Note that the controller re-detects its accessories when it is initialised, which Nitor does at
start-up. After a power loss (switching the PSU off, not a normal shutdown) the controller forgets
its accessory list until it is initialised again, so choosing **Refresh** is worth trying.

## Effects or channels are missing

Nitor only offers what the hardware and liquidctl actually support. A few examples:

- A Kraken Z has exactly one controllable LED channel (`external`). Its pump face is a display, not
  an RGB ring, and Nitor does not control displays.
- The 2022 "3+6 channel" RGB & Fan Controller cannot have its LEDs controlled by liquidctl yet, so
  Nitor says so instead of showing controls that would do nothing.
- Some effects accept a single colour, some up to eight, and the `super-*` modes theoretically up to
  forty (one per LED). Nitor offers up to eight colour slots; per-LED editing is not implemented yet.

## Changes do not seem to apply

- Look at the status line. Nitor reports every hardware write, and every failure, there.
- Nitor debounces changes: it waits a fraction of a second after you stop changing something, so a
  colour-wheel drag becomes one write rather than fifty. **Apply now** skips that wait.
- If nothing happens at all, check the permission section above. Writes are what need permission;
  detection does not.

## Startup lighting does not come back after a reboot

```bash
systemctl --user status nitor.service
```

Common causes:

- The setting is off in **Settings**.
- The controller was unplugged when you logged in. Nitor treats "no controller connected" as
  nothing to do, not as a failure, so the service stays quiet in that case — the log line says so.
- The unit was written for a source checkout and the checkout has moved. Toggle the setting off and
  on again to rewrite it.

## Reporting a problem

**Settings → Copy diagnostics** produces a report containing versions, the detected USB ids, the
channels and the permission state. It deliberately contains no user names, host names, home
directories or serial numbers, so it is safe to paste into an issue.

Also useful, if you can:

```bash
lsusb | grep -iE "NZXT|1e71"
liquidctl list
liquidctl --match "RGB & Fan Controller" initialize
```

Please do not paste the output of `liquidctl --debug` without reading it first: it can include
device paths and other details.

## When Nitor refuses to do something

If you are reading this because the program refused a command, that is deliberate. Nitor sets LED
colours and nothing else. Commands that would touch pump speed, fan speed, fan or pump curves,
cooling modes, thermal thresholds, the LCD or firmware are rejected by the backend before any
process is started. See [`development-notes.md`](development-notes.md) for how that is enforced.
