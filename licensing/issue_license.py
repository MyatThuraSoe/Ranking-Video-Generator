"""Issue Ed25519-signed LRBar-RankGen license keys.

The customer sends you the Machine ID shown in the activation window. Issue a
key for that exact ID:

    python licensing/issue_license.py --machine 7F3A-9C2E-1B44-D07A-55C1 --type day
    python licensing/issue_license.py --machine 7F3A-9C2E-1B44-D07A-55C1 --type lifetime

A ``day`` key is valid for 24 hours from the moment it is generated and allows
at most 2 video exports (override with ``--videos``).  A ``lifetime`` key never
expires and has no export limit.

Every issued key is appended to ``licensing/issued_keys.csv`` (gitignored) so
you have a record of what was sold.  Keep ``private_key.pem`` secret.
"""
import argparse
import base64
import csv
import json
import os
import secrets
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), "ranking_video_studio")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from utils.machine_id import normalize_machine_id  # noqa: E402

KEY_PREFIX = "LRBG1"
KEY_VERSION = 1
DAY_SECONDS = 24 * 60 * 60
DEFAULT_TRIAL_VIDEOS = 2
PRIVATE_KEY_PATH = os.path.join(HERE, "private_key.pem")
LOG_PATH = os.path.join(HERE, "issued_keys.csv")

KIND_ALIASES = {
    "day": "day", "1day": "day", "1-day": "day", "trial": "day",
    "lifetime": "lifetime", "life": "lifetime", "forever": "lifetime",
}


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _load_private_key(path=PRIVATE_KEY_PATH):
    from cryptography.hazmat.primitives import serialization

    if not os.path.isfile(path):
        raise SystemExit(
            f"Private key not found: {path}\n"
            "Run 'python licensing/keygen.py' first (or restore your backup).")
    with open(path, "rb") as fh:
        data = fh.read()
    password = os.environ.get("LRBAR_PRIVATE_KEY_PASSWORD")
    try:
        key = serialization.load_pem_private_key(
            data, password=password.encode("utf-8") if password else None)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Could not load the private key: {exc}") from exc
    if not hasattr(key, "sign"):
        raise SystemExit("The private key file is not an Ed25519 signing key.")
    return key


def build_license_key(machine, kind="day", days=1, videos=DEFAULT_TRIAL_VIDEOS,
                      note="", issued_at=None, private_key=None,
                      license_id=None):
    """Return ``(license_key, payload_dict, info_dict)`` for one customer."""
    machine_id = normalize_machine_id(machine)
    if not machine_id:
        raise ValueError(
            "Machine ID must be 20 hexadecimal characters, for example "
            "7F3A-9C2E-1B44-D07A-55C1. Ask the customer to copy it from the "
            "activation window.")

    kind = KIND_ALIASES.get(str(kind).strip().lower())
    if kind is None:
        raise ValueError("License type must be 'day' or 'lifetime'.")
    if kind == "day":
        days = max(1, int(days))
        videos = max(1, int(videos))
        issued = int(issued_at if issued_at is not None else time.time())
        expires = issued + days * DAY_SECONDS
        max_videos = videos
    else:
        issued = int(issued_at if issued_at is not None else time.time())
        expires = 0
        max_videos = 0

    payload = {
        "v": KEY_VERSION,
        "m": machine_id,
        "t": kind,
        "i": issued,
        "e": expires,
        "n": max_videos,
        "r": str(license_id or secrets.token_hex(4)),
        "note": str(note or "")[:120],
    }
    payload_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True).encode("utf-8")
    signed = f"{KEY_PREFIX}.{_b64e(payload_bytes)}"
    key = private_key if private_key is not None else _load_private_key()
    signature = key.sign(signed.encode("ascii"))
    license_key = f"{signed}.{_b64e(signature)}"

    info = {
        "machine": machine_id,
        "kind": kind,
        "issued_at": issued,
        "expires_at": expires,
        "videos": max_videos,
        "license_id": payload["r"],
        "note": payload["note"],
    }
    return license_key, payload, info


def _fmt(ts):
    if not ts:
        return "never"
    return datetime.fromtimestamp(int(ts)).strftime("%d %b %Y %H:%M")


def describe(info):
    if info["kind"] == "lifetime":
        term = "Lifetime - never expires, unlimited exports"
    else:
        term = (f"1-Day - expires {_fmt(info['expires_at'])} "
                f"({info['videos']} video exports)")
    return (f"Machine ID : {info['machine']}\n"
            f"Type       : {term}\n"
            f"License ID : {info['license_id']}")


def log_issue(key, info, path=None):
    """Append the issued key to the seller's private log (best effort)."""
    path = path or LOG_PATH
    new_file = not os.path.isfile(path)
    try:
        with open(path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if new_file:
                writer.writerow([
                    "issued_at", "machine_id", "type", "expires_at",
                    "video_limit", "license_id", "note", "license_key",
                ])
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                info["machine"], info["kind"], _fmt(info["expires_at"]),
                info["videos"], info["license_id"], info["note"], key,
            ])
    except OSError as exc:
        print(f"[warn] could not write {path}: {exc}", file=sys.stderr)


def issue_key(machine, kind="day", days=1, videos=DEFAULT_TRIAL_VIDEOS,
              note="", log=True):
    key, _payload, info = build_license_key(
        machine, kind=kind, days=days, videos=videos, note=note)
    if log:
        log_issue(key, info)
    return key, info


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Issue an offline LRBar-RankGen license key.")
    parser.add_argument("--machine", required=True,
                        help="customer Machine ID, e.g. 7F3A-9C2E-1B44-D07A-55C1")
    parser.add_argument("--type", required=True, choices=["day", "lifetime"],
                        help="day = 24h + 2 exports, lifetime = unlimited")
    parser.add_argument("--days", type=int, default=1,
                        help="validity in days for a day key (default 1)")
    parser.add_argument("--videos", type=int, default=DEFAULT_TRIAL_VIDEOS,
                        help="export limit for a day key (default 2)")
    parser.add_argument("--note", default="", help="customer name / order note")
    parser.add_argument("--out", default="",
                        help="also write the key to this text file")
    parser.add_argument("--no-log", action="store_true",
                        help="do not append to issued_keys.csv")
    parser.add_argument("--quiet", action="store_true",
                        help="print only the license key")
    args = parser.parse_args(argv)

    try:
        key, info = issue_key(
            args.machine, kind=args.type, days=args.days,
            videos=args.videos, note=args.note, log=not args.no_log)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(key + "\n")

    if args.quiet:
        print(key)
    else:
        print("Issued LRBar-RankGen license")
        print("---------------------------")
        print(describe(info))
        print("\nLicense key (send this whole line to the customer):\n")
        print(key)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
