import os

import pandas as pd

from utils.app_paths import sample_assets_dir

# name, score, subtitle, sample logo filename (portable across machines)
SAMPLE_ROWS = [
    ("Python", 9850, "AI & Data Science", "python-logo.jpg"),
    ("JavaScript", 8740, "Web Engine King", "JavaScript-logo.png"),
    ("C++", 7600, "High Performance", "ISO_C++_Logo.svg.webp"),
    ("Rust", 6900, "Systems Programming", "rust logo.webp"),
    ("Go", 6400, "Cloud Native", "Go-Logo_Blue.png"),
    ("Java", 5800, "Enterprise Backbone", "Java-Logo.jpg"),
]


def get_demo_data():
    folder = sample_assets_dir()
    rows = []
    for name, score, text, filename in SAMPLE_ROWS:
        image = os.path.join(folder, filename) if folder else ""
        if image and not os.path.isfile(image):
            image = ""
        rows.append({"name": name, "score": str(score), "text": text,
                     "image": image, "extratext": ""})
    return pd.DataFrame(rows, columns=["name", "score", "text", "image",
                                       "extratext"])