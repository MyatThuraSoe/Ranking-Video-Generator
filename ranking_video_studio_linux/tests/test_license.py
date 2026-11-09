"""Tests for the offline license key format and trial counter."""
import base64
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from utils import license as lic  # noqa: E402

TEST_PRIVATE = Ed25519PrivateKey.generate()
TEST_PUBLIC_B64 = base64.b64encode(
    TEST_PRIVATE.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw)).decode("ascii")


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def make_key(machine=None, kind="day", issued_at=None, expires_at=None,
             max_videos=None, note="test"):
    machine = machine or lic.machine_id()
    issue = int(time.time()) if issued_at is None else int(issued_at)
    if expires_at is None:
        expires_at = issue + lic.DAY_SECONDS if kind == "day" else 0
    if max_videos is None:
        max_videos = lic.TRIAL_VIDEO_LIMIT if kind == "day" else 0
    payload = {
        "v": 1, "m": machine, "t": kind, "i": issue,
        "e": int(expires_at), "n": int(max_videos),
        "r": "testbeef", "note": note,
    }
    payload_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signed = f"{lic.KEY_PREFIX}.{_b64e(payload_bytes)}"
    signature = TEST_PRIVATE.sign(signed.encode("ascii"))
    return f"{signed}.{_b64e(signature)}", payload


class LicenseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lrbar-license-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = mock.patch.dict(os.environ, {
            "LRBAR_LICENSE_DIR": self.tmp,
            "LRBAR_LICENSE_NO_MIRROR": "1",
            "LRBAR_LICENSE_NO_REGISTRY": "1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.pub = mock.patch.object(lic, "PUBLIC_KEY_B64", TEST_PUBLIC_B64)
        self.pub.start()
        self.addCleanup(self.pub.stop)

    def test_machine_id_is_stable_and_formatted(self):
        first = lic.machine_id()
        self.assertRegex(first, r"^[0-9A-F]{4}(-[0-9A-F]{4}){4}$")
        self.assertEqual(first, lic.machine_id())

    def test_lifetime_activation_has_unlimited_exports(self):
        key, _ = make_key(kind="lifetime")
        status = lic.activate(key)
        self.assertTrue(status.active)
        self.assertEqual(status.kind_label, "Lifetime License")
        self.assertIsNone(status.videos_left)
        for _ in range(5):
            status = lic.reserve_video()
            self.assertTrue(status.active)
        self.assertEqual(status.videos_used, 0)

    def test_day_key_allows_two_videos_then_blocks(self):
        key, _ = make_key(kind="day")
        status = lic.activate(key)
        self.assertEqual(status.videos_left, 2)

        lic.reserve_video()
        self.assertEqual(lic.status().videos_left, 1)
        lic.reserve_video()
        self.assertEqual(lic.status().videos_left, 0)

        with self.assertRaises(lic.LicenseError):
            lic.reserve_video()
        self.assertEqual(lic.status().videos_used, 2)

    def test_whitespace_in_pasted_key_is_ignored(self):
        key, _ = make_key(kind="lifetime")
        wrapped = key[:40] + "\n  " + key[40:] + "\n"
        self.assertTrue(lic.activate(wrapped).active)

    def test_key_found_inside_a_pasted_message(self):
        key, _ = make_key(kind="lifetime")
        message = f"Thanks for your order!\nYour license key:\n{key}\nEnjoy!"
        self.assertTrue(lic.activate(message).active)

    def test_reactivating_same_key_keeps_video_counter(self):
        key, _ = make_key(kind="day")
        lic.activate(key)
        lic.reserve_video()
        lic.activate(key)
        self.assertEqual(lic.status().videos_used, 1)

    def test_expired_day_key_is_rejected(self):
        now = int(time.time())
        key, _ = make_key(kind="day", issued_at=now - 3 * 86400,
                          expires_at=now - 2 * 86400)
        with self.assertRaises(lic.LicenseError) as ctx:
            lic.activate(key)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_key_for_another_machine_is_rejected(self):
        other = "AAAA-BBBB-CCCC-DDDD-EEEE"
        key, _ = make_key(machine=other, kind="lifetime")
        with self.assertRaises(lic.LicenseError) as ctx:
            lic.activate(key)
        message = str(ctx.exception)
        self.assertIn(lic.machine_id(), message)
        self.assertIn(other, message)

    def test_edited_payload_fails_signature(self):
        key, payload = make_key(kind="day", max_videos=2)
        payload["n"] = 999
        payload_bytes = json.dumps(
            payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        parts = key.split(".")
        tampered = f"{parts[0]}.{_b64e(payload_bytes)}.{parts[2]}"
        with self.assertRaises(lic.LicenseError):
            lic.parse_and_verify(tampered)

    def test_garbage_key_is_rejected(self):
        for bad in ("", "hello", "LRBG1.abc.def", "LRBG2.abc.def"):
            with self.assertRaises(lic.LicenseError):
                lic.parse_and_verify(bad)

    def test_tampered_state_file_is_ignored(self):
        key, _ = make_key(kind="day")
        lic.activate(key)
        path = os.path.join(self.tmp, lic.STATE_FILENAME)
        with open(path, "r", encoding="utf-8") as fh:
            sealed = json.load(fh)
        sealed["data"]["videos_used"] = 0
        sealed["data"]["last_seen"] = 0
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(sealed, fh)
        self.assertEqual(lic._load_state(), lic._empty_state())
        self.assertFalse(lic.status().active)

    def test_sealed_mirror_survives_deleting_visible_state(self):
        """The XDG config mirror must keep a used 1-Day quota used."""
        config_home = tempfile.mkdtemp(prefix="lrbar-config-")
        self.addCleanup(shutil.rmtree, config_home, True)
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config_home}):
            os.environ.pop("LRBAR_LICENSE_NO_MIRROR", None)
            os.environ.pop("LRBAR_LICENSE_NO_REGISTRY", None)

            key, _ = make_key(kind="day")
            lic.activate(key)
            lic.reserve_video()
            lic.reserve_video()

            mirror = os.path.join(
                config_home, "LRBar-RankGen", lic._MIRROR_FILENAME)
            self.assertTrue(os.path.isfile(mirror))

            os.remove(os.path.join(self.tmp, lic.STATE_FILENAME))
            status = lic.status()
            self.assertTrue(status.active)
            self.assertEqual(status.videos_used, 2)
            self.assertEqual(status.videos_left, 0)
            with self.assertRaises(lic.LicenseError):
                lic.reserve_video()

    def test_deactivate_clears_the_mirror(self):
        config_home = tempfile.mkdtemp(prefix="lrbar-config-")
        self.addCleanup(shutil.rmtree, config_home, True)
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config_home}):
            os.environ.pop("LRBAR_LICENSE_NO_MIRROR", None)
            os.environ.pop("LRBAR_LICENSE_NO_REGISTRY", None)

            key, _ = make_key(kind="lifetime")
            lic.activate(key)
            mirror = os.path.join(
                config_home, "LRBar-RankGen", lic._MIRROR_FILENAME)
            self.assertTrue(os.path.isfile(mirror))
            lic.deactivate()
            self.assertFalse(os.path.exists(mirror))
            self.assertFalse(lic.status().active)

    def test_config_dir_follows_xdg(self):
        from utils.app_paths import config_dir

        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp}):
            self.assertEqual(
                config_dir(), os.path.join(self.tmp, "LRBar-RankGen"))

    def test_deactivate_clears_activation(self):
        key, _ = make_key(kind="lifetime")
        lic.activate(key)
        self.assertTrue(lic.status().active)
        lic.deactivate()
        self.assertFalse(lic.status().active)


if __name__ == "__main__":
    unittest.main()
