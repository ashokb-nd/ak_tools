"""Utilities for filtering analytics logs."""

from pathlib import Path

def clean_log_in_folder(folder: str = ".", extra_keywords: tuple[str, ...] = ()) -> str:
    DEFAULT_KEYWORDS = ["drowsy_sensor_fusion", "drowsy_severe", "LaneEncroachment"]
    input_filename = "analytics.log"
    output_filename = "analytics_filtered.log"

    """Find analytics.log in a folder, clean it, and save analytics_filtered.log."""
    analytics_file = Path(folder) / input_filename
    if not analytics_file.exists() or not analytics_file.is_file():
        raise FileNotFoundError(f"{input_filename} not found in folder: {Path(folder).resolve()}")

    with analytics_file.open("r") as file:
        data = file.readlines()

    words = list(extra_keywords) if extra_keywords else DEFAULT_KEYWORDS
    data_filtered = [line for line in data if any(word in line for word in words)]

    data_cleaned = [" ".join(line.split(" - ")[2:]) for line in data_filtered]

    output_file = analytics_file.with_name(output_filename)
    with output_file.open("w") as f:
        f.writelines("%s" % line for line in data_cleaned)

    return str(output_file)
