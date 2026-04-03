"""Workday ATS handler (myworkdayjobs.com, myworkday.com)."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class WorkdayHandler(BasePlatformHandler):
    """Fill application forms on Workday-hosted career pages."""

    PLATFORM_NAME = "workday"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Workday: navigating to job page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        # Click "Apply" button
        apply_clicked = self.safe_click(
            By.CSS_SELECTOR,
            "a[data-automation-id='jobPostingApplyButton'], "
            "button[data-automation-id='jobPostingApplyButton']",
            timeout=5,
        )
        if not apply_clicked:
            self.safe_click(By.XPATH, "//a[contains(text(),'Apply')] | //button[contains(text(),'Apply')]")

        time.sleep(3)
        self.wait_for_page_load()

        # Workday often requires "Apply Manually" vs "Apply with LinkedIn"
        self.safe_click(
            By.XPATH,
            "//a[contains(text(),'Apply Manually')] | //button[contains(text(),'Apply Manually')]",
            timeout=3,
        )
        time.sleep(2)

        # May need to create account or sign in
        if self._check_for_account_wall():
            print("  [!] Workday requires account creation. Attempting auto-login...")
            login_email = self.data.get("login_email", self.data["email"])
            login_password = self.data.get("login_password", "")
            self.safe_fill(By.CSS_SELECTOR, "input[type='email'], input[data-automation-id*='email']", login_email)
            if login_password:
                self.safe_fill(By.CSS_SELECTOR, "input[type='password']", login_password)
            self.safe_click(By.CSS_SELECTOR, "button[type='submit'], button[data-automation-id*='submit']", timeout=3)
            time.sleep(3)

            # Poll for account wall to clear
            for _ in range(24):
                time.sleep(5)
                if not self._check_for_account_wall():
                    print("  [+] Workday login completed.")
                    break
            else:
                print("  [!] Workday login timeout.")
            self.wait_for_page_load()

        filled_count = 0

        # ── Personal info ───────────────────────────────────────────

        # Workday uses data-automation-id attributes
        wd_fields = [
            ("legalNameSection_firstName", self.data["first_name"]),
            ("legalNameSection_lastName", self.data["last_name"]),
            ("email", self.data["email"]),
            ("phone-number", self.data["phone"]),
            ("addressSection_addressLine1", self.data["street"]),
            ("addressSection_city", self.data["city"]),
            ("addressSection_postalCode", self.data["zipcode"]),
        ]

        for auto_id, value in wd_fields:
            if self.safe_fill(
                By.CSS_SELECTOR,
                f"input[data-automation-id='{auto_id}']",
                value,
                timeout=3,
            ):
                filled_count += 1

        # Country / state dropdowns
        self.safe_click(
            By.CSS_SELECTOR,
            "button[data-automation-id='addressSection_countryRegion']",
            timeout=2,
        )
        time.sleep(1)
        self.safe_click(
            By.XPATH,
            f"//div[@data-automation-id='promptOption' and contains(text(),'{self.data['country']}')]",
            timeout=2,
        )

        # ── Resume upload ───────────────────────────────────────────

        resume_uploaded = self.safe_upload(
            By.CSS_SELECTOR,
            "input[data-automation-id='file-upload-input-ref'], input[type='file']",
            self.data["resume_path"],
            timeout=3,
        )
        if resume_uploaded:
            filled_count += 1
            time.sleep(3)

        # ── Cover letter ────────────────────────────────────────────

        cover_text = job_info.get("cover_letter") or self.data["cover_letter"]
        if cover_text:
            self.fill_text_area(
                By.CSS_SELECTOR,
                "textarea[data-automation-id='coverLetter'], textarea",
                cover_text,
                timeout=3,
            )

        # ── Work experience section ─────────────────────────────────

        self.safe_fill(
            By.CSS_SELECTOR,
            "input[data-automation-id='jobTitle']",
            "Data Analyst Intern",
            timeout=2,
        )
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[data-automation-id='company']",
            self.data["current_employer"],
            timeout=2,
        )

        # ── Education section ───────────────────────────────────────

        self.safe_fill(
            By.CSS_SELECTOR,
            "input[data-automation-id='school']",
            self.data["education_university"],
            timeout=2,
        )
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[data-automation-id='degree']",
            self.data["education_degree"],
            timeout=2,
        )

        # ── Custom questions ────────────────────────────────────────

        self._fill_label_questions()

        # ── Navigate through steps ──────────────────────────────────

        # Workday forms can be multi-step. Try clicking "Next" / "Save and Continue"
        for _ in range(3):
            next_clicked = self.safe_click(
                By.CSS_SELECTOR,
                "button[data-automation-id='bottom-navigation-next-button'], "
                "button[data-automation-id='saveAndContinue']",
                timeout=3,
            )
            if not next_clicked:
                break
            time.sleep(2)
            self.wait_for_page_load()
            # Fill any new fields on this page
            self._fill_label_questions()

        # ── AI fallback for remaining unknown fields ────────────────
        self.fill_unknown_fields(job_info)

        # ── Highlight submit (DO NOT CLICK) ─────────────────────────

        self.highlight_submit_button(
            By.CSS_SELECTOR,
            "button[data-automation-id='bottom-navigation-next-button'], "
            "button[data-automation-id='submit'], button[type='submit']",
        )

        print(f"  [+] Workday: filled {filled_count} core fields.")
        return "filled" if filled_count >= 2 else "error"

    def _check_for_account_wall(self) -> bool:
        """Check if Workday is showing a create-account / sign-in page."""
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            return any(phrase in page_text for phrase in [
                "create account", "sign in to apply", "create your account",
            ])
        except Exception:
            return False

    def _fill_label_questions(self):
        """Fill questions by matching label text to known answers."""
        keyword_map = {
            "authorized": "Yes",
            "authorised": "Yes",
            "right to work": "Yes",
            "visa": "Yes",
            "sponsorship": "No",
            "salary": str(self.data["desired_salary"]),
            "experience": self.data["years_of_experience"],
            "notice": "0",
            "start date": "Immediately",
        }
        for keyword, value in keyword_map.items():
            try:
                xpath = (
                    f"//label[contains(translate(text(),"
                    f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                    f"'{keyword}')]/..//input[not(@type='file') and not(@type='hidden')]"
                )
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed():
                        el.clear()
                        el.send_keys(value)
                        break
            except Exception:
                pass
