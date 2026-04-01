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
            if "page cannot be found" in page_text or "404" in self.driver.title or "not found" in page_text:
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
            timeout=10,
        )
        if not clicked:
            # Try the nav link
            clicked = self.safe_click(
                By.XPATH,
                "//a[contains(text(),'Log In')]",
                timeout=3,
            )
        if not clicked:
            # Try JS fallback — only match specific button/link text
            clicked = self.driver.execute_script("""
                const els = document.querySelectorAll('button, a');
                for (const el of els) {
                    const text = el.textContent.trim().toLowerCase();
                    if (text === 'log in to apply' || text === 'log in / sign up'
                        || text === 'log in' || text === 'sign up') {
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

        # ── Verify we're on the login page ──────────────────────────
        current_url = self.driver.current_url.lower()
        if "snake" not in current_url and "login" not in current_url:
            print("  [!] Did not navigate to login page.")
            return "error"

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
            timeout=10,
        )
        time.sleep(2)

        # ── Poll for OTP completion (user enters code in browser) ───
        print(f"  [i] TELUS sent OTP to {login_email}. Enter it in browser. Polling 120s...")
        for countdown in range(24):  # 24 * 5 = 120 seconds
            time.sleep(5)
            current_url = self.driver.current_url
            if "snake" not in current_url and "login" not in current_url.lower():
                print("  [+] TELUS: logged in successfully.")
                return "filled"
            remaining = 120 - (countdown + 1) * 5
            if remaining > 0 and remaining % 30 == 0:
                print(f"  [i] Still waiting for OTP... {remaining}s remaining")

        print("  [!] TELUS OTP timeout after 120s.")
        return "manual"

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
