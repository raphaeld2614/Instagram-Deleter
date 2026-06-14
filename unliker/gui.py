"""Tkinter GUI for the Instagram Unliker.

The engine runs on a worker thread and reports back through callbacks. Those
callbacks only push messages onto a thread-safe queue; the Tk main loop drains
the queue via root.after(...) and is the *only* place that touches widgets.
"""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from . import config
from .core import ChromeLaunchError, UnlikerEngine

POLL_MS = 100


class UnlikerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.settings = config.load_settings()

        self.engine = UnlikerEngine(
            self.settings,
            log=lambda msg: self.events.put(("log", msg)),
            on_count=lambda total: self.events.put(("count", total)),
            on_state=lambda state: self.events.put(("state", state)),
        )

        self._build_ui()
        self._apply_ui_state("idle")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(POLL_MS, self._poll_events)

        if config.find_chrome() is None:
            self._log(
                "[!] Google Chrome was not detected. Please install it from "
                f"{config.CHROME_DOWNLOAD_URL} before starting."
            )

    # ----------------------------------------------------------------- UI build
    def _build_ui(self) -> None:
        self.root.title(config.APP_DISPLAY_NAME)
        self.root.minsize(560, 560)

        pad = {"padx": 10, "pady": 6}

        # --- Controls row ---
        controls = ttk.Frame(self.root)
        controls.pack(fill="x", **pad)

        self.open_btn = ttk.Button(
            controls, text="1. Open Browser / Log In", command=self._on_open_browser
        )
        self.open_btn.pack(side="left")

        self.start_btn = ttk.Button(controls, text="2. Start", command=self._on_start)
        self.start_btn.pack(side="left", padx=(8, 0))

        self.stop_btn = ttk.Button(controls, text="Stop", command=self._on_stop)
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.count_var = tk.StringVar(value="Erased: 0")
        ttk.Label(controls, textvariable=self.count_var, font=("Segoe UI", 10, "bold")).pack(
            side="right"
        )

        # --- Settings row ---
        settings = ttk.LabelFrame(self.root, text="Settings")
        settings.pack(fill="x", **pad)

        # Row 0: what to erase (mode dropdown). Maps a label back to its mode key.
        ttk.Label(settings, text="What to erase:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self._mode_keys = list(config.MODES.keys())
        mode_labels = [config.MODES[k]["label"] for k in self._mode_keys]
        self.mode_combo = ttk.Combobox(settings, values=mode_labels, state="readonly", width=24)
        current_mode = self.settings.get("mode", config.DEFAULT_MODE)
        if current_mode not in self._mode_keys:
            current_mode = config.DEFAULT_MODE
        self.mode_combo.current(self._mode_keys.index(current_mode))
        self.mode_combo.grid(row=0, column=1, columnspan=5, sticky="w", padx=(0, 8), pady=6)

        # Row 1: batch size + pacing.
        ttk.Label(settings, text="Items per batch:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.batch_var = tk.IntVar(value=int(self.settings["max_items_per_batch"]))
        self.batch_spin = ttk.Spinbox(settings, from_=1, to=20, width=6, textvariable=self.batch_var)
        self.batch_spin.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=6)

        ttk.Label(settings, text="Delay between batches (s):").grid(
            row=1, column=2, sticky="w", padx=8, pady=6
        )
        self.min_delay_var = tk.DoubleVar(value=float(self.settings["min_delay"]))
        self.min_delay_spin = ttk.Spinbox(
            settings, from_=0.5, to=60, increment=0.5, width=6, textvariable=self.min_delay_var
        )
        self.min_delay_spin.grid(row=1, column=3, sticky="w", pady=6)
        ttk.Label(settings, text="to").grid(row=1, column=4, padx=4, pady=6)
        self.max_delay_var = tk.DoubleVar(value=float(self.settings["max_delay"]))
        self.max_delay_spin = ttk.Spinbox(
            settings, from_=0.5, to=120, increment=0.5, width=6, textvariable=self.max_delay_var
        )
        self.max_delay_spin.grid(row=1, column=5, sticky="w", padx=(0, 8), pady=6)

        # --- Status line ---
        self.status_var = tk.StringVar(value="Ready. Click 'Open Browser / Log In' to begin.")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", padx=10)

        # --- Log pane ---
        log_frame = ttk.LabelFrame(self.root, text="Activity log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_widget = scrolledtext.ScrolledText(
            log_frame, height=16, state="disabled", wrap="word", font=("Consolas", 9)
        )
        self.log_widget.pack(fill="both", expand=True, padx=4, pady=4)

    # --------------------------------------------------------------- UI helpers
    def _log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def _set_settings_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.batch_spin, self.min_delay_spin, self.max_delay_spin):
            widget.configure(state=state)
        # A combobox uses "readonly" (not "normal") for its enabled-but-fixed state.
        self.mode_combo.configure(state="readonly" if enabled else "disabled")

    def _apply_ui_state(self, state: str) -> None:
        """Map an engine/UI state to button + settings enablement and a status line."""
        if state == "idle":
            self.open_btn.configure(state="normal")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self._set_settings_enabled(True)
            self.status_var.set("Ready. Click 'Open Browser / Log In' to begin.")
        elif state == "opening":
            self.open_btn.configure(state="disabled")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self._set_settings_enabled(False)
            self.status_var.set("Opening Chrome...")
        elif state == "browser_open":
            self.open_btn.configure(state="disabled")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self._set_settings_enabled(True)
            self.status_var.set("Log in if needed, then click Start.")
        elif state == "running":
            self.open_btn.configure(state="disabled")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self._set_settings_enabled(False)
            self.status_var.set("Running — unliking in progress. Click Stop to halt.")
        elif state == "stopped":
            self.open_btn.configure(state="disabled")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self._set_settings_enabled(True)
            self.status_var.set("Stopped. Click Start to resume, or close the window.")
        elif state == "closing":
            self.open_btn.configure(state="disabled")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self._set_settings_enabled(False)
            self.status_var.set("Closing browser...")

    def _collect_settings(self) -> bool:
        """Read settings from the widgets into self.settings. Returns False if invalid."""
        try:
            batch = int(self.batch_var.get())
            lo = float(self.min_delay_var.get())
            hi = float(self.max_delay_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Invalid settings", "Please enter valid numbers for the settings.")
            return False
        if batch < 1:
            messagebox.showerror("Invalid settings", "Items per batch must be at least 1.")
            return False
        if lo <= 0 or hi <= 0:
            messagebox.showerror("Invalid settings", "Delays must be greater than zero.")
            return False
        if hi < lo:
            lo, hi = hi, lo
        mode_index = self.mode_combo.current()
        if 0 <= mode_index < len(self._mode_keys):
            self.settings["mode"] = self._mode_keys[mode_index]
        self.settings["max_items_per_batch"] = batch
        self.settings["min_delay"] = lo
        self.settings["max_delay"] = hi
        config.save_settings(self.settings)
        return True

    # ------------------------------------------------------------ button actions
    def _on_open_browser(self) -> None:
        if config.find_chrome() is None:
            messagebox.showerror(
                "Chrome not found",
                "Google Chrome was not found on this computer.\n\n"
                f"Please install it from {config.CHROME_DOWNLOAD_URL} and try again.",
            )
            return
        if not self._collect_settings():
            return
        self._apply_ui_state("opening")

        def worker():
            try:
                self.engine.open_browser()  # pushes state "browser_open" on success
            except ChromeLaunchError as exc:
                self.events.put(("error", str(exc)))
                self.events.put(("state", "idle"))

        threading.Thread(target=worker, name="OpenBrowser", daemon=True).start()

    def _on_start(self) -> None:
        if not self._collect_settings():
            return
        self.engine.settings = self.settings
        self.engine.start()  # pushes state "running"

    def _on_stop(self) -> None:
        self.stop_btn.configure(state="disabled")
        self.status_var.set("Stopping — finishing the current step...")
        self.engine.stop()

    # ----------------------------------------------------------------- shutdown
    def _on_close(self) -> None:
        if self.engine.is_running:
            if not messagebox.askokcancel("Quit", "Unliking is running. Stop and quit?"):
                return
        self._apply_ui_state("closing")

        def worker():
            self.engine.shutdown()
            self.events.put(("closed", None))

        threading.Thread(target=worker, name="Shutdown", daemon=True).start()

    # -------------------------------------------------------------- event drain
    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "count":
                    self.count_var.set(f"Erased: {payload}")
                elif kind == "state":
                    self._apply_ui_state(payload)
                elif kind == "error":
                    messagebox.showerror("Error", payload)
                elif kind == "closed":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll_events)


def main() -> None:
    root = tk.Tk()
    UnlikerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
