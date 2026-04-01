"""TELUS Digital AI handler (telusinternational.ai) — Email OTP login."""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from platforms.base import BasePlatformHandler


class TelusHandler(BasePlatformHandler):
    """Handle TELUS Digital AI job applications.

    TELUS uses email OTP login — fills email, clicks Continue, then pauses
    for the user to enter the OTP code from their email.
    """

    PLATFORM_NAME = "telus"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] TELUS: navigating to job page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        # ── Dismiss cookie popup ────────────────────────────────────
        self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Okay, Got it')]",
            timeout=5,
        )
        time.sleep(1)

        # ── Click "Log in to apply" ─────────────────────────────────
        clicked = self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Log in to apply')]",
            timeout=10,
        )
        if not clicked:
            # Maybe already on login page or redirected
            clicked = self.safe_click(
                By.XPATH,
                "//a[contains(text(),'Log In')]",
                timeout=5,
            )
        if not clicked:
            print("  [!] Could not find login button.")
            return "error"

        self.wait_for_page_load()
        time.sleep(3)

        # ── Fill email on login page ────────────────────────────────
        login_email = self.data.get("login_email", self.data["email"])
        filled = self._fill_email(login_email)
        if not filled:
            print("  [!] Could not fill email field.")
            return "error"

        print(f"  [+] Filled login email: {login_email}")
        time.sleep(1)

        # Click Continue
        self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Continue')]",
            timeout=5,
        )
        time.sleep(2)

        # ── Pause for user to enter OTP ─────────────────────────────
        print("  [i] TELUS sent an OTP to your email. Enter it in the browser.")
        try:
            import pyautogui
            pyautogui.confirm(
                f"TELUS sent an OTP code to {login_email}.\n\n"
                "1. Check your email for the code\n"
                "2. Enter it in the browser\n"
                "3. Click OK here when you're logged in",
                "TELUS OTP - Enter Code",
                ["OK - I'm logged in", "Skip"],
            )
        except Exception:
            input("  Press Enter after entering OTP and logging in...")

        # ── Check if we're now logged in and on the job page ────────
        time.sleep(2)
        current_url = self.driver.current_url
        if "snake" in current_url or "login" in current_url.lower():
            print("  [!] Still on login page — login may have failed.")
            return "error"

        print("  [+] TELUS: logged in successfully.")
        return "filled"

    def _fill_email(self, email: str) -> bool:
        """Fill the email input on the TELUS login page."""
        # Try multiple selectors
        for selector in [
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//label[contains(text(),'Email')]/following::input[1]"),
            (By.XPATH, "//input[@type='text' or @type='email']"),
        ]:
            if self.safe_fill(selector[0], selector[1], email):
                return True
        return False
