"""Application paths, persisted settings, and Chrome detection.

Everything user-writable lives under %LOCALAPPDATA%\\InstagramUnliker so that the
login session survives across runs even when the app is a frozen PyInstaller exe
(where the executable's own directory is read-only / a temp extraction dir).
"""

import json
import os
import shutil
from pathlib import Path

APP_NAME = "InstagramEraser"        # used for the per-user data folder name
APP_DISPLAY_NAME = "Instagram Eraser"  # shown in the window title / installer
CHROME_DOWNLOAD_URL = "https://www.google.com/chrome/"

# Each "erase mode" maps a dropdown choice to its Instagram activity page and the
# button verb(s) Instagram uses for that content type. `verbs` lists every label
# the action/confirm button might show; the selectors are built from this list so
# they still work even though the reposts UI says "Remove" rather than "Unlike".
MODES = {
    "likes": {
        "label": "Likes (posts & reels)",
        "url": "https://www.instagram.com/your_activity/interactions/likes/",
        "path_token": "interactions/likes",
        "verbs": ["Unlike"],
    },
    "reposts": {
        "label": "Reposts (reels)",
        "url": "https://www.instagram.com/your_activity/interactions/reposts/",
        "path_token": "interactions/reposts",
        "verbs": ["Remove", "Unlike"],
    },
}
DEFAULT_MODE = "likes"

DEFAULT_SETTINGS = {
    "mode": DEFAULT_MODE,
    "max_items_per_batch": 8,
    # Seconds to wait between batches. A wider/larger range looks more human and
    # is gentler on rate limits. The small per-action jitter is fixed in core.py.
    "min_delay": 4.0,
    "max_delay": 7.0,
}


def get_mode(mode_key: str) -> dict:
    """Return the mode config for a key, falling back to the default mode."""
    return MODES.get(mode_key, MODES[DEFAULT_MODE])


def _app_dir() -> Path:
    """Stable, per-user, writable application directory."""
    base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / APP_NAME


APP_DIR = _app_dir()
PROFILE_DIR = APP_DIR / "chrome_profile"
SETTINGS_FILE = APP_DIR / "settings.json"


def ensure_dirs() -> None:
    """Create the app + profile directories if they do not exist yet."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    """Load settings.json, falling back to defaults for any missing keys."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            settings.update({k: stored[k] for k in DEFAULT_SETTINGS if k in stored})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return settings


def save_settings(settings: dict) -> None:
    """Persist the known settings keys to settings.json."""
    ensure_dirs()
    to_store = {k: settings.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(to_store, fh, indent=2)


def find_chrome() -> str | None:
    """Return the path to an installed Google Chrome, or None if not found.

    Checks PATH, the standard install locations, and the Windows registry's
    App Paths entry. undetected_chromedriver needs a real Chrome binary present.
    """
    # 1) On PATH (rare on Windows, common elsewhere).
    for name in ("chrome", "chrome.exe", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found

    # 2) Standard Windows install locations.
    candidates = []
    for env_var in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        base = os.getenv(env_var)
        if base:
            candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    # 3) Windows registry App Paths (covers non-standard installs).
    try:
        import winreg  # noqa: PLC0415 - Windows-only, imported lazily

        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                    root,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                ) as key:
                    path, _ = winreg.QueryValueEx(key, None)
                    if path and Path(path).is_file():
                        return path
            except OSError:
                continue
    except ImportError:
        pass

    return None
