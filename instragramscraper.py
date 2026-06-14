import os
import time
import sys
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

# Configuration
TARGET_URL = "https://www.instagram.com/your_activity/interactions/likes/"
MAX_ITEMS_PER_BATCH = 8  

# --- UI XPATH SELECTORS ---
SELECT_BUTTON_XPATH = "//*[text()='Select']"
CANCEL_BUTTON_XPATH = "//*[text()='Cancel']"
BOTTOM_UNLIKE_BUTTON_XPATH = "//div[@role='button']//*[contains(text(), 'Unlike')]"
CONFIRM_UNLIKE_BUTTON_XPATH = "//*[@role='dialog']//button[contains(text(), 'Unlike')] | //*[@role='dialog']//*[text()='Unlike']"

# --- THE NEW NET-CASTING GRID SELECTORS ---
# The bot will try these one by one until it finds the thumbnails
GRID_ITEM_XPATHS = [
    "//*[@aria-label='Image with button']",            # Most common on modern accounts
    "//div[@role='checkbox']",                         # Looks directly for the selection circles
    "//div[contains(@aria-label, 'Image') and @role='button']", # Alternate image wrapper
    "//img/ancestor::div[@role='button'][1]"           # Fallback: Finds images inside clickable boxes
]

def setup_stealth_driver():
    options = uc.ChromeOptions()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    profile_path = os.path.join(current_dir, "instagram_profile")
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument(f"--window-size={random.randint(1000, 1200)},{random.randint(800, 1000)}")
    
    # Force language to English so the text-based Selectors ('Select', 'Cancel') don't break
    options.add_argument("--lang=en-US") 
    
    driver = uc.Chrome(options=options)
    return driver

def random_delay(min_seconds=1.0, max_seconds=3.0):
    time.sleep(random.uniform(min_seconds, max_seconds))

def get_grid_items(driver):
    """Casts a wide net to find the grid items using multiple possible Instagram layouts."""
    for xpath in GRID_ITEM_XPATHS:
        items = driver.find_elements(By.XPATH, xpath)
        if len(items) > 0:
            print(f"    -> [Success] Found {len(items)} items using selector: {xpath}")
            return items
    return []

def process_page(driver):
    print("\n[*] Starting new batch...")
    wait = WebDriverWait(driver, 10)
    short_wait = WebDriverWait(driver, 3) 
    actions = ActionChains(driver)
    
    if "interactions/likes" not in driver.current_url:
        print("[!] Not on the likes page. Navigating back...")
        driver.get(TARGET_URL)
        random_delay(3, 5)
        return False
    
    try:
        # Step 1: Click "Select" and VERIFY we entered selection mode
        print("    -> Looking for 'Select' button...")
        try:
            select_btn = wait.until(EC.presence_of_element_located((By.XPATH, SELECT_BUTTON_XPATH)))
            driver.execute_script("arguments[0].scrollIntoView(true);", select_btn)
            actions.move_to_element(select_btn).pause(0.5).click().perform()
        except TimeoutException:
            print("    [?] 'Select' button missing. We might already be in selection mode.")

        # Verification step
        try:
            short_wait.until(EC.presence_of_element_located((By.XPATH, CANCEL_BUTTON_XPATH)))
            print("    -> Selection mode verified!")
        except TimeoutException:
            print("    [!] Failed to enter selection mode. Retrying next loop...")
            return False

        random_delay(1.5, 2.5)
            
        # Step 2: Find items using our new net-casting function
        print("    -> Scanning for liked posts/reels...")
        items = get_grid_items(driver)
        
        if not items:
            print("[!] No items found. Instagram might be loading slowly, or you are out of likes.")
            return False
            
        items_to_process = items[:MAX_ITEMS_PER_BATCH]
        print(f"    -> Clicking {len(items_to_process)} items...")

        # Step 3: Click each item
        selected_count = 0
        for item in items_to_process:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)
                random_delay(0.3, 0.8)
                actions.move_to_element(item).pause(0.2).click().perform()
                selected_count += 1
                random_delay(0.5, 1.2)
            except Exception as e:
                print(f"    [!] Couldn't click an item: {e}")
                
        if selected_count == 0:
            return False

        # Step 4: Click Bottom "Unlike"
        print(f"    -> Clicking bottom 'Unlike ({selected_count})' button...")
        bottom_unlike = wait.until(EC.presence_of_element_located((By.XPATH, BOTTOM_UNLIKE_BUTTON_XPATH)))
        actions.move_to_element(bottom_unlike).pause(0.5).click().perform()
        random_delay(1.0, 2.0)

        # Step 5: Confirm "Unlike"
        print("    -> Confirming Unlike in popup dialog...")
        confirm_unlike = wait.until(EC.presence_of_element_located((By.XPATH, CONFIRM_UNLIKE_BUTTON_XPATH)))
        actions.move_to_element(confirm_unlike).pause(0.5).click().perform()
        
        print("[#] Batch unliked successfully!")
        random_delay(3.0, 5.0) 
        return True

    except TimeoutException:
        print("[!] Timed out waiting for UI buttons. Retrying...")
        return False
    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        return False

def main():
    print("[*] Booting up stealth browser...")
    driver = setup_stealth_driver()
    print("[*] Browser initialized. Press CTRL + C to stop at any time.")
    
    try:
        driver.get(TARGET_URL)
        input("[?] Log in if needed, ensure you are on the 'Likes' page, then press Enter to begin...")

        while True:
            success = process_page(driver)
            
            if not success:
                print("[*] Retrying in a few seconds...")
                random_delay(3.0, 5.0)
            
            if "interactions/likes" in driver.current_url:
                print("[*] Reloading page for the next batch...")
                driver.refresh()
            
            random_delay(4.0, 7.0)

    except KeyboardInterrupt:
        print("\n[-] Stop signal received. Exiting gracefully...")
    finally:
        print("[*] Closing browser session.")
        driver.quit()
        sys.exit(0)

if __name__ == "__main__":
    main()