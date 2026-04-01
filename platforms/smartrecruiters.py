"""SmartRecruiters handler (jobs.smartrecruiters.com).

SmartRecruiters uses web components with shadow DOM (spl-input, spl-autocomplete,
spl-phone-field, spl-dropzone). Standard Selenium find_element cannot reach these
inputs — all interaction must go through execute_script with shadowRoot traversal.

Note: SmartRecruiters has aggressive bot detection. If a CAPTCHA appears,
the handler pauses for the user to solve it manually.
"""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from platforms.base import BasePlatformHandler


class SmartRecruitersHandler(BasePlatformHandler):
    """Fill application forms on SmartRecruiters-hosted career pages."""

    PLATFORM_NAME = "smartrecruiters"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] SmartRecruiters: navigating...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        # Check if we're on job description page — click "I'm interested"
        if not self._is_application_form():
            if self._click_apply_button():
                time.sleep(4)
                self.wait_for_page_load()
            else:
                print("  [!] Could not find Apply button.")
                return "error"

        # Check for CAPTCHA
        if self._is_captcha_page():
            print("  [!] CAPTCHA detected — waiting up to 60s for manual solve...")
            self._wait_for_captcha_solve(timeout=60)
            if self._is_captcha_page():
                self.take_screenshot("smartrecruiters", "captcha")
                return "manual"

        time.sleep(2)

        # Fill the form via shadow DOM JS
        filled = self._fill_shadow_fields()

        # Fill city autocomplete
        filled += self._fill_city()

        # Upload resume
        self._upload_resume()

        # Fill unknown fields via AI
        self.fill_unknown_fields(job_info)

        self.take_screenshot("smartrecruiters", "filled")

        # Highlight Next/Submit button without clicking
        self._highlight_action_button()

        print(f"  [+] SmartRecruiters: filled {filled} fields.")
        return "filled" if filled >= 3 else "error"

    def _is_application_form(self) -> bool:
        """Check if we're on the application form (oneclick-ui)."""
        url = self.driver.current_url.lower()
        if "oneclick-ui" in url:
            return True
        return bool(self.driver.execute_script(
            "return !!document.querySelector('oc-oneclick-form, oc-oneclick-form-root');"
        ))

    def _is_captcha_page(self) -> bool:
        """Check if a CAPTCHA/verification page is showing."""
        try:
            text = self.driver.execute_script("return (document.body.innerText || '').toLowerCase();")
            return "verification required" in text or "slide right" in text
        except Exception:
            return False

    def _wait_for_captcha_solve(self, timeout: int = 60) -> None:
        """Poll until CAPTCHA is solved or timeout."""
        for _ in range(timeout // 5):
            time.sleep(5)
            if not self._is_captcha_page():
                print("  [+] CAPTCHA solved.")
                return

    def _click_apply_button(self) -> bool:
        """Click 'I'm interested' or similar apply button on job description page."""
        return bool(self.driver.execute_script("""
            const links = document.querySelectorAll('a, button');
            for (const el of links) {
                const text = (el.textContent || '').trim().toLowerCase();
                if (text.includes("i'm interested") || text.includes('apply now') ||
                    text.includes('easy apply') || text.includes('apply for')) {
                    el.click();
                    return true;
                }
            }
            return false;
        """))

    def _fill_shadow_fields(self) -> int:
        """Fill form fields inside spl-input shadow DOMs."""
        field_map = {
            "first-name-input": self.data["first_name"],
            "last-name-input": self.data["last_name"],
            "email-input": self.data.get("login_email", self.data["email"]),
            "confirm-email-input": self.data.get("login_email", self.data["email"]),
            "linkedin-input": self.data.get("linkedin", ""),
            "website-input": self.data.get("website", ""),
        }

        filled = 0
        for input_id, value in field_map.items():
            if not value:
                continue
            try:
                result = self.driver.execute_script("""
                    const splInputs = document.querySelectorAll('spl-input');
                    for (const si of splInputs) {
                        if (!si.shadowRoot) continue;
                        const inp = si.shadowRoot.getElementById(arguments[0]);
                        if (inp) {
                            inp.focus();
                            inp.value = arguments[1];
                            inp.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                            inp.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
                            inp.dispatchEvent(new Event('blur', {bubbles: true, composed: true}));
                            return true;
                        }
                    }
                    return false;
                """, input_id, value)
                if result:
                    filled += 1
                    print(f"  [+] Filled '{input_id}'")
            except Exception as exc:
                print(f"  [!] Shadow fill error '{input_id}': {exc}")

        # Phone number — inside spl-phone-field shadow root
        filled += self._fill_phone()

        return filled

    def _fill_phone(self) -> int:
        """Fill phone number inside spl-phone-field shadow DOM."""
        try:
            result = self.driver.execute_script("""
                // Try direct spl-phone-field
                const phone = document.querySelector('spl-phone-field');
                if (phone && phone.shadowRoot) {
                    const inp = phone.shadowRoot.querySelector('input[type="tel"], input');
                    if (inp) {
                        inp.focus();
                        inp.value = arguments[0];
                        inp.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
                        return true;
                    }
                }
                // Fallback: try nested oc-phone-number > spl-phone-field
                const wrapper = document.querySelector('oc-phone-number');
                if (wrapper) {
                    const inner = wrapper.querySelector('spl-phone-field');
                    if (inner && inner.shadowRoot) {
                        const inp = inner.shadowRoot.querySelector('input');
                        if (inp) {
                            inp.focus();
                            inp.value = arguments[0];
                            inp.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                            return true;
                        }
                    }
                }
                return false;
            """, self.data["phone"])
            if result:
                print("  [+] Filled phone number")
                return 1
        except Exception as exc:
            print(f"  [!] Phone fill error: {exc}")
        return 0

    def _fill_city(self) -> int:
        """Fill city autocomplete by focusing, typing, and selecting first match."""
        try:
            # Focus the autocomplete input via shadow DOM
            found = self.driver.execute_script("""
                // Try spl-autocomplete directly
                let auto = document.querySelector('spl-autocomplete');
                if (!auto) {
                    const wrapper = document.querySelector('oc-location-autocomplete');
                    if (wrapper) auto = wrapper.querySelector('spl-autocomplete');
                }
                if (auto && auto.shadowRoot) {
                    const inp = auto.shadowRoot.querySelector('input');
                    if (inp) {
                        inp.focus();
                        inp.value = '';
                        inp.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                        return true;
                    }
                }
                return false;
            """)

            if not found:
                print("  [!] City autocomplete not found")
                return 0

            # Type city name using ActionChains (reaches focused element)
            city = self.data.get("city", "Melbourne")
            actions = ActionChains(self.driver)
            actions.send_keys(city).perform()
            time.sleep(3)  # Wait for suggestions to load

            # Select first option with keyboard
            actions = ActionChains(self.driver)
            actions.send_keys(Keys.ARROW_DOWN).send_keys(Keys.ENTER).perform()
            time.sleep(1)

            print(f"  [+] City filled: {city}")
            return 1
        except Exception as exc:
            print(f"  [!] City fill error: {exc}")
            return 0

    def _upload_resume(self) -> None:
        """Upload resume via spl-dropzone shadow DOM file input."""
        try:
            # Make file input visible and move to light DOM for Selenium access
            self.driver.execute_script("""
                const dropzones = document.querySelectorAll('spl-dropzone');
                for (const dz of dropzones) {
                    if (!dz.shadowRoot) continue;
                    const inp = dz.shadowRoot.querySelector('input[type="file"]');
                    if (inp) {
                        // Clone to light DOM so Selenium can find it
                        const clone = document.createElement('input');
                        clone.type = 'file';
                        clone.id = '__sr_resume_upload__';
                        clone.accept = inp.accept;
                        clone.style.cssText = 'display:block;position:fixed;top:0;left:0;z-index:99999;';
                        document.body.appendChild(clone);
                        // Wire up change event to forward to original
                        clone.addEventListener('change', () => {
                            const dt = new DataTransfer();
                            for (const f of clone.files) dt.items.add(f);
                            inp.files = dt.files;
                            inp.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
                        });
                        return true;
                    }
                }
                return false;
            """)
            time.sleep(1)

            try:
                upload_el = self.driver.find_element(By.ID, "__sr_resume_upload__")
                upload_el.send_keys(self.data["resume_path"])
                print("  [+] Resume uploaded.")
                time.sleep(3)
            except Exception:
                print("  [!] Resume clone upload failed — trying direct file input.")
                self.safe_upload(By.CSS_SELECTOR, "input[type='file']", self.data["resume_path"], timeout=3)

            # Clean up clone
            self.driver.execute_script("""
                const clone = document.getElementById('__sr_resume_upload__');
                if (clone) clone.remove();
            """)
        except Exception as exc:
            print(f"  [!] Resume upload error: {exc}")

    def _highlight_action_button(self) -> None:
        """Highlight Next/Submit button without clicking."""
        self.driver.execute_script("""
            const btns = document.querySelectorAll('button, input[type="submit"]');
            for (const btn of btns) {
                const text = (btn.textContent || btn.value || '').trim().toLowerCase();
                if (text === 'next' || text === 'submit' || text.includes('submit application')) {
                    btn.style.border = '4px solid red';
                    btn.style.boxShadow = '0 0 15px red';
                    btn.scrollIntoView({block: 'center'});
                    break;
                }
            }
        """)
        print("  [+] Action button highlighted (NOT clicking).")
