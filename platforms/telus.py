"""TELUS Digital AI handler (telusinternational.ai) — Email OTP login."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class TelusHandler(BasePlatformHandler):
    """Handle TELUS Digital AI job applications.

    TELUS uses email OTP login — fills email but user must enter the code manually.
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
            print("  [!] Could not find 'Log in to apply' button.")
            return "error"

        self.wait_for_page_load()
        time.sleep(3)

        # ── Fill email on login page ────────────────────────────────
        login_email = self.data.get("login_email", self.data["email"])
        filled = self.safe_fill(
            By.CSS_SELECTOR,
            "input[type='email'], input[placeholder*='email' i], input[name*='email' i]",
            login_email,
        )
        if not filled:
            # Try by label
            filled = self.safe_fill(
                By.XPATH,
                "//input[@type='text' or @type='email']",
                login_email,
            )

        if filled:
            print(f"  [+] Filled login email: {login_email}")
            time.sleep(1)

            # Click Continue
            self.safe_click(
                By.XPATH,
                "//button[contains(text(),'Continue')]",
                timeout=5,
            )
            time.sleep(2)
            print("  [i] TELUS uses Email OTP — user must enter code manually.")
        else:
            print("  [!] Could not fill email field.")
            return "error"

        return "manual"
