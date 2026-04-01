"""Michael Page job application handler (michaelpage.com.au)."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class MichaelPageHandler(BasePlatformHandler):
    """Fill application forms on Michael Page career pages."""

    PLATFORM_NAME = "michaelpage"

    # Select2 dropdown IDs and their desired values
    _SELECT2_FIELDS = {
        "edit-cc-industry-cc-industry-1": "32626",            # Technology & Telecoms
        "edit-cc-industry-cc-industry-2": "32656",            # Software
        "edit-cc-job-function-cc-job-function-1": "27426",    # Analytics
        "edit-cc-job-function-cc-job-function-2": "27456",    # Data Analyst
        "edit-current-role-cc-experience-level": "32861",     # Entry Level
        "edit-preferred-job-type-section-preferred-job-type": "permanent;temporary;ftc",  # Permanent, open to contract
        "edit-preferred-job-type-section-notice-period": "Immediately Available",
        "edit-preferred-job-type-section-salary-container-currency": "AUD",
    }

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Michael Page: navigating to application page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        try:
            self._step_1_apply_method()
            self._step_2_personal_information()
            self._step_3_employment_details()
        except Exception as exc:
            print(f"  [!] Michael Page error: {exc}")
            self.take_screenshot("michaelpage", "error")
            return "error"

        # Highlight submit (user clicks manually)
        self.highlight_submit_button(
            By.CSS_SELECTOR,
            "input#edit-submit, button.mp-job-apply-final-submit-loader",
        )

        self.take_screenshot("michaelpage", "filled")
        print("  [+] Michael Page: form filled successfully.")
        return "filled"

    def _step_1_apply_method(self) -> None:
        """Click 'Apply with CV' and enter email address."""
        print("  [>] Step 1: Apply method...")

        # Click "Apply with CV" via JS — most reliable
        clicked = self.driver.execute_script("""
            const els = document.querySelectorAll('a, button, div[role="button"]');
            for (const el of els) {
                const text = (el.textContent || '').trim().toLowerCase();
                if (text.includes('apply with cv') || text.includes('apply with your cv')) {
                    el.scrollIntoView({block: 'center'});
                    el.click();
                    return true;
                }
            }
            return false;
        """)
        if clicked:
            print("  [+] Clicked 'Apply with CV'.")
        else:
            print("  [!] Could not find 'Apply with CV' — trying to proceed anyway.")

        time.sleep(3)
        self.wait_for_page_load()

        # Fill email — use JS to find by placeholder/label since ID varies
        login_email = self.data.get("login_email", self.data["email"])
        filled = self.driver.execute_script("""
            const inputs = document.querySelectorAll('input[type="text"], input[type="email"]');
            for (const inp of inputs) {
                if (inp.offsetParent === null) continue;
                const label = inp.getAttribute('aria-label') || inp.placeholder || '';
                if (label.toLowerCase().includes('email')) {
                    inp.focus();
                    inp.value = arguments[0];
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
                }
                return false;
            """, login_email)

        time.sleep(1)

        # Click "Navigate to personal information"
        self._click_nav_button("navigate to personal")
        time.sleep(3)
        self.wait_for_page_load()

    def _step_2_personal_information(self) -> None:
        """Fill personal information fields and upload CV."""
        print("  [>] Step 2: Personal information...")

        # Fill fields by their actual IDs, with JS fallback by placeholder
        field_map = {
            "edit-mp-first-name": (self.data["first_name"], "Name"),
            "edit-mp-last-name": (self.data["last_name"], "Surname"),
            "edit-mp-phone-number": (self.data["phone"], "Telephone"),
            "edit-postcode": (self.data["postcode"], "Postcode"),
            "edit-city": (self.data["city"], "Town"),
        }

        for field_id, (value, placeholder) in field_map.items():
            if not self.safe_fill(By.ID, field_id, value, timeout=3):
                # Fallback: try by name attribute
                name_attr = field_id.replace("edit-", "").replace("-", "_")
                if not self.safe_fill(By.CSS_SELECTOR, f"input[name*='{name_attr}']", value, timeout=2):
                    # JS fallback: find by placeholder
                    self.driver.execute_script("""
                        const inputs = document.querySelectorAll('input[type="text"]');
                        for (const inp of inputs) {
                            if (inp.offsetParent === null) continue;
                            if ((inp.placeholder || '').toLowerCase().includes(arguments[1].toLowerCase())) {
                                inp.focus();
                                inp.value = arguments[0];
                                inp.dispatchEvent(new Event('input', {bubbles: true}));
                                inp.dispatchEvent(new Event('change', {bubbles: true}));
                                return;
                            }
                        }
                    """, value, placeholder)

        # Select "No" for Aboriginal/Torres Strait Islander
        self._click_radio_by_id("edit-first-nations-no")

        # Upload CV
        self._upload_cv()

        time.sleep(1)

        # Navigate to employment step
        self._click_nav_button("navigate to employment")
        time.sleep(3)
        self.wait_for_page_load()

    def _step_3_employment_details(self) -> None:
        """Fill employment detail dropdowns and fields using Select2 jQuery API."""
        print("  [>] Step 3: Employment details...")

        # Fill Select2 dropdowns sequentially (sub-options depend on parent)
        # Industry
        self._set_select2("edit-cc-industry-cc-industry-1",
                          self._SELECT2_FIELDS["edit-cc-industry-cc-industry-1"])
        time.sleep(1)

        # Sub Industry (enabled after Industry)
        self._set_select2("edit-cc-industry-cc-industry-2",
                          self._SELECT2_FIELDS["edit-cc-industry-cc-industry-2"])
        time.sleep(1)

        # Department
        self._set_select2("edit-cc-job-function-cc-job-function-1",
                          self._SELECT2_FIELDS["edit-cc-job-function-cc-job-function-1"])
        time.sleep(1)

        # Role (enabled after Department)
        self._set_select2("edit-cc-job-function-cc-job-function-2",
                          self._SELECT2_FIELDS["edit-cc-job-function-cc-job-function-2"])
        time.sleep(1)

        # Current Job Title
        self.safe_fill(
            By.ID,
            "edit-current-role-current-job-title",
            self.data["current_job_title"],
        )

        # Experience Level
        self._set_select2("edit-current-role-cc-experience-level",
                          self._SELECT2_FIELDS["edit-current-role-cc-experience-level"])

        # Preferred job type
        self._set_select2("edit-preferred-job-type-section-preferred-job-type",
                          self._SELECT2_FIELDS["edit-preferred-job-type-section-preferred-job-type"])
        time.sleep(1)

        # Notice period (appears after job type is selected)
        self._set_select2("edit-preferred-job-type-section-notice-period",
                          self._SELECT2_FIELDS["edit-preferred-job-type-section-notice-period"])

        # Currency
        self._set_select2("edit-preferred-job-type-section-salary-container-currency",
                          self._SELECT2_FIELDS["edit-preferred-job-type-section-salary-container-currency"])

        # Annual salary
        self.safe_fill(
            By.ID,
            "edit-preferred-job-type-section-salary-container-annual-salary",
            str(self.data.get("current_salary", self.data.get("desired_salary", "60000"))),
        )

        # Privacy consent checkbox
        self._check_checkbox_by_id("edit-mp-pp-check")

    # ── Private helpers ────────────────────────────────────────────────

    def _set_select2(self, element_id: str, value: str) -> bool:
        """Set a Select2 dropdown value using jQuery trigger."""
        try:
            result = self.driver.execute_script("""
                const el = document.getElementById(arguments[0]);
                if (!el) return 'not_found';
                if (el.disabled) return 'disabled';
                // Try jQuery Select2 API
                if (typeof jQuery !== 'undefined') {
                    jQuery('#' + arguments[0]).val(arguments[1]).trigger('change');
                    return 'set_jquery';
                }
                // Fallback: set value directly
                el.value = arguments[1];
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return 'set_direct';
            """, element_id, value)
            if result == 'not_found':
                print(f"  [!] Select2 '{element_id}' not found.")
                return False
            if result == 'disabled':
                print(f"  [!] Select2 '{element_id}' is disabled — skipping.")
                return False
            print(f"  [+] Select2 '{element_id}' -> {value} ({result})")
            return True
        except Exception as exc:
            print(f"  [!] Select2 error '{element_id}': {exc}")
            return False

    def _click_radio_by_id(self, radio_id: str) -> bool:
        """Click a radio button by its ID using JS."""
        try:
            self.driver.execute_script("""
                const radio = document.getElementById(arguments[0]);
                if (radio) radio.click();
            """, radio_id)
            print(f"  [+] Clicked radio '{radio_id}'.")
            return True
        except Exception as exc:
            print(f"  [!] Radio click error '{radio_id}': {exc}")
            return False

    def _check_checkbox_by_id(self, checkbox_id: str) -> bool:
        """Check a checkbox by ID if not already checked."""
        try:
            self.driver.execute_script("""
                const cb = document.getElementById(arguments[0]);
                if (cb && !cb.checked) cb.click();
            """, checkbox_id)
            print(f"  [+] Checked '{checkbox_id}'.")
            return True
        except Exception as exc:
            print(f"  [!] Checkbox error '{checkbox_id}': {exc}")
            return False

    def _click_nav_button(self, text_fragment: str) -> bool:
        """Click a navigation button by partial text match (JS fallback)."""
        try:
            clicked = self.driver.execute_script("""
                const btns = document.querySelectorAll('input[type="submit"], button');
                const target = arguments[0].toLowerCase();
                for (const btn of btns) {
                    const label = (btn.getAttribute('aria-label') || btn.textContent || btn.value || '').toLowerCase();
                    if (label.includes(target)) {
                        btn.scrollIntoView({block: 'center'});
                        btn.click();
                        return true;
                    }
                }
                return false;
            """, text_fragment)
            if clicked:
                print(f"  [+] Clicked nav button '{text_fragment}'.")
            else:
                print(f"  [!] Nav button '{text_fragment}' not found.")
            return bool(clicked)
        except Exception as exc:
            print(f"  [!] Nav button error: {exc}")
            return False

    def _upload_cv(self) -> None:
        """Upload CV via the hidden file input."""
        try:
            # Make the file input visible
            self.driver.execute_script("""
                const fileInput = document.getElementById('edit-field-cv-0-upload');
                if (fileInput) {
                    fileInput.style.display = 'block';
                    fileInput.style.opacity = '1';
                    fileInput.style.position = 'static';
                    fileInput.style.width = 'auto';
                    fileInput.style.height = 'auto';
                }
            """)
            time.sleep(1)

            self.safe_upload(
                By.ID,
                "edit-field-cv-0-upload",
                self.data["resume_path"],
                timeout=5,
            )
            print("  [+] CV uploaded successfully.")
            time.sleep(3)
        except Exception as exc:
            print(f"  [!] CV upload error: {exc}")
