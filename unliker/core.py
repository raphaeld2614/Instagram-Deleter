"""The unliking engine: the original Selenium logic refactored into a threaded,
stoppable, GUI-friendly class.

Compared to the original CLI script the behavioural changes are:
  * print() -> self.log() (routed to a callback, e.g. the GUI log pane)
  * the input() "press Enter to begin" gate -> open_browser() + a separate start
  * Ctrl+C / KeyboardInterrupt -> a threading.Event checked each loop and during sleeps
  * the Chrome user-data-dir lives in a stable per-user folder (config.PROFILE_DIR)
The XPath selectors and the net-casting grid logic are preserved verbatim.
"""

import random
import threading
import time

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from . import config

# --- UI XPATH SELECTORS ---
# Select/Cancel are the same across content types; the action + confirm buttons
# differ by mode (e.g. "Unlike" for likes vs "Remove" for reposts), so they are
# built from the active mode's verbs by build_action_xpaths().
SELECT_BUTTON_XPATH = "//*[text()='Select']"
CANCEL_BUTTON_XPATH = "//*[text()='Cancel']"


def build_action_xpaths(verbs):
    """Build the bottom action-bar and confirm-dialog XPaths for the given verbs.

    Matching any of `verbs` lets the same loop work whether Instagram labels the
    action "Unlike" or "Remove".
    """
    bottom = " | ".join(
        f"//div[@role='button']//*[contains(text(), '{verb}')]" for verb in verbs
    )
    confirm = " | ".join(
        f"//*[@role='dialog']//button[contains(text(), '{verb}')] "
        f"| //*[@role='dialog']//*[text()='{verb}']"
        for verb in verbs
    )
    return bottom, confirm


# The bot tries these one by one until it finds the thumbnails.
GRID_ITEM_XPATHS = [
    "//*[@aria-label='Image with button']",                       # Most common on modern accounts
    "//div[@role='checkbox']",                                    # Selection circles
    "//div[contains(@aria-label, 'Image') and @role='button']",  # Alternate image wrapper
    "//img/ancestor::div[@role='button'][1]",                     # Fallback: image inside clickable box
]


class ChromeLaunchError(Exception):
    """Raised when the browser cannot be started (Chrome missing / version mismatch)."""


