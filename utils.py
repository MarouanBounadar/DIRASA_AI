import os
import re
import subprocess
import sys

def open_file(filepath: str):
    """Opens a file with the system's default application on Windows."""
    if os.path.exists(filepath):
        try:
            os.startfile(filepath)
        except Exception as e:
            print(f"Error opening file: {e}")

def open_directory(directory: str):
    """Opens the directory in Windows File Explorer."""
    if os.path.exists(directory):
        try:
            subprocess.run(["explorer", os.path.normpath(directory)], check=False)
        except Exception as e:
            print(f"Error opening directory: {e}")

def format_duration(seconds: float) -> str:
    """Formats seconds into readable string (e.g. 1h 24m or 15m 30s)."""
    if not seconds or seconds <= 0:
        return "Non spécifiée"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"

def format_size(bytes_or_mb: float, is_mb: bool = True) -> str:
    """Formats file size."""
    if is_mb:
        return f"{bytes_or_mb:.1f} Mo"
    return f"{bytes_or_mb / (1024*1024):.1f} Mo"

def is_valid_url(text: str) -> bool:
    """Checks if string looks like an HTTP/HTTPS URL."""
    if not text:
        return False
    text = text.strip()
    return text.startswith("http://") or text.startswith("https://")
