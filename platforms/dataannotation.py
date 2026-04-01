"""DataAnnotation handler (app.dataannotation.tech) — Typeform signup."""

import time

from selenium.webdriver.common.by import By

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

        time.sleep(2)

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
            if self._fill_typeform_step("email", self.data["email"]):
                filled += 1

            # Step 2: First name
            if self._fill_typeform_step("answer", self.data["first_name"]):
                filled += 1

            # Step 3: Last name
            if self._fill_typeform_step("answer", self.data["last_name"]):
                filled += 1

            # Step 4: Phone — highlight Submit but don't click
            phone = self.data.get("phone", "")
            try:
                phone_input = self.driver.find_element(
                    By.CSS_SELECTOR, "input[type='tel'], input[placeholder*='Phone']"
                )
                phone_input.clear()
                phone_input.send_keys(phone)
                filled += 1
                print("  [+] Filled phone number.")
                time.sleep(1)

                # Highlight the Submit button
                try:
                    submit_btn = self.driver.find_element(
                        By.XPATH, "//button[contains(text(),'Submit')]"
                    )
                    self.driver.execute_script(
                        "arguments[0].style.border = '4px solid red'; "
                        "arguments[0].style.boxShadow = '0 0 15px red';",
                        submit_btn,
                    )
                    print("  [+] Highlighted Submit button (NOT clicking).")
                except Exception:
                    pass
            except Exception as exc:
                print(f"  [!] Phone step error: {exc}")

        finally:
            # Switch back to main content
            self.driver.switch_to.default_content()

        return filled

    def _fill_typeform_step(self, input_hint: str, value: str) -> bool:
        """Fill a single Typeform step and click OK/Next."""
        try:
            time.sleep(1)

            # Find the visible text input
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email']")
            target = None
            for inp in inputs:
                if inp.is_displayed():
                    target = inp
                    break

            if not target:
                print(f"  [!] No visible input found for step '{input_hint}'.")
                return False

            target.clear()
            target.send_keys(value)
            time.sleep(0.5)

            # Click OK / Next button
            ok_clicked = False
            for xpath in [
                "//button[contains(text(),'OK')]",
                "//button[contains(text(),'Next')]",
            ]:
                try:
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    for btn in buttons:
                        if btn.is_displayed():
                            btn.click()
                            ok_clicked = True
                            break
                except Exception:
                    continue
                if ok_clicked:
                    break

            if ok_clicked:
                time.sleep(1.5)
                return True

            print(f"  [!] Could not click OK/Next for step '{input_hint}'.")
            return False

        except Exception as exc:
            print(f"  [!] Typeform step error for '{input_hint}': {exc}")
            return False