class UnlikerEngine:
    """Drives the unlike loop. Owns the Selenium driver and a stop flag.

    Callbacks (all optional, all called from the worker thread):
      log(message: str)      -> append a line to the UI log
      on_count(total: int)   -> report cumulative items unliked
      on_state(state: str)   -> one of: "idle", "browser_open", "running", "stopped"
    """

    def __init__(self, settings: dict, log=None, on_count=None, on_state=None):
        self.settings = settings
        self._log_cb = log
        self._on_count = on_count
        self._on_state = on_state

        self.driver = None
        self._stop_event = threading.Event()
        self._thread = None
        self.total_erased = 0

    # ------------------------------------------------------------------ helpers
    def log(self, message: str) -> None:
        if self._log_cb:
            self._log_cb(message)
        else:
            print(message)

    def _set_state(self, state: str) -> None:
        if self._on_state:
            self._on_state(state)

    def _sleep(self, min_seconds: float, max_seconds: float) -> None:
        """Interruptible jittered sleep. Returns immediately once stop is requested."""
        duration = random.uniform(min_seconds, max_seconds)
        # wait() returns True the moment the event is set, so Stop is responsive.
        self._stop_event.wait(duration)

    def _between_batch_sleep(self) -> None:
        lo = float(self.settings.get("min_delay", config.DEFAULT_SETTINGS["min_delay"]))
        hi = float(self.settings.get("max_delay", config.DEFAULT_SETTINGS["max_delay"]))
        if hi < lo:
            lo, hi = hi, lo
        self._sleep(lo, hi)

    @property
    def mode(self) -> dict:
        return config.get_mode(self.settings.get("mode", config.DEFAULT_MODE))

    @property
    def target_url(self) -> str:
        return self.mode["url"]

    @property
    def path_token(self) -> str:
        return self.mode["path_token"]

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ browser
    def open_browser(self) -> None:
        """Launch the stealth Chrome session and navigate to the likes page.

        Raises ChromeLaunchError with a friendly message on failure.
        """
        if config.find_chrome() is None:
            raise ChromeLaunchError(
                "Google Chrome was not found on this computer.\n\n"
                f"Please install Chrome from {config.CHROME_DOWNLOAD_URL} and try again."
            )

        config.ensure_dirs()
        self.log("[*] Booting up stealth browser...")
        try:
            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={config.PROFILE_DIR}")
            options.add_argument(
                f"--window-size={random.randint(1000, 1200)},{random.randint(800, 1000)}"
            )
            # Force English so the text-based selectors ('Select'/'Cancel') don't break.
            options.add_argument("--lang=en-US")
            # use_subprocess=False avoids UC re-spawning the (frozen) executable as a
            # child process, which would otherwise relaunch the whole GUI.
            self.driver = uc.Chrome(options=options, use_subprocess=False)
        except Exception as exc:  # noqa: BLE001 - surface any launch failure to the UI
            raise ChromeLaunchError(self._describe_launch_error(exc)) from exc

        self.driver.get(self.target_url)
        self.log("[*] Browser ready. Log in if needed and make sure you're on the 'Likes' page.")
        self._set_state("browser_open")

    @staticmethod
    def _describe_launch_error(exc: Exception) -> str:
        text = str(exc)
        if "version" in text.lower() and "chrome" in text.lower():
            return (
                "Chrome and the driver versions don't match.\n\n"
                "This usually fixes itself on the next launch. If it persists, update "
                "Google Chrome to the latest version and try again.\n\n"
                f"Details: {text}"
            )
        return f"Could not start Chrome.\n\nDetails: {text}"

    # ------------------------------------------------------------------ control
    def start(self) -> None:
        """Begin the unlike loop on a background thread."""
        if self.driver is None:
            raise RuntimeError("open_browser() must be called before start().")
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="UnlikerLoop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Request the loop to halt (returns immediately; loop ends within a cycle)."""
        self._stop_event.set()

    def shutdown(self) -> None:
        """Stop the loop and close the browser. Safe to call multiple times."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
            self._thread = None
        if self.driver is not None:
            self.log("[*] Closing browser session.")
            try:
                self.driver.quit()
            except Exception:  # noqa: BLE001 - driver may already be gone
                pass
            self.driver = None
        self._set_state("idle")

    # ------------------------------------------------------------------ the loop
    def _run(self) -> None:
        self._set_state("running")
        self.log("[*] Started. Click Stop at any time to halt.")
        try:
            while not self._stop_event.is_set():
                success = self.process_page()

                if self._stop_event.is_set():
                    break

                if not success:
                    self.log("[*] Retrying in a few seconds...")
                    self._sleep(3.0, 5.0)

                if self.driver and self.path_token in self.driver.current_url:
                    self.log("[*] Reloading page for the next batch...")
                    self.driver.refresh()

                self._between_batch_sleep()
        except Exception as exc:  # noqa: BLE001 - never let the thread die silently
            self.log(f"[!] Loop stopped due to an unexpected error: {exc}")
        finally:
            self.log("[-] Stopped.")
            self._set_state("stopped")

    def get_grid_items(self):
        """Cast a wide net to find grid items across possible Instagram layouts."""
        for xpath in GRID_ITEM_XPATHS:
            items = self.driver.find_elements(By.XPATH, xpath)
            if len(items) > 0:
                self.log(f"    -> [Success] Found {len(items)} items using selector: {xpath}")
                return items
        return []

    def process_page(self) -> bool:
        self.log("\n[*] Starting new batch...")
        wait = WebDriverWait(self.driver, 10)
        short_wait = WebDriverWait(self.driver, 3)
        actions = ActionChains(self.driver)

        verbs = self.mode["verbs"]
        primary_verb = verbs[0]
        bottom_action_xpath, confirm_action_xpath = build_action_xpaths(verbs)

        if self.path_token not in self.driver.current_url:
            self.log("[!] Not on the target page. Navigating back...")
            self.driver.get(self.target_url)
            self._sleep(3, 5)
            return False

        try:
            # Step 1: Click "Select" and verify we entered selection mode.
            self.log("    -> Looking for 'Select' button...")
            try:
                select_btn = wait.until(
                    EC.presence_of_element_located((By.XPATH, SELECT_BUTTON_XPATH))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", select_btn)
                actions.move_to_element(select_btn).pause(0.5).click().perform()
            except TimeoutException:
                self.log("    [?] 'Select' button missing. We might already be in selection mode.")

            try:
                short_wait.until(EC.presence_of_element_located((By.XPATH, CANCEL_BUTTON_XPATH)))
                self.log("    -> Selection mode verified!")
            except TimeoutException:
                self.log("    [!] Failed to enter selection mode. Retrying next loop...")
                return False

            self._sleep(1.5, 2.5)
            if self._stop_event.is_set():
                return False

            # Step 2: Find items via the net-casting helper.
            self.log("    -> Scanning for items to erase...")
            items = self.get_grid_items()
            if not items:
                self.log("[!] No items found. Instagram may be loading slowly, or you're out of items.")
                return False

            max_items = int(
                self.settings.get(
                    "max_items_per_batch", config.DEFAULT_SETTINGS["max_items_per_batch"]
                )
            )
            items_to_process = items[:max_items]
            self.log(f"    -> Clicking {len(items_to_process)} items...")

            # Step 3: Click each item.
            selected_count = 0
            for item in items_to_process:
                if self._stop_event.is_set():
                    return False
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", item
                    )
                    self._sleep(0.3, 0.8)
                    actions.move_to_element(item).pause(0.2).click().perform()
                    selected_count += 1
                    self._sleep(0.5, 1.2)
                except Exception as exc:  # noqa: BLE001 - one bad item shouldn't abort the batch
                    self.log(f"    [!] Couldn't click an item: {exc}")

            if selected_count == 0:
                return False

            # Step 4: Click the bottom action button (e.g. "Unlike"/"Remove").
            self.log(f"    -> Clicking bottom '{primary_verb} ({selected_count})' button...")
            bottom_action = wait.until(
                EC.presence_of_element_located((By.XPATH, bottom_action_xpath))
            )
            actions.move_to_element(bottom_action).pause(0.5).click().perform()
            self._sleep(1.0, 2.0)

            # Step 5: Confirm in the dialog.
            self.log(f"    -> Confirming '{primary_verb}' in popup dialog...")
            confirm_action = wait.until(
                EC.presence_of_element_located((By.XPATH, confirm_action_xpath))
            )
            actions.move_to_element(confirm_action).pause(0.5).click().perform()

            self.total_erased += selected_count
            if self._on_count:
                self._on_count(self.total_erased)
            self.log("[#] Batch erased successfully!")
            self._sleep(3.0, 5.0)
            return True

        except TimeoutException:
            self.log("[!] Timed out waiting for UI buttons. Retrying...")
            return False
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on unexpected errors
            self.log(f"[!] An unexpected error occurred: {exc}")
            return False
