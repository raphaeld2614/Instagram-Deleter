# Instagram Deleter

A small Windows desktop app that mass-erases your Instagram interactions. From a
dropdown you choose **what** to erase:

- **Likes** — the posts & reels you've liked (`Your activity → Likes`)
- **Reposts** — the reels you've reposted (`Your activity → Reposts`)

It drives a real Chrome browser (so you log in normally), then repeatedly selects
and removes batches of items. A GUI lets you start and stop at any time, tune the
batch size and pacing, and watch a live log with a running count.

> **Heads-up / disclaimer**
> Automating actions on Instagram is against Instagram's Terms of Service and could
> get your account rate-limited or actioned. Use at your own risk, on your own
> account. Because the app relies on Instagram's web UI, it can break if Instagram
> changes its layout (the app already tries several selectors to stay resilient).

---

## For end users

### Requirements
- **Windows 10/11**
- **Google Chrome** installed ([download](https://www.google.com/chrome/)). The app
  detects Chrome automatically and tells you if it's missing.
- An **internet connection on first run** — the app downloads a matching browser
  driver once and caches it.

### Install & run
- **Installer:** run `InstagramDeleter-Setup.exe` and launch from the Start Menu /
  desktop shortcut, **or**
- **Portable:** unzip `InstagramDeleter.zip` and run `InstagramDeleter.exe`.

### How to use
1. In **What to erase**, choose **Likes** or **Reposts**.
2. Click **1. Open Browser / Log In**. A Chrome window opens on the matching activity page.
3. Log into Instagram if needed. (Your login is saved, so you usually only do this once.)
4. Adjust **Items per batch** and **Delay between batches** if you like.
5. Click **2. Start**. The log shows batches being erased and the **Erased** counter climbs.
6. Click **Stop** at any time. Closing the window stops everything and closes Chrome.

Your settings and login session are stored under
`%LOCALAPPDATA%\InstagramDeleter` (so they persist between runs).

---

## For developers

### Run from source
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unliker        # or: python run_unliker.py
```

### Project layout
```
unliker/
  config.py     # per-user paths, settings, Chrome detection, and the MODES table
  core.py       # UnlikerEngine: the threaded, stoppable, mode-aware Selenium loop
  gui.py        # Tkinter UI (mode dropdown, Start/Stop, settings, live log, counter)
  __main__.py   # `python -m unliker`
run_unliker.py  # PyInstaller entry point
build/
  unliker.spec  # PyInstaller spec (onedir, windowed)
  installer.iss # Inno Setup installer script
  build.ps1     # one-command build
```

> The package directory is still named `unliker/` for continuity; the product is
> "Instagram Deleter". Adding a new erase target is just a new entry in
> `config.MODES` (a label, URL, path token, and the button verb(s) Instagram uses).

### Build a distributable app
```powershell
powershell -ExecutionPolicy Bypass -File build\build.ps1
```
This creates `.venv`, installs deps + PyInstaller, builds
`dist\InstagramDeleter\InstagramDeleter.exe`, then produces
`dist\InstagramDeleter-Setup.exe` (if [Inno Setup](https://jrsoftware.org/isdl.php)
is installed) or `dist\InstagramDeleter.zip` as a fallback.

### Build notes / troubleshooting
- **onedir, not onefile:** `undetected_chromedriver` patches and launches a driver
  binary and is unreliable inside a single-file build, so the spec ships a folder.
- **Python version:** if PyInstaller errors on a very new Python or the Microsoft
  Store build of Python, install a stable [python.org](https://www.python.org/)
  release (3.12 or 3.13), delete `.venv`, and re-run the build script.
- **Chrome / driver version mismatch:** the app detects the installed Chrome version
  and tells `undetected_chromedriver` to download the matching driver; if they still
  disagree it reads the real version from the error and retries once automatically,
  so a driver/Chrome mismatch self-corrects. A first run still needs internet to
  download the matching driver, which is then cached.
- **Reposts button wording:** the Reposts mode assumes Instagram's action/confirm
  button reads "Remove" (it also still matches "Unlike"). If Instagram uses a
  different word, update the `verbs` list for `reposts` in `config.MODES`.
- **SmartScreen:** an unsigned executable may trigger Windows SmartScreen ("More info →
  Run anyway"). Code-signing the exe/installer removes this but is out of scope here.
