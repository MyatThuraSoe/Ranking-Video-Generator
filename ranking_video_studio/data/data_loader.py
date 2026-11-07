import os

import pandas as pd

from utils.config import MAX_ROWS


def load_dataset(path):
    """Load CSV/Excel, validate, sort by score desc. Returns DataFrame.

    Raises ValueError with a human-readable message on bad input.
    """
    if not os.path.isfile(path):
        raise ValueError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            raise ValueError("Unsupported file type. Please use .csv, .xlsx or .xls")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read file: {e}")

    df.columns = [str(c).strip().lower() for c in df.columns]
    if "name" not in df.columns or "score" not in df.columns:
        raise ValueError(
            "Missing required columns: 'name' and 'score'.\n"
            f"Found columns: {', '.join(df.columns)}")

    df = df.copy()
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["score"])
    if len(df) == 0:
        raise ValueError("No rows with a valid numeric 'score' found.")
    df["name"] = df["name"].astype(str)
    if "text" not in df.columns:
        df["text"] = ""
    if "image" not in df.columns:
        df["image"] = ""
    if "flag" not in df.columns:
        df["flag"] = ""
    df["text"] = df["text"].fillna("").astype(str)
    df["image"] = df["image"].fillna("").astype(str)
    df["flag"] = df["flag"].fillna("").astype(str)

    df = df.sort_values("score", ascending=False).head(MAX_ROWS).reset_index(drop=True)
    return df
