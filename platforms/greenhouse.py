"""Greenhouse ATS handler (boards.greenhouse.io, job-boards.greenhouse.io)."""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from platforms.base import BasePlatformHandler


class GreenhouseHandler(BasePlatformHandler):
    """Fill application forms on Greenhouse-hosted career pages."""

    PLATFORM_NAME = "greenhouse"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Greenhouse: navigating to application page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        # Some Greenhouse pages show the job description first with an
        # "Apply" button that scrolls to the form. Click it if present.
        self.safe_click(
            By.CSS_SELECTOR,
            "button:not([type='submit'])",
            timeout=2,
        )
        time.sleep(1)

        # ── Fill standard fields ────────────────────────────────────

        filled_count = 0

        # First Name
        if self.safe_fill(By.ID, "first_name", self.data["first_name"]):
            filled_count += 1

        # Last Name
        if self.safe_fill(By.ID, "last_name", self.data["last_name"]):
            filled_count += 1

        # Preferred First Name (optional)
        self.safe_fill(By.ID, "preferred_first_name", self.data["first_name"], timeout=2)

        # Email
        if self.safe_fill(By.ID, "email", self.data["email"]):
            filled_count += 1

        # Phone — Greenhouse has a Country combobox + phone input
        self._fill_phone_with_country()
        filled_count += 1

        # ── Resume upload ───────────────────────────────────────────

        # Greenhouse uses button-based upload. Find the file input
        # (it may be hidden behind the "Attach" button).
        resume_uploaded = self._upload_via_file_input("resume")
        if resume_uploaded:
            filled_count += 1
            time.sleep(2)

        # ── Cover letter ────────────────────────────────────────────

        # Greenhouse cover letter: click "Enter manually" then type
        cover_text = self.data.get("tailored_cover_letter") or self.data["cover_letter"]
        # Use job-specific cover letter if available from job_info
        if job_info.get("cover_letter"):
            cover_text = job_info["cover_letter"]

        cl_filled = self._fill_cover_letter(cover_text)
        if cl_filled:
            filled_count += 1

        # ── LinkedIn Profile ────────────────────────────────────────

        # Greenhouse uses aria-label or label text association
        linkedin_filled = self.safe_fill(
            By.CSS_SELECTOR,
            "input[aria-label*='LinkedIn'], input[placeholder*='LinkedIn']",
            self.data["linkedin"],
            timeout=2,
        )
        if not linkedin_filled:
            linkedin_filled = self.safe_fill(
                By.XPATH,
                "//label[contains(text(),'LinkedIn Profile')]/following::input[1]",
                self.data["linkedin"],
                timeout=2,
            )
        if not linkedin_filled:
            self._try_fill_by_label("linkedin", self.data["linkedin"])

        # Website / portfolio
        website_filled = self.safe_fill(
            By.CSS_SELECTOR,
            "input[aria-label*='Website'], input[placeholder*='Website']",
            self.data["website"],
            timeout=2,
        )
        if not website_filled:
            website_filled = self.safe_fill(
                By.XPATH,
                "//label[contains(text(),'Website')]/following::input[1]",
                self.data["website"],
                timeout=2,
            )
        if not website_filled:
            self._try_fill_by_label("website", self.data["website"])

        # ── Custom questions ────────────────────────────────────────

        self._fill_custom_questions()

        # ── Privacy / consent checkboxes ────────────────────────────

        self._check_consent_boxes()

        # ── AI fallback for remaining unknown fields ────────────────
        self.fill_unknown_fields(job_info)

        # ── Highlight submit button (DO NOT CLICK) ──────────────────

        self.highlight_submit_button(
            By.XPATH,
            "//button[contains(text(),'Submit')]",
        )

        # Scroll to form area for screenshot
        try:
            form = self.driver.find_element(By.CSS_SELECTOR, "form, #application-form, [data-automation*='application']")
            self._scroll_into_view(form)
        except Exception:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(0.5)

        print(f"  [+] Greenhouse: filled {filled_count} core fields.")
        return "filled" if filled_count >= 3 else "error"

    def _fill_phone_with_country(self):
        """Fill the phone field, setting country code first if there's a dropdown."""
        try:
            # Greenhouse has a Country combobox for phone prefix
            country_combo = self.driver.find_elements(
                By.CSS_SELECTOR, "div.phone-field select, select[name*='country'], "
                "input[role='combobox'][aria-label*='Country']"
            )
            if country_combo:
                # Try clicking the combobox and selecting Australia
                combo = country_combo[0]
                self._scroll_into_view(combo)
                combo.click()
                time.sleep(0.5)
                combo.send_keys("Australia")
                time.sleep(1)
                combo.send_keys(Keys.ENTER)
                time.sleep(0.5)

            # Fill phone number
            self.safe_fill(By.ID, "phone", self.data["phone"])
        except Exception as exc:
            print(f"  [!] Phone/country fill error: {exc}")
            # Fallback: just fill phone
            self.safe_fill(By.ID, "phone", self.data["phone"])

    def _upload_via_file_input(self, field_keyword: str) -> bool:
        """Find a file input near a label and upload resume."""
        try:
            # Greenhouse hides file inputs. Find all input[type=file] elements.
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            for inp in file_inputs:
                # Check if this input is near the resume/CV section
                parent_text = ""
                try:
                    parent = inp.find_element(By.XPATH, "./ancestor::div[contains(@class,'field')]")
                    parent_text = parent.text.lower()
                except Exception:
                    pass

                if field_keyword.lower() in parent_text or not parent_text:
                    inp.send_keys(self.data["resume_path"])
                    print(f"  [+] Uploaded file to '{field_keyword}' field.")
                    return True

            # Fallback: just use the first file input
            if file_inputs:
                file_inputs[0].send_keys(self.data["resume_path"])
                print(f"  [+] Uploaded file to first file input.")
                return True
        except Exception as exc:
            print(f"  [!] File upload error: {exc}")
        return False

    def _fill_cover_letter(self, cover_text: str) -> bool:
        """Fill cover letter — click 'Enter manually' first, then type into the textarea."""
        if not cover_text:
            return False

        try:
            # Greenhouse has two "Enter manually" buttons:
            # 1st = Resume/CV section, 2nd = Cover Letter section.
            # We need the one inside the Cover Letter group/fieldset.
            enter_manually_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[contains(text(),'Enter manually')]"
            )

            cl_button = None

            # Strategy 1: find the button inside a group/fieldset labeled "Cover Letter"
            for btn in enter_manually_buttons:
                try:
                    group = btn.find_element(By.XPATH, "./ancestor::fieldset | ./ancestor::*[@role='group']")
                    group_text = group.get_attribute("aria-label") or group.text
                    if "cover" in group_text.lower():
                        cl_button = btn
                        break
                except Exception:
                    pass

            # Strategy 2: if two buttons exist, the second is cover letter
            if not cl_button and len(enter_manually_buttons) >= 2:
                cl_button = enter_manually_buttons[1]

            # Strategy 3: find button preceded by "Cover Letter" text
            if not cl_button:
                try:
                    cl_button = self.driver.find_element(
                        By.XPATH,
                        "//label[contains(text(),'Cover Letter')]/following::button[contains(text(),'Enter manually')][1]"
                    )
                except Exception:
                    pass

            if not cl_button:
                print("  [!] Could not find Cover Letter 'Enter manually' button.")
                return False

            # Click the button to reveal the textarea
            self._scroll_into_view(cl_button)
            cl_button.click()
            time.sleep(1.5)

            # After clicking, Greenhouse creates a new textarea.
            # It's the most recently created visible textarea on the page.
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            for ta in reversed(textareas):
                if ta.is_displayed():
                    ta.clear()
                    ta.send_keys(cover_text)
                    print("  [+] Cover letter filled successfully.")
                    return True

            print("  [!] Textarea not found after clicking 'Enter manually'.")
            return False

        except Exception as exc:
            print(f"  [!] Cover letter error: {exc}")
            return False

    def _check_consent_boxes(self):
        """Check all required consent/privacy checkboxes."""
        try:
            checkboxes = self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='checkbox']"
            )
            for cb in checkboxes:
                if not cb.is_selected():
                    try:
                        # Some checkboxes need their label clicked instead
                        self._scroll_into_view(cb)
                        try:
                            cb.click()
                        except Exception:
                            # Try clicking the label instead
                            label = cb.find_element(By.XPATH, "./following-sibling::label | ./parent::label | ./ancestor::div//label")
                            label.click()
                        print("  [+] Checked consent checkbox.")
                    except Exception:
                        pass
        except Exception as exc:
            print(f"  [!] Checkbox error: {exc}")

    def _fill_custom_questions(self):
        """Attempt to fill custom application questions."""
        self._try_fill_by_label("authorized", "Yes")
        self._try_fill_by_label("visa", self.data["require_visa"])
        self._try_fill_by_label("sponsorship", self.data["require_visa"])
        self._try_fill_by_label("salary", str(self.data["desired_salary"]))
        self._try_fill_by_label("experience", self.data["years_of_experience"])
        self._try_fill_by_label("notice", str(self.data["notice_period"]))

        self._try_select_by_label("gender", self.data["gender"])
        self._try_select_by_label("race", self.data["ethnicity"])
        self._try_select_by_label("ethnicity", self.data["ethnicity"])
        self._try_select_by_label("veteran", self.data["veteran_status"])
        self._try_select_by_label("disability", self.data["disability_status"])

    def _try_fill_by_label(self, label_keyword: str, value: str):
        """Try to find an input near a label containing keyword and fill it."""
        try:
            xpath = (
                f"//label[contains(translate(text(),"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                f"'{label_keyword.lower()}')]/..//input[not(@type='file') and not(@type='hidden') and not(@type='checkbox')]"
            )
            elements = self.driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed():
                    el.clear()
                    el.send_keys(value)
                    return
            # Also try textarea
            xpath_ta = (
                f"//label[contains(translate(text(),"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                f"'{label_keyword.lower()}')]/..//textarea"
            )
            elements = self.driver.find_elements(By.XPATH, xpath_ta)
            for el in elements:
                if el.is_displayed():
                    el.clear()
                    el.send_keys(value)
                    return
        except Exception:
            pass

    def _try_select_by_label(self, label_keyword: str, value: str):
        """Try to find a <select> near a label containing keyword and select value."""
        try:
            xpath = (
                f"//label[contains(translate(text(),"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                f"'{label_keyword.lower()}')]/..//select"
            )
            elements = self.driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed():
                    from selenium.webdriver.support.ui import Select
                    select = Select(el)
                    for option in select.options:
                        if value.lower() in option.text.lower():
                            select.select_by_visible_text(option.text)
                            return
        except Exception:
            pass
