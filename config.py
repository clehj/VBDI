import json
import logging
import sys
from pathlib import Path


logger = logging.getLogger("config")


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_FILE = _app_dir() / "config.json"

DEFAULT_CONFIG = {
    "version": 1,
    "default_volume": 100,
    "default_folder": "",
    "window_width": 960,
    "window_height": 640,
    "log_enabled": False,
    "check_update": True,
    "decoder_preference": "auto",   # auto / software / hardware
    "recent_files": [],
    "max_recent": 10,
}


class Config:
    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        if not CONFIG_FILE.exists():
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"config.load_failed: {e}")
            return

        for key, default_value in DEFAULT_CONFIG.items():
            value = data.get(key, default_value)
            if type(value) is not type(default_value):
                if isinstance(default_value, int) and isinstance(value, (int, float)):
                    value = int(value)
                else:
                    continue
            self._data[key] = value
        logger.info(f"config.loaded path={CONFIG_FILE}")

    def save(self):
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"config.save_failed: {e}")

    def get(self, key):
        return self._data.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self._data[key] = value

    def add_recent(self, path: str):
        try:
            resolved = str(Path(path).resolve())
        except Exception:
            return
        recent = list(self._data.get("recent_files") or [])
        if resolved in recent:
            recent.remove(resolved)
        recent.insert(0, resolved)
        max_n = int(self._data.get("max_recent", 10))
        self._data["recent_files"] = recent[:max_n]
        self.save()

    def clear_recent(self):
        self._data["recent_files"] = []
        self.save()