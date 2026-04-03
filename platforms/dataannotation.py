"""DataAnnotation handler (app.dataannotation.tech) — Typeform signup."""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from platforms.base import BasePlatformHandler


class DataAnnotationHandler(BasePlatformHandler):
    """Fill the Typeform signup on DataAnnotation."""

    PLATFORM_NAME = "dataannotation"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] DataAnnotation: navigating to signup page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        # ── Click "Continue with Email" ─────────────────────────────
        clicked = self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Continue with Email')]",
            timeout=10,
        )
        if not clicked:
            print("  [!] Could not find 'Continue with Email' button.")
            return "error"

        time.sleep(3)

        # ── The Typeform is inside an iframe ─────────────────────────
        filled = self._fill_typeform_signup()

        print(f"  [+] DataAnnotation: filled {filled} fields.")
        return "filled" if filled >= 3 else "error"

    def _fill_typeform_signup(self) -> int:
        """Fill the 4-step Typeform: email → first name → last name → phone."""
        filled = 0

        # Switch to the Typeform iframe
        try:
            iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe[src*='typeform']")
            self.driver.switch_to.frame(iframe)
        except Exception as exc:
            print(f"  [!] Could not find Typeform iframe: {exc}")
            return 0

        try:
            # Step 1: Email
            if self._fill_and_advance(self.data.get("login_email", self.data["email"])):
                filled += 1
                print("  [+] Filled email.")

            # Step 2: First name
            if self._fill_and_advance(self.data["first_name"]):
                filled += 1
                print("  [+] Filled first name.")

            # Step 3: Last name
            if self._fill_and_advance(self.data["last_name"]):
                filled += 1
                print("  [+] Filled last name.")

            # Step 4: Phone — fill but highlight Submit, don't click
            time.sleep(1)
            phone = self.data.get("phone", "")
            phone_filled = self.driver.execute_script("""
                const inputs = document.querySelectorAll('input[type="tel"], input[placeholder*="Phone"]');
                for (const inp of inputs) {
                    if (inp.offsetParent !== null) {
                        inp.value = arguments[0];
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            """, phone)
            if phone_filled:
                filled += 1
                print("  [+] Filled phone number.")

            # AI fallback for remaining unknown fields
            self.fill_unknown_fields()

            # Highlight Submit button
            self.driver.execute_script("""
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.toLowerCase().includes('submit')) {
                        btn.style.border = '4px solid red';
                        btn.style.boxShadow = '0 0 15px red';
                    }
                }
            """)
            print("  [+] Highlighted Submit button (NOT clicking).")

        finally:
            self.driver.switch_to.default_content()

        return filled

    def _fill_and_advance(self, value: str) -> bool:
        """Fill the current visible input and press Enter/click OK to advance."""
        try:
            time.sleep(1.5)

            # Fill via JS to handle React inputs
            filled = self.driver.execute_script("""
                const inputs = document.querySelectorAll(
                    'input[type="text"], input[type="email"], input:not([type])'
                );
                for (const inp of inputs) {
                    if (inp.offsetParent !== null && inp.type !== 'hidden') {
                        // Clear and set value
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeInputValueSetter.call(inp, arguments[0]);
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        inp.focus();
                        return true;
                    }
                }
                return false;
            """, value)

            if not filled:
                return False

            time.sleep(0.5)

            # Click the OK/Next button via JS
            advanced = self.driver.execute_script("""
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent.toLowerCase();
                    if ((text.includes('ok') || text.includes('next')) && btn.offsetParent !== null) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            """)

            if not advanced:
                # Fallback: press Enter on the input
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")
                for inp in inputs:
                    if inp.is_displayed():
                        inp.send_keys(Keys.RETURN)
                        break

            time.sleep(1.5)
            return True

        except Exception as exc:
            print(f"  [!] Typeform step error: {exc}")
            return False
