"""Persistence for the dataset table editor.

Named projects live in states/<name>.json with created/updated metadata.
The working session is auto-saved to states/_autosave.json on every edit
(and into the active project, when one is open). The last folder the user
picked an image from is remembered in app_settings.json so the next image
picker opens right there.
"""
import json
import os
import re
from datetime import datetime

from utils.app_paths import user_data_dir

_APP_DIR = user_data_dir()
STATES_DIR = os.path.join(_APP_DIR, "states")
TEMPLATES_DIR = os.path.join(_APP_DIR, "templates")
AUTOSAVE_NAME = "_autosave"
_SETTINGS_PATH = os.path.join(_APP_DIR, "app_settings.json")

COLUMNS = ["name", "score", "text", "image", "extratext"]


def _ensure_dir():
    os.makedirs(STATES_DIR, exist_ok=True)


def _safe_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name).strip())
    return name[:80]


def _state_path(name):
    return os.path.join(STATES_DIR, _safe_name(name) + ".json")


def _write_json(path, payload):
    _ensure_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def df_to_records(df):
    import pandas as pd
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col in COLUMNS:
            val = row.get(col, "")
            rec[col] = "" if val is None or pd.isna(val) else str(val)
        records.append(rec)
    return records


def records_to_df(records):
    import pandas as pd
    rows = []
    for rec in records:
        try:
            score = float(str(rec.get("score", "0")).replace(",", ""))
        except (TypeError, ValueError):
            score = 0.0
        rows.append({
            "name": str(rec.get("name", "")),
            "score": score,
            "text": str(rec.get("text", "")),
            "image": str(rec.get("image", "")),
            "extratext": str(rec.get("extratext", "")),
            "flag": str(rec.get("flag", "")),
        })
    if not rows:
        rows = [{"name": "", "score": 0.0, "text": "", "image": "",
                 "extratext": "", "flag": ""}]
    return pd.DataFrame(rows)


def save_project(name, records):
    """Create or update a named project, preserving its creation date."""
    now = datetime.now().isoformat(timespec="seconds")
    created = now
    path = _state_path(name)
    if os.path.isfile(path):
        try:
            old = _read_json(path)
            created = old.get("created_at") or old.get("saved_at") or now
        except (OSError, ValueError):
            pass
    payload = {
        "name": str(name),
        "created_at": created,
        "updated_at": now,
        "saved_at": now,
        "row_count": len(records),
        "rows": records,
    }
    _write_json(path, payload)


def load_project(name):
    return _read_json(_state_path(name)).get("rows", [])


def project_meta(name):
    try:
        data = _read_json(_state_path(name))
    except (OSError, ValueError):
        return None
    return {
        "name": data.get("name", name),
        "created_at": data.get("created_at", data.get("saved_at", "")),
        "updated_at": data.get("updated_at", data.get("saved_at", "")),
        "row_count": data.get("row_count", len(data.get("rows", []))),
    }


def project_exists(name):
    return os.path.isfile(_state_path(name))


def delete_project(name):
    path = _state_path(name)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def rename_project(old, new):
    if old == new:
        return True
    if project_exists(new):
        return False
    data = _read_json(_state_path(old))
    data["name"] = str(new)
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(_state_path(new), data)
    os.remove(_state_path(old))
    return True


def list_projects():
    """Metadata for every saved project, most recently updated first."""
    if not os.path.isdir(STATES_DIR):
        return []
    metas = []
    for fn in os.listdir(STATES_DIR):
        if fn.endswith(".json") and not fn.startswith("_"):
            meta = project_meta(fn[:-5])
            if meta:
                metas.append(meta)
    metas.sort(key=lambda m: m["updated_at"], reverse=True)
    return metas


# ------------------------------------------------------------- templates
# Templates store the full customization state (everything except the data
# table) in templates/<name>.json, kept apart from project states so they
# never appear in the project list.
def _template_path(name):
    return os.path.join(TEMPLATES_DIR, _safe_name(name) + ".json")


def save_template(name, settings):
    """Create or update a named template, preserving its creation date."""
    now = datetime.now().isoformat(timespec="seconds")
    created = now
    path = _template_path(name)
    if os.path.isfile(path):
        try:
            old = _read_json(path)
            created = old.get("created_at") or old.get("saved_at") or now
        except (OSError, ValueError):
            pass
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    _write_json(path, {
        "name": str(name),
        "created_at": created,
        "updated_at": now,
        "saved_at": now,
        "settings": dict(settings),
    })


def load_template(name):
    try:
        return _read_json(_template_path(name)).get("settings", {})
    except (OSError, ValueError):
        return {}


def template_meta(name):
    try:
        data = _read_json(_template_path(name))
    except (OSError, ValueError):
        return None
    return {
        "name": data.get("name", name),
        "created_at": data.get("created_at", data.get("saved_at", "")),
        "updated_at": data.get("updated_at", data.get("saved_at", "")),
        "field_count": len(data.get("settings", {})),
    }


def template_exists(name):
    return os.path.isfile(_template_path(name))


def delete_template(name):
    path = _template_path(name)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def rename_template(old, new):
    if old == new:
        return True
    if template_exists(new):
        return False
    data = _read_json(_template_path(old))
    data["name"] = str(new)
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(_template_path(new), data)
    os.remove(_template_path(old))
    return True


def list_templates():
    """Metadata for every saved template, most recently updated first."""
    if not os.path.isdir(TEMPLATES_DIR):
        return []
    metas = []
    for fn in os.listdir(TEMPLATES_DIR):
        if fn.endswith(".json") and not fn.startswith("_"):
            meta = template_meta(fn[:-5])
            if meta:
                metas.append(meta)
    metas.sort(key=lambda m: m["updated_at"], reverse=True)
    return metas


def save_autosave(records):
    _write_json(_state_path(AUTOSAVE_NAME), {
        "name": AUTOSAVE_NAME,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "rows": records,
    })


def load_autosave():
    path = _state_path(AUTOSAVE_NAME)
    if not os.path.isfile(path):
        return None
    try:
        return _read_json(path).get("rows", [])
    except (OSError, ValueError):
        return None


def autosave_time():
    path = _state_path(AUTOSAVE_NAME)
    if not os.path.isfile(path):
        return ""
    try:
        return _read_json(path).get("saved_at", "").replace("T", " ")
    except (OSError, ValueError):
        return ""


# ------------------------------------------------------- app-level settings
def _load_settings():
    if os.path.isfile(_SETTINGS_PATH):
        try:
            return _read_json(_SETTINGS_PATH)
        except (OSError, ValueError):
            pass
    return {}


def get_last_image_dir():
    d = _load_settings().get("last_image_dir", "")
    return d if d and os.path.isdir(d) else ""


def _save_settings(settings):
    _ensure_dir()
    tmp = _SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _SETTINGS_PATH)


def set_last_image_dir(path):
    settings = _load_settings()
    settings["last_image_dir"] = os.path.dirname(os.path.abspath(path))
    _save_settings(settings)


def get_video_save_path():
    return _load_settings().get("video_save_path", "")


def set_video_save_path(path):
    settings = _load_settings()
    settings["video_save_path"] = str(path)
    _save_settings(settings)


def get_theme():
    return _load_settings().get("theme", "Bright")


def set_theme(name):
    settings = _load_settings()
    settings["theme"] = str(name)
    _save_settings(settings)