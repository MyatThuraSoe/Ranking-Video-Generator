# License keys (Machine ID)

The app refuses to open until a valid key for the current computer has been
activated. Keys are Ed25519-signed tokens. The **public** key is compiled into
the app; the **private** key in this folder signs keys and must never be
shipped or committed.

## One-time setup (already done)

`python licensing/keygen.py` created:

| File | Purpose | Keep secret? |
| --- | --- | --- |
| `licensing/private_key.pem` | signs license keys | **YES — back it up offline** |
| `ranking_video_studio/utils/license_public_key.py` | verifies keys in the app | no (shipped) |

If you lose `private_key.pem` you cannot issue keys for the shipped build. If
it leaks, anyone can generate keys. Back it up in a password manager or
encrypted drive. `keygen.py --force` rotates the pair but invalidates every
already-issued license.

## Issue a key — Java GUI

Double-click **`Run License Manager.bat`**. The first launch compiles the Java
app automatically (a console window appears briefly); later launches open
immediately. Java 17 or newer is required — this machine has Java 23.

The window has two tabs:

### Generate Key

| Field | Notes |
| --- | --- |
| Account name | optional — customer or business name |
| Machine ID | **required** — 20 hex characters from the customer's activation window |
| Phone number | optional — WhatsApp / phone |
| Note | optional — order details, platform, etc. |
| License type | **1-Day** (24 h, 2 video exports) or **Lifetime** (unlimited) |
| Validity | for 1-Day keys: number of days and video exports (default 1 / 2) |

Click **Generate License Key**, then **Copy Key** and send the whole line to
the customer. **Save as .txt…** writes the key to a file if you prefer.

The Machine ID is normalized automatically, so a pasted
`e09f18a54b04478f6b8f` becomes `E09F-18A5-4B04-478F-6B8F`. The expiry clock
starts when you click Generate, so create the key right before sending it.
On a small screen the tab scrolls, and after generating the window scrolls
straight to the key card.

### History / Records

Every generated key is saved automatically with its generation time, account,
Machine ID, phone, note, type, expiry and full key. The tab supports:

* search/filter across all fields,
* **Copy Key** for the selected record,
* **Details…** (or double-click a row) to see the full key,
* **Delete** to remove a history entry (the key itself keeps working),
* **Export CSV…** for a spreadsheet/backup.

Records live in **`licensing/license_records.json`** (gitignored). Back it up
together with the private key — it is your sales record, not part of the app.
The file is plain JSON (not encrypted), so keep the `licensing` folder private
and never ship it inside the app installer.

## Rebuilding after editing the Java app

```bat
cd licensing\java
build.bat
```

That produces `licensing\java\dist\LRBar-License-Manager.jar`; the launcher
runs it with `javaw`. The app finds `private_key.pem` by walking up from the
jar, so it works no matter which folder you start it from.

## CLI fallback (Python)

The Python CLI still works and writes its own sales log
(`licensing/issued_keys.csv`). It is useful for scripts or if Java is not
installed:

```bat
..\.venv\Scripts\python.exe issue_license.py --machine 7F3A-9C2E-1B44-D07A-55C1 --type day
..\.venv\Scripts\python.exe issue_license.py --machine 7F3A-9C2E-1B44-D07A-55C1 --type lifetime
```

The Java GUI is the recommended tool because it keeps the customer details and
generation time in one searchable history.

## License types

| Type | Validity | Video exports |
| --- | --- | --- |
| `day` (1-Day) | 24 hours **from the moment the key is generated** | 2 |
| `lifetime` | never expires | unlimited |

The 24-hour window is signed into the key, so generate it right before you
send it.

## How enforcement works

* The key payload is bound to the customer's Machine ID. A key copied to
  another computer is rejected (the error shows both Machine IDs).
* Ed25519 signature verification means a key cannot be edited (type, expiry or
  video limit) without the private key.
* `license.json` in `%APPDATA%\LRBar-RankGen` stores the active key and the
  trial video counter. A sealed mirror is kept in
  `HKCU\Software\LRBar\RankGen`, so deleting the file does not restore used
  exports.
* The export counter is consumed when an export starts. If an export fails or
  is cancelled, that attempt still counts — this prevents restarting the app
  to get free attempts.
* Changing the machine ID (Windows reinstall, new PC) invalidates the key;
  issue a new one. Customers can see their current Machine ID in the
  **License** button / **File → License…** window.

## Testing

From `ranking_video_studio`, run the Python test suite:

```bat
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

To check the Java GUI without touching your real history:

```bat
cd licensing\java
javac -encoding UTF-8 -cp build\classes -d build\test-classes test\lrbar\license\GuiSmokeTest.java
java -cp "build\classes;build\test-classes" lrbar.license.GuiSmokeTest
```

To remove the activation on this computer (for testing), from `licensing`:

```bat
..\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'../ranking_video_studio'); from utils import license; license.deactivate()"
```

After changing any licensing code, rebuild the app **and the installer**
(`python build_exe.py` from `ranking_video_studio`) so the shipped
`LRBar-RankGen-Setup.exe` contains the protected build.

## Security limits (read this before shipping)

This is **offline, client-side** protection. It reliably stops casual key
sharing, copying a key to another PC and editing the key payload. It cannot
stop a determined person from patching the Python/PyInstaller executable, and
offline keys cannot be revoked early. If you need revocation, device limits
across reinstalls or stronger anti-tamper, you need an activation server; this
design can be extended to call one later.

Also keep in mind:

* A user who changes their system clock can stretch a 1-Day window. The app
  detects large backward jumps but a server is the only complete fix.
* The public key is visible in the binary by design.
* Never put `licensing/` (especially `private_key.pem`) into the PyInstaller
  build or the repository. The app build only needs
  `ranking_video_studio/utils/license_public_key.py`.
* The Java license manager must never be shipped to customers — it can sign
  keys.
