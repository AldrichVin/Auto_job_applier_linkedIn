"""TELUS Digital AI handler (telusinternational.ai) — Email OTP login."""

import time

from selenium.webdriver.common.by import By

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

        # ── Check for 404 ──────────────────────────────────────────
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "page cannot be found" in page_text or "404" in self.driver.title:
                print("  [!] Page not found (404).")
                return "error"
        except Exception:
            pass

        # ── Dismiss cookie popup (may not be present) ───────────────
        self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Okay, Got it')]",
            timeout=3,
        )
        time.sleep(0.5)

        # ── Click "Log in to apply" ─────────────────────────────────
        clicked = self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Log in to apply')]",
            timeout=5,
        )
        if not clicked:
            # Try the nav link
            clicked = self.safe_click(
                By.XPATH,
                "//a[contains(text(),'Log In')]",
                timeout=3,
            )
        if not clicked:
            # Try JS fallback
            clicked = self.driver.execute_script("""
                const els = document.querySelectorAll('button, a');
                for (const el of els) {
                    const text = el.textContent.trim().toLowerCase();
                    if (text.includes('log in') || text.includes('apply')) {
                        el.click();
                        return true;
                    }
                }
                return false;
            """)
        if not clicked:
            print("  [!] Could not find login/apply button.")
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
            result = pyautogui.confirm(
                f"TELUS sent an OTP code to {login_email}.\n\n"
                "1. Check your email for the code\n"
                "2. Enter it in the browser\n"
                "3. Click OK here when you're logged in",
                "TELUS OTP - Enter Code",
                ["OK - I'm logged in", "Skip"],
            )
            if result == "Skip":
                return "manual"
        except Exception:
            input("  Press Enter after entering OTP and logging in...")

        time.sleep(2)
        print("  [+] TELUS: login flow completed.")
        return "filled"

    def _fill_email(self, email: str) -> bool:
        """Fill the email input on the TELUS login page."""
        for selector in [
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//label[contains(text(),'Email')]/following::input[1]"),
            (By.XPATH, "//input[@type='text' or @type='email']"),
        ]:
            if self.safe_fill(selector[0], selector[1], email):
                return True
        return False
