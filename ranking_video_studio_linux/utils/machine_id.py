"""Stable, human-friendly Machine ID used to bind a license to one computer.

On Linux the systemd/D-Bus ``machine-id`` (``/etc/machine-id``) is the primary
source because it survives reboots and kernel updates and is only regenerated
when the OS is reinstalled.  If it is unavailable we fall back to the DMI
product UUID and, as a last resort, the hostname + primary MAC address.

The Windows implementation is retained so this module can still be imported on
a developer machine, but only Linux sources are used by the Linux build.

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


def _linux_dmi_uuid():
    """Read the firmware product UUID (usually readable without root)."""
    try:
        with open("/sys/class/dmi/id/product_uuid", "r",
                  encoding="utf-8", errors="ignore") as fh:
            value = fh.read().strip()
        if value:
            return value
    except OSError:
        pass
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
    dmi = _linux_dmi_uuid()
    if dmi:
        return f"dmi:{dmi}"
    hostname = os.uname().nodename if hasattr(os, "uname") else ""
    return f"node:{uuid.getnode():012X}|host:{hostname}"


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
