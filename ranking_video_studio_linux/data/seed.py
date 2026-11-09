"""First-run seeding of bundled sample content into writable user data.

A frozen build ships templates, sample logo images and a portable sample
dataset under ``seed/``. On first launch these are copied into the per-user
writable directory so the app opens populated and the samples show up in the
Templates and Projects lists. Existing user files are never overwritten.
"""
import json
import os
import shutil

from utils.app_paths import bundle_dir, user_data_dir

SAMPLE_PROJECT = "Sample Ranking"


def seed_user_data():
    seed = os.path.join(bundle_dir(), "seed")
    if not os.path.isdir(seed):
        return False
    from data import state_store as store

    target = user_data_dir()
    changed = False

    assets_src = os.path.join(seed, "sample_assets")
    assets_dst = os.path.join(target, "sample_assets")
    if os.path.isdir(assets_src):
        os.makedirs(assets_dst, exist_ok=True)
        for fn in os.listdir(assets_src):
            dst = os.path.join(assets_dst, fn)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(assets_src, fn), dst)
                changed = True

    tpl_src = os.path.join(seed, "templates")
    tpl_dst = os.path.join(target, "templates")
    if os.path.isdir(tpl_src):
        os.makedirs(tpl_dst, exist_ok=True)
        for fn in os.listdir(tpl_src):
            if not fn.endswith(".json"):
                continue
            dst = os.path.join(tpl_dst, fn)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(tpl_src, fn), dst)
                changed = True

    data_src = os.path.join(seed, "sample_data.json")
    if os.path.isfile(data_src) and not store.project_exists(SAMPLE_PROJECT):
        with open(data_src, "r", encoding="utf-8") as fh:
            records = json.load(fh)
        for rec in records:
            img = rec.get("image", "")
            if img and not os.path.isabs(img):
                rec["image"] = os.path.join(assets_dst, img)
        store.save_project(SAMPLE_PROJECT, records)
        changed = True

    return changed