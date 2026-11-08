"""Stable, human-friendly Machine ID used to bind a license to one computer.

Windows' ``MachineGuid`` (written by Setup) is the primary source because it
survives reboots, Windows updates, hardware swaps and network changes.  It is
only regenerated when Windows itself is reinstalled.  If the registry value is
unavailable we fall back to the system volume serial number and, as a last
resort, the hostname + primary MAC address.

The published ID is a salted SHA-256 digest truncated to 80 bits and grouped in
four-character blocks (``7F3A-9C2E-1B44-D07A-55C1``), so it does not leak the
underlying hardware identifiers.
"""
import hashlib
import os
import re
import uuid

_ID_SALT = "LRBar-RankGen|machine-v1|"
_GROUP_RE = re.compile(r"[^0-9A-Fa-f]")


def _windows_machine_guid():
    """Read HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid."""
    if os.name != "nt":
        return ""
    try:
        import winreg
    except ImportError:
        return ""
    access_modes = [winreg.KEY_READ]
    wow64 = getattr(winreg, "KEY_WOW64_64KEY", 0)
    if wow64:
        access_modes.insert(0, winreg.KEY_READ | wow64)
    for access in access_modes:
        try:
            with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography", 0, access) as key:
                value, _kind = winreg.QueryValueEx(key, "MachineGuid")
                if value:
                    return str(value).strip()
        except (OSError, ValueError):
            continue
    return ""


def _windows_volume_serial():
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        root = (os.environ.get("SystemDrive") or "C:") + "\\"
        serial = wintypes.DWORD()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root), None, 0, ctypes.byref(serial),
            None, None, None, 0)
        if ok and serial.value:
            return f"{serial.value:08X}"
    except Exception:
        pass
    return ""


def _posix_machine_id():
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                value = fh.read().strip()
            if value:
                return value
        except OSError:
            continue
    return ""


def _raw_fingerprint():
    """Pick the most stable identifier available on this platform."""
    if os.name == "nt":
        primary = _windows_machine_guid()
        if primary:
            return primary
        volume = _windows_volume_serial()
        if volume:
            return f"volume:{volume}|node:{uuid.getnode():012X}"
        return f"node:{uuid.getnode():012X}"

    primary = _posix_machine_id()
    if primary:
        return primary
    return f"node:{uuid.getnode():012X}|host:{os.uname().nodename}"


def machine_id():
    """Return the 20-hex-character, dash-grouped ID shown to the user."""
    digest = hashlib.sha256(
        (_ID_SALT + _raw_fingerprint()).encode("utf-8")).hexdigest()
    raw = digest[:20].upper()
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def normalize_machine_id(text):
    """Accept an ID with or without dashes/spaces and return canonical form.

    Returns "" when the input is not a valid Machine ID.
    """
    raw = _GROUP_RE.sub("", str(text or "")).upper()
    if len(raw) != 20:
        return ""
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))
