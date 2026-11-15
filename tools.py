import os
import subprocess
import csv
import static_ffmpeg

try:
    static_ffmpeg.add_paths()
except Exception as e:
    print(f"static_ffmpeg warning in tools: {e}")

def extract_video_slides(video_source: str, output_dir: str, count: int = 4) -> list:
    """
    Extracts key slide frames from a video stream or file at regular intervals.
    Returns list of saved image paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    slide_paths = []

    # Try probe duration or sample at fixed timestamps if duration unknown
    timestamps = ["00:08:00", "00:25:00", "00:50:00", "01:20:00"]
    if count == 6:
        timestamps = ["00:05:00", "00:20:00", "00:40:00", "01:00:00", "01:20:00", "01:40:00"]

    for i, ts in enumerate(timestamps[:count], 1):
        out_img = os.path.join(output_dir, f"slide_{i}.jpg")
        try:
            cmd = [
                "ffmpeg", "-y", "-ss", ts, "-i", video_source,
                "-vframes", "1", "-q:v", "2", out_img
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            if res.returncode == 0 and os.path.exists(out_img) and os.path.getsize(out_img) > 2000:
                slide_paths.append(out_img)
        except Exception as e:
            print(f"Slide {i} extraction skipped: {e}")

    # Fallback: if timestamps were too far, try at 00:01:00, 00:03:00
    if not slide_paths:
        for i, ts in enumerate(["00:01:00", "00:03:00"], 1):
            out_img = os.path.join(output_dir, f"slide_early_{i}.jpg")
            try:
                cmd = ["ffmpeg", "-y", "-ss", ts, "-i", video_source, "-vframes", "1", "-q:v", "2", out_img]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if res.returncode == 0 and os.path.exists(out_img) and os.path.getsize(out_img) > 2000:
                    slide_paths.append(out_img)
            except Exception:
                pass

    return slide_paths

def export_anki_csv(flashcards: list, output_csv_path: str, course_title: str = "Dirasa") -> str:
    """
    Exports flashcards to Anki-compatible CSV file (UTF-8, tab-separated).
    Columns: Front, Back, Tag
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
    clean_tag = "".join(c for c in course_title if c.isalnum() or c == "_")[:20] or "Cours"

    with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["#front", "back", "tags"])
        for card in flashcards:
            front = card.get("front", "").strip()
            back = card.get("back", "").strip()
            if front and back:
                writer.writerow([front, back, clean_tag])

    return output_csv_path
