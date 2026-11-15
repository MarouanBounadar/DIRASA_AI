import json
import os
import sys

def get_app_dir() -> str:
    """Returns the folder where user data lives (next to the .exe when frozen, else the source folder)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "groq_api_key": "",
    "preferred_provider": "gemini",  # "gemini" or "groq"
    "gemini_model": "gemini-3.5-flash",
    "groq_model": "llama-3.3-70b-versatile",
    "output_language": "Français",     # "Français", "Darija / Arabe", "Anglais", "Mixte (Français/Darija)"
    "output_dir": os.path.join(APP_DIR, "exports"),
    "theme": "dark",
    "color_theme": "blue"
}

def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"Error loading config: {e}")
    
    # Check if environment variables exist
    if not config.get("gemini_api_key") and os.getenv("GEMINI_API_KEY"):
        config["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
    if not config.get("groq_api_key") and os.getenv("GROQ_API_KEY"):
        config["groq_api_key"] = os.getenv("GROQ_API_KEY")

    # Ensure output dir exists
    os.makedirs(config["output_dir"], exist_ok=True)
    return config

def save_config(config_data: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
