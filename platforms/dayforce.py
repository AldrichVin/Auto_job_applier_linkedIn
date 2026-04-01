"""Dayforce HCM handler (jobs.dayforcehcm.com)."""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from platforms.base import BasePlatformHandler


class DayforceHandler(BasePlatformHandler):
    """Fill application forms on Dayforce HCM career pages."""

    PLATFORM_NAME = "dayforce"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Dayforce: navigating to job page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        # ── Dismiss cookie consent popup ────────────────────────────
        self._dismiss_cookie_consent()

        # ── Click the "Apply for ..." button ────────────────────────
        applied = self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Apply for')]",
            timeout=10,
        )
        if not applied:
            print("  [!] Could not find 'Apply for' button.")
            return "error"

        self.wait_for_page_load()
        time.sleep(2)

        # ── Select "Apply without an account" ───────────────────────
        apply_without = self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Apply without an account')]",
            timeout=10,
        )
        if not apply_without:
            print("  [!] Could not find 'Apply without an account' button.")
            return "error"

        self.wait_for_page_load()
        time.sleep(3)

        # ── Step 1: Candidate info ──────────────────────────────────
        filled_count = self._fill_candidate_info()

        # ── Resume upload ───────────────────────────────────────────
        resume_uploaded = self._upload_resume()
        if resume_uploaded:
            filled_count += 1

        # ── Click "Next" to advance to Questionnaire ────────────────
        time.sleep(1)
        next_clicked = self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Next')]",
            timeout=5,
        )
        if next_clicked:
            print("  [+] Clicked 'Next' — stopping before Submit.")
            self.wait_for_page_load()
            time.sleep(2)

        # ── Highlight submit if visible (DO NOT CLICK) ──────────────
        self.highlight_submit_button(
            By.XPATH,
            "//button[contains(text(),'Submit')]",
        )

        print(f"  [+] Dayforce: filled {filled_count} core fields.")
        return "filled" if filled_count >= 5 else "error"

    # ── Private helpers ─────────────────────────────────────────────

    def _dismiss_cookie_consent(self) -> None:
        """Accept cookie consent popup if present."""
        try:
            accept_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(text(),'Accept') or contains(text(),'accept') "
                    "or contains(text(),'OK') or contains(text(),'Got it') "
                    "or contains(text(),'Agree')]",
                ))
            )
            accept_btn.click()
            print("  [+] Dismissed cookie consent popup.")
            time.sleep(1)
        except Exception:
            pass  # No cookie banner — that's fine

    def _fill_candidate_info(self) -> int:
        """Fill all fields on the candidate info step. Returns count of filled fields."""
        filled = 0

        # Email address
        if self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'Email address')]/following::input[1]",
            self.data["email"],
        ):
            filled += 1

        # Confirm email address
        if self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'Confirm email')]/following::input[1]",
            self.data["email"],
        ):
            filled += 1

        # Prefix (RC Select combobox)
        prefix_value = self.data.get("prefix", "Mr")
        prefix_combobox = self._find_combobox_by_label("Prefix")
        if prefix_combobox and self._fill_rc_select(prefix_combobox, prefix_value):
            filled += 1

        # First name
        if self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'First name')]/following::input[1]",
            self.data["first_name"],
        ):
            filled += 1

        # Middle name (optional)
        middle_name = self.data.get("middle_name", "")
        if middle_name:
            self.safe_fill(
                By.XPATH,
                "//label[contains(text(),'Middle name')]/following::input[1]",
                middle_name,
                timeout=3,
            )

        # Last name
        if self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'Last name')]/following::input[1]",
            self.data["last_name"],
        ):
            filled += 1

        # LinkedIn Profile (optional)
        linkedin = self.data.get("linkedin", "")
        if linkedin:
            self.safe_fill(
                By.XPATH,
                "//label[contains(text(),'LinkedIn')]/following::input[1]",
                linkedin,
                timeout=3,
            )

        # Mobile phone country dialling code (RC Select combobox)
        phone_country_combobox = self._find_combobox_by_label("dialling code")
        if not phone_country_combobox:
            phone_country_combobox = self._find_combobox_by_label("country code")
        if phone_country_combobox:
            self._fill_rc_select(phone_country_combobox, "Aus", partial_match=True)
            time.sleep(0.5)

        # Mobile phone number (strip country code — Dayforce has separate dialling code)
        phone_number = self.data.get("phone", "")
        phone_number = phone_number.lstrip("+")
        if phone_number.startswith("61"):
            phone_number = phone_number[2:]
        phone_number = phone_number.lstrip("0")
        if self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'Mobile phone number')]/following::input[not(@role='combobox')][1]",
            phone_number,
        ):
            filled += 1

        # Preferred contact method (RC Select combobox)
        contact_method = self.data.get("preferred_contact_method", "Email")
        contact_combobox = self._find_combobox_by_label("Preferred contact")
        if contact_combobox and self._fill_rc_select(contact_combobox, contact_method):
            filled += 1

        # Country (RC Select combobox)
        country = self.data.get("country", "Australia")
        country_combobox = self._find_combobox_by_label("Country")
        if country_combobox and self._fill_rc_select(country_combobox, country):
            filled += 1
            time.sleep(1.5)  # Wait for State/Province to become enabled

        # State/Province (RC Select combobox — disabled until Country is set)
        state = self.data.get("state", "Victoria")
        state_combobox = self._find_combobox_by_label("State")
        if not state_combobox:
            state_combobox = self._find_combobox_by_label("Province")
        if state_combobox and self._fill_rc_select(state_combobox, state):
            filled += 1

        # Address line 1
        address = self.data.get("address_line1", "")
        if address and self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'Address line 1')]/following::input[1]",
            address,
        ):
            filled += 1

        # City
        city = self.data.get("city", "")
        if city and self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'City')]/following::input[1]",
            city,
        ):
            filled += 1

        # ZIP/Postal code
        postcode = self.data.get("postcode", "")
        if postcode and self.safe_fill(
            By.XPATH,
            "//label[contains(text(),'ZIP') or contains(text(),'Postal')]/following::input[1]",
            postcode,
        ):
            filled += 1

        # How did you hear about us? (RC Select combobox)
        referral = self.data.get("referral_source", "LinkedIn")
        referral_combobox = self._find_combobox_by_label("hear about")
        if referral_combobox and self._fill_rc_select(referral_combobox, referral):
            filled += 1

        return filled

    def _find_combobox_by_label(self, label_text: str) -> WebElement | None:
        """Find an RC Select combobox input by nearby label text."""
        try:
            # Strategy 1: label text -> ancestor form-item -> combobox input
            xpath = (
                f"//label[contains(translate(text(),"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                f"'{label_text.lower()}')]"
                f"/ancestor::div[contains(@class,'form-item') or contains(@class,'field')]"
                f"//input[@role='combobox']"
            )
            elements = self.driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed():
                    return el

            # Strategy 2: label followed by combobox input
            xpath_fallback = (
                f"//label[contains(translate(text(),"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                f"'{label_text.lower()}')]"
                f"/following::input[@role='combobox'][1]"
            )
            elements = self.driver.find_elements(By.XPATH, xpath_fallback)
            for el in elements:
                if el.is_displayed():
                    return el
        except Exception as exc:
            print(f"  [!] Could not find combobox for '{label_text}': {exc}")

        return None

    def _fill_rc_select(
        self, combobox_element: WebElement, value: str, partial_match: bool = False
    ) -> bool:
        """Fill an RC Select / Ant Design combobox by typing and selecting from dropdown."""
        try:
            self._scroll_into_view(combobox_element)
            combobox_element.click()
            time.sleep(0.5)
            combobox_element.send_keys(value)
            time.sleep(1)

            # Find and click matching option in listbox
            script = """
            const listboxes = document.querySelectorAll('[role="listbox"]');
            for (const lb of listboxes) {
                const options = lb.querySelectorAll('[role="option"]');
                for (const opt of options) {
                    const text = opt.textContent.trim();
                    if (arguments[0] ? text.includes(arguments[1]) : text === arguments[1]) {
                        opt.click();
                        return text;
                    }
                }
            }
            return null;
            """
            result = self.driver.execute_script(script, partial_match, value)
            return result is not None
        except Exception as exc:
            print(f"  [!] RC Select fill error for '{value}': {exc}")
            return False

    def _upload_resume(self) -> bool:
        """Upload resume via the hidden file input."""
        resume_path = self.data.get("resume_path", "")
        if not resume_path:
            print("  [!] No resume path configured.")
            return False

        try:
            # Make the hidden file input visible via JS
            self.driver.execute_script("""
                const input = document.getElementById('jobPostingApplication_files_resume');
                if (input) {
                    input.style.display = 'block';
                    input.style.visibility = 'visible';
                    input.style.opacity = '1';
                    input.style.height = 'auto';
                    input.style.width = 'auto';
                    input.style.position = 'relative';
                }
            """)
            time.sleep(0.5)

            uploaded = self.safe_upload(
                By.ID,
                "jobPostingApplication_files_resume",
                resume_path,
                timeout=5,
            )
            if uploaded:
                print("  [+] Resume uploaded successfully.")
                time.sleep(2)
                return True
        except Exception as exc:
            print(f"  [!] Resume upload error: {exc}")

        return False
