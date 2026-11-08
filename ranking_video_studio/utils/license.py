"""Offline, machine-bound license activation.

A license key is a compact, Ed25519-signed token issued by the vendor::

    LRBG1.<base64url(payload JSON)>.<base64url(64-byte signature)>

The payload is bound to a single Machine ID and declares either a **1-day**
license (24 hours from issue, at most two video exports) or a **lifetime**
license (never expires, unlimited exports).  The app ships only the *public*
key, so keys cannot be forged; the private signing key never leaves the vendor.

The activation record (key + video counter) is stored in
``%APPDATA%/LRBar-RankGen/license.json`` and mirrored to
``HKCU\\Software\\LRBar\\RankGen`` so deleting one copy does not reset a
1-day quota.  Both copies are sealed with an HMAC derived from the Machine ID.

This is a client-side check: it stops casual sharing and tampering, but a
determined attacker who patches the executable can always bypass it.  Online
activation is required for revocation or stronger enforcement.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime

from utils.app_paths import user_data_dir
from utils.license_public_key import PUBLIC_KEY_B64
from utils.machine_id import machine_id, normalize_machine_id

KEY_PREFIX = "LRBG1"
KEY_VERSION = 1
DAY_KIND = "day"
LIFETIME_KIND = "lifetime"
KIND_LABELS = {DAY_KIND: "1-Day License", LIFETIME_KIND: "Lifetime License"}

TRIAL_VIDEO_LIMIT = 2
DAY_SECONDS = 24 * 60 * 60

STATE_FILENAME = "license.json"
_REGISTRY_PATH = r"Software\LRBar\RankGen"
_REGISTRY_VALUE = "license_state"
_STATE_SALT = b"LRBar-RankGen/license-state/v1"
_CLOCK_SKEW = 6 * 60 * 60          # tolerate DST / small clock corrections
_ISSUE_SKEW = 48 * 60 * 60         # tolerate a clock slightly behind issuance

_WHITESPACE_RE = re.compile(r"[\s\u200b-\u200d\ufeff]+")
# A signature is exactly 64 bytes => 86 unpadded base64url characters.  The
# fixed length lets us recover a key pasted inside a longer chat message.
_KEY_RE = re.compile(r"LRBG1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{86}")


class LicenseError(Exception):
    """A license problem that can be shown to the user as-is."""


# --------------------------------------------------------------- key format
@dataclass(frozen=True)
class LicenseInfo:
    """Verified contents of a license key."""

    key: str
    kind: str
    machine: str
    issued_at: int
    expires_at: int
    max_videos: int
    license_id: str

    @property
    def is_lifetime(self):
        return self.kind == LIFETIME_KIND

    @property
    def label(self):
        return KIND_LABELS.get(self.kind, self.kind)

    def expires_text(self):
        if self.is_lifetime:
            return "Never"
        return _format_time(self.expires_at)


@dataclass(frozen=True)
class Status:
    """Everything the UI needs to know about the current activation."""

    machine_id: str
    active: bool
    error: str = ""
    info: LicenseInfo = None
    videos_used: int = 0
    activated_at: int = 0
    last_seen: int = 0

    @property
    def kind_label(self):
        return self.info.label if self.info else "Not activated"

    @property
    def max_videos(self):
        return self.info.max_videos if self.info else 0

    @property
    def videos_left(self):
        """Remaining exports, or None for an unlimited lifetime license."""
        if not self.active or self.info is None:
            return 0
        if self.info.is_lifetime:
            return None
        return max(0, self.info.max_videos - self.videos_used)

    @property
    def expires_at(self):
        return self.info.expires_at if self.info else 0

    def summary(self):
        if not self.active:
            return self.error or "This copy is not activated."
        if self.info is None:
            return "Licensed."
        if self.info.is_lifetime:
            return "Lifetime License — active, unlimited video exports."
        left = self.videos_left
        return (f"1-Day License — {left} of {self.info.max_videos} video "
                f"exports left · expires {self.info.expires_text()}")


def _format_time(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%d %b %Y, %H:%M")
    except (OSError, OverflowError, ValueError):
        return "unknown"


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def normalize_key(text):
    """Strip whitespace, quotes and any surrounding chat text.

    Customers often paste the seller's whole message (``"Your key: LRBG1..."``)
    or a key wrapped across several lines; only the token itself matters.
    """
    if not text:
        return ""
    cleaned = _WHITESPACE_RE.sub("", str(text)).strip("\"'")
    match = _KEY_RE.search(cleaned)
    if match:
        return match.group(0).rstrip("=")
    return cleaned.replace("=", "")


def _public_key(public_key_b64=None):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        raw = base64.b64decode(public_key_b64 or PUBLIC_KEY_B64)
        return Ed25519PublicKey.from_public_bytes(raw)
    except Exception as exc:  # pragma: no cover - only on a broken build
        raise LicenseError(
            "The license verifier is damaged in this installation. "
            "Please reinstall LRBar-RankGen.") from exc


def parse_and_verify(key, *, machine=None, public_key_b64=None, now=None):
    """Verify a license key and return its :class:`LicenseInfo`.

    Raises :class:`LicenseError` with a user-facing message when the key is
    malformed, signed by another key, issued for another computer, expired or
    otherwise unusable.
    """
    from cryptography.exceptions import InvalidSignature

    key = normalize_key(key)
    if not key:
        raise LicenseError("Please paste your license key first.")

    parts = key.split(".")
    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        raise LicenseError(
            "This does not look like a LRBar-RankGen license key. "
            "Copy the complete key you received and paste it again.")

    signed_text = f"{parts[0]}.{parts[1]}"
    try:
        payload_bytes = _b64d(parts[1])
        signature = _b64d(parts[2])
    except Exception as exc:
        raise LicenseError(
            "This license key is damaged or incomplete. "
            "Copy it again exactly as you received it.") from exc
    if len(signature) != 64:
        raise LicenseError(
            "This license key is damaged or incomplete. "
            "Copy it again exactly as you received it.")

    try:
        _public_key(public_key_b64).verify(
            signature, signed_text.encode("ascii"))
    except InvalidSignature as exc:
        raise LicenseError(
            "This license key is not valid for LRBar-RankGen "
            "(signature check failed). Please use the key exactly as supplied "
            "by the seller.") from exc
    except LicenseError:
        raise
    except Exception as exc:
        raise LicenseError(
            "This license key could not be verified. "
            "Please use the key exactly as supplied by the seller.") from exc

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise LicenseError(
            "This license key is damaged or incomplete. "
            "Copy it again exactly as you received it.") from exc

    if not isinstance(payload, dict) or payload.get("v") != KEY_VERSION:
        raise LicenseError(
            "This license key uses an unsupported format. "
            "Please ask the seller for a new key.")

    try:
        kind = str(payload["t"])
        key_machine = normalize_machine_id(payload["m"])
        issued_at = int(payload["i"])
        expires_at = int(payload["e"])
        max_videos = int(payload.get("n", 0))
        license_id = str(payload.get("r", ""))
    except (KeyError, TypeError, ValueError) as exc:
        raise LicenseError(
            "This license key is damaged or incomplete. "
            "Copy it again exactly as you received it.") from exc

    if kind not in (DAY_KIND, LIFETIME_KIND):
        raise LicenseError(
            "This license key has an unknown license type. "
            "Please ask the seller for a new key.")
    if not key_machine:
        raise LicenseError(
            "This license key is damaged (missing Machine ID). "
            "Please ask the seller for a new key.")

    current_machine = normalize_machine_id(machine or machine_id())
    if not hmac.compare_digest(key_machine, current_machine):
        raise LicenseError(
            "This license key was issued for a different computer.\n\n"
            f"This computer's Machine ID is:\n{current_machine}\n\n"
            f"The key was issued for:\n{key_machine}\n\n"
            "Send your Machine ID to the seller and ask for a key made for "
            "this computer.")

    if kind == DAY_KIND:
        if max_videos <= 0:
            raise LicenseError(
                "This 1-day license key is damaged (missing video limit). "
                "Please ask the seller for a new key.")
        if expires_at <= issued_at:
            raise LicenseError(
                "This 1-day license key is damaged (invalid expiry). "
                "Please ask the seller for a new key.")
    else:
        expires_at = 0
        max_videos = 0

    now = int(now if now is not None else time.time())
    if now < issued_at - _ISSUE_SKEW:
        raise LicenseError(
            "This computer's clock is set earlier than the license issue "
            "date. Set the correct date and time, then try again.")
    if kind == DAY_KIND and now >= expires_at:
        raise LicenseError(
            "This 1-day license expired on "
            f"{_format_time(expires_at)}.\n\n"
            "If that date looks wrong, set your computer's date and time "
            "correctly and try again. Otherwise request a new license key "
            "from the seller.")

    return LicenseInfo(
        key=key,
        kind=kind,
        machine=key_machine,
        issued_at=issued_at,
        expires_at=expires_at,
        max_videos=max_videos,
        license_id=license_id,
    )


# ------------------------------------------------------------ sealed state
def _store_dir():
    override = os.environ.get("LRBAR_LICENSE_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    return user_data_dir()


def _state_path():
    return os.path.join(_store_dir(), STATE_FILENAME)


def _state_secret():
    return hashlib.sha256(
        _STATE_SALT + b"|" + machine_id().encode("ascii")).digest()


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _seal(data):
    raw = _canonical(data)
    sig = hmac.new(_state_secret(), raw, hashlib.sha256).hexdigest()
    return {"data": data, "sig": sig}


def _unseal(blob):
    if not blob:
        return None
    try:
        outer = json.loads(blob)
        data = outer["data"]
        sig = str(outer["sig"])
        if not isinstance(data, dict):
            return None
        expected = hmac.new(
            _state_secret(), _canonical(data), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        state = {
            "key": str(data.get("key", "")),
            "activated_at": int(data.get("activated_at", 0)),
            "videos_used": max(0, int(data.get("videos_used", 0))),
            "last_seen": max(0, int(data.get("last_seen", 0))),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not state["key"]:
        return None
    return state


# The registry mirror means deleting license.json cannot reset the trial.
def _registry_enabled():
    return (os.name == "nt"
            and os.environ.get("LRBAR_LICENSE_NO_REGISTRY") != "1")


def _registry_read():
    if not _registry_enabled():
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REGISTRY_PATH) as key:
            value, _kind = winreg.QueryValueEx(key, _REGISTRY_VALUE)
            return str(value)
    except (OSError, ValueError):
        return ""


def _registry_write(blob):
    if not _registry_enabled():
        return
    try:
        import winreg

        with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, _REGISTRY_PATH, 0,
                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, _REGISTRY_VALUE, 0, winreg.REG_SZ, blob)
    except (OSError, ValueError):
        pass


def _registry_clear():
    if not _registry_enabled():
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REGISTRY_PATH, 0,
                            winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, _REGISTRY_VALUE)
    except (OSError, ValueError):
        pass


def _read_file_blob():
    try:
        with open(_state_path(), "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _read_records():
    records = []
    for blob in (_read_file_blob(), _registry_read()):
        state = _unseal(blob)
        if state is not None:
            records.append(state)
    return records


def _empty_state():
    return {"key": "", "activated_at": 0, "videos_used": 0, "last_seen": 0}


def _load_state():
    """Merge the file and registry copies, preferring the newest one.

    Video counters are merged upward for the same key so removing one copy of
    the state file can never hand back a used export.
    """
    records = _read_records()
    if not records:
        return _empty_state()
    records.sort(key=lambda s: (s["last_seen"], s["activated_at"]),
                 reverse=True)
    newest = dict(records[0])
    newest["videos_used"] = max(
        r["videos_used"] for r in records if r["key"] == newest["key"])
    return newest


def _write_state(state):
    sealed = _seal(state)
    blob = json.dumps(sealed, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)
    path = _state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(blob)
        os.replace(tmp, path)
    except OSError:
        pass
    _registry_write(blob)


# --------------------------------------------------------------- public API
def status(now=None):
    """Current activation state, including remaining trial exports."""
    now = int(now if now is not None else time.time())
    current_machine = machine_id()
    state = _load_state()

    if not state["key"]:
        return Status(
            machine_id=current_machine, active=False,
            error="This copy of LRBar-RankGen is not activated yet.")

    try:
        info = parse_and_verify(
            state["key"], machine=current_machine, now=now)
    except LicenseError as exc:
        return Status(
            machine_id=current_machine, active=False, error=str(exc),
            videos_used=state["videos_used"],
            activated_at=state["activated_at"],
            last_seen=state["last_seen"])

    if (not info.is_lifetime
            and now < state["last_seen"] - _CLOCK_SKEW):
        return Status(
            machine_id=current_machine, active=False,
            error="The system clock on this computer has moved backwards "
                  "since this license was last used. Set the correct date "
                  "and time, then try again.",
            info=info, videos_used=state["videos_used"],
            activated_at=state["activated_at"],
            last_seen=state["last_seen"])

    return Status(
        machine_id=current_machine, active=True, info=info,
        videos_used=state["videos_used"],
        activated_at=state["activated_at"],
        last_seen=state["last_seen"])


def activate(key, now=None):
    """Verify and store a license key for this computer.

    Re-activating the same key keeps the existing video counter; activating a
    different key starts that key's own quota.
    """
    now = int(now if now is not None else time.time())
    info = parse_and_verify(key, now=now)
    state = _load_state()
    same_key = bool(state["key"]) and state["key"] == info.key
    new_state = {
        "key": info.key,
        "activated_at": state["activated_at"] if same_key else now,
        "videos_used": state["videos_used"] if same_key else 0,
        "last_seen": now,
    }
    _write_state(new_state)
    return status(now)


def deactivate():
    """Forget the activation on this computer (support / tests only)."""
    _write_state(_empty_state())
    try:
        os.remove(_state_path())
    except OSError:
        pass
    _registry_clear()


def reserve_video(now=None):
    """Consume one video export from the active license.

    Called immediately before an export starts.  Raises
    :class:`LicenseError` when the license is inactive, expired or out of
    trial exports.  Returns the updated :class:`Status`.
    """
    now = int(now if now is not None else time.time())
    current = status(now)
    if not current.active:
        raise LicenseError(current.error or "Your license is not valid.")
    if current.info is not None and not current.info.is_lifetime:
        left = current.videos_left
        if left is not None and left <= 0:
            raise LicenseError(
                "Your 1-Day License has already used its "
                f"{current.info.max_videos} video exports.\n\n"
                "Please request a new license key from the seller to "
                "export more videos.")
        state = _load_state()
        state["videos_used"] = max(
            state["videos_used"], current.videos_used) + 1
        state["last_seen"] = now
        _write_state(state)
    return status(now)
