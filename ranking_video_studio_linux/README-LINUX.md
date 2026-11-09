# LRBar-RankGen — Linux build

This folder is a **separate Linux port** of the app. The Windows project in
`../ranking_video_studio` is untouched and remains the source of truth for the
Windows build; both copies share the same key format, Machine ID layout and
Python licence verifier.

Everything here is source + build scripts. PyInstaller cannot cross-compile, so
the actual binary must be produced on a Linux machine (or Linux CI).

## Requirements

- Python 3.10+ (3.11/3.12 recommended)
- `python3 -venv` and `python3-dev`
- FFmpeg with `libx264` on `PATH` (bundled into the build)
- Cairo headers if `pycairo` has no wheel for your distro
- PyQt6 runtime libraries (usually already present on a desktop install)

Debian/Ubuntu example:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-dev build-essential \
    pkg-config libcairo2-dev ffmpeg \
    libgl1 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0
```

Fedora example:

```bash
sudo dnf install python3 python3-devel gcc pkg-config cairo-devel ffmpeg \
    mesa-libGL libxcb libxkbcommon-x11
```

## Run from source

```bash
cd ranking_video_studio_linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

On first launch the activation window appears and shows this computer's
Machine ID. Send that ID to the seller; paste the key you receive back into the
window. There is no online check — verification is fully offline.

The owner tool is the same Java key manager as on Windows:

```bash
cd ../licensing/java
./run.sh          # or: java -jar dist/LRBar-License-Manager.jar
```

It is an **owner-only** tool and must never be shipped to customers.

## Build the binary

```bash
cd ranking_video_studio_linux
source .venv/bin/activate
pip install pyinstaller
python build_linux.py
```

The script:

1. verifies it is running on Linux and that `ffmpeg` has `libx264`,
2. stages FFmpeg and the first-run seed content into `packaging/`,
3. runs PyInstaller from `LRBar-RankGen.spec`,
4. produces `dist/LRBar-RankGen` (one file, windowed).

Check the result headlessly:

```bash
./dist/LRBar-RankGen --selftest
```

The command prints a JSON report and exits non-zero if any check fails
(imports, bundled assets, licence verifier, FFmpeg, a 0.5 s test export).

## Install for the current user

```bash
bash linux/install.sh
```

This installs the binary under `~/.local/share/lrbar-rankgen`, symlinks
`~/.local/bin/lrbar-rankgen`, adds icons under
`~/.local/share/icons/hicolor/...` and writes a desktop entry to
`~/.local/share/applications/lrbar-rankgen.desktop`. No root is needed.

```bash
bash linux/install.sh --uninstall   # keeps projects and licence
```

If `~/.local/bin` is not on `PATH`, launch from the application menu or run
`~/.local/bin/lrbar-rankgen` directly.

## Where Linux keeps data

| What | Location |
| --- | --- |
| Projects, templates, settings | `${XDG_DATA_HOME:-~/.local/share}/LRBar-RankGen/` |
| Visible licence record | `${XDG_DATA_HOME:-~/.local/share}/LRBar-RankGen/license.json` |
| Sealed licence mirror | `${XDG_CONFIG_HOME:-~/.config}/LRBar-RankGen/license-state.json` |
| Machine ID source | `/etc/machine-id` (then `/var/lib/dbus/machine-id`, then the DMI product UUID) |

The second sealed copy exists so deleting `license.json` cannot reset a 1-Day
quota. Both copies are HMAC-sealed with a key derived from the Machine ID.

Because the Machine ID comes from `/etc/machine-id`, reinstalling the app,
changing the hostname or updating the kernel keeps the same ID. Reinstalling
the **operating system** generates a new ID, so a machine-bound key must then be
reissued by the owner.

## Tests

```bash
cd ranking_video_studio_linux
python -m unittest discover -s tests
```

The tests use `LRBAR_LICENSE_DIR` (temporary state directory) and
`LRBAR_LICENSE_NO_MIRROR=1` so they never touch your real licence.

## Packaging notes

- **AppImage / .deb / Flatpak** are possible next steps; `build_linux.py`
  currently produces the single binary and `linux/install.sh` handles the
  per-user install. Keep using `dist/LRBar-RankGen` as the payload for any
  future wrapper.
- Build on the **oldest** distro/glibc you intend to support. A binary built on
  a rolling-release distro will not start on older LTS systems.
- PyQt6 ships its own Qt libraries. On Wayland, Qt may use the `wayland` or
  `xcb` platform plugin; both are bundled. If a minimal system lacks X11
  libraries, install the `libxcb-*` packages listed above.
- FFmpeg is copied from `PATH` at build time. A distro build works but a
  static build (e.g. johnvansickle.com/ffmpeg) gives the most portable result.
- There is no code signing requirement on Linux. If you later distribute a
  `.deb`/Flatpak, add the appropriate repository/Flatpak metadata.

## Licence enforcement limits

Verification is client-side and offline: it stops casual key sharing and
tampering, but someone who patches the executable can bypass it. Revocation or
stronger enforcement would require an online activation service.

The private signing key (`../licensing/private_key.pem`) never ships with the
app. Only the public key is embedded in `utils/license_public_key.py`.
