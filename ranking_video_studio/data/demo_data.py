import pandas as pd


def get_demo_data():
    return pd.DataFrame({
        "name": ["Python", "JavaScript", "C++", "Rust", "Go", "Java"],
        "score": [9850, 8740, 7600, 6900, 6400, 5800],
        "text": [
            "AI & Data Science", "Web Engine King", "High Performance",
            "Systems Programming", "Cloud Native", "Enterprise Backbone",
        ],
        "image": ["", "", "", "", "", ""],
        "extratext": ["", "", "", "", "", ""],
    })
