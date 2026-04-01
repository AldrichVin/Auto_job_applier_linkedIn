"""SmartRecruiters handler (jobs.smartrecruiters.com)."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class SmartRecruitersHandler(BasePlatformHandler):
    """Fill application forms on SmartRecruiters-hosted career pages."""

    PLATFORM_NAME = "smartrecruiters"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] SmartRecruiters: navigating to job page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(2)

        # Click "Apply" button
        self.safe_click(
            By.CSS_SELECTOR,
            "button.js-apply-btn, a.apply-btn, button[data-test='apply-button'], "
            "a[data-test='apply-button']",
            timeout=5,
        )
        if not self.safe_click(By.XPATH, "//button[contains(text(),'Apply')] | //a[contains(text(),'Apply')]", timeout=3):
            pass
        time.sleep(3)
        self.wait_for_page_load()

        filled_count = 0

        # ── Standard fields ─────────────────────────────────────────

        name_fields = [
            ("input[name='firstName'], input[aria-label='First name']", self.data["first_name"]),
            ("input[name='lastName'], input[aria-label='Last name']", self.data["last_name"]),
            ("input[name='email'], input[aria-label='Email'], input[type='email']", self.data["email"]),
            ("input[name='phoneNumber'], input[aria-label='Phone'], input[type='tel']", self.data["phone"]),
            ("input[name='location'], input[aria-label='Location']", f"{self.data['city']}, {self.data['country']}"),
        ]

        for selector, value in name_fields:
            if self.safe_fill(By.CSS_SELECTOR, selector, value, timeout=3):
                filled_count += 1

        # ── Resume upload ───────────────────────────────────────────

        if self.safe_upload(By.CSS_SELECTOR, "input[type='file']", self.data["resume_path"], timeout=3):
            filled_count += 1
            time.sleep(2)

        # ── Cover letter ────────────────────────────────────────────

        cover_text = job_info.get("cover_letter") or self.data["cover_letter"]
        if cover_text:
            self.fill_text_area(
                By.CSS_SELECTOR,
                "textarea[name*='cover'], textarea[aria-label*='cover'], textarea",
                cover_text,
                timeout=3,
            )

        # ── LinkedIn / website ──────────────────────────────────────

        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name*='linkedin'], input[aria-label*='LinkedIn']",
            self.data["linkedin"],
            timeout=2,
        )
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name*='website'], input[aria-label*='website'], input[name*='portfolio']",
            self.data["website"],
            timeout=2,
        )

        # ── Custom questions ────────────────────────────────────────

        self._fill_label_questions()

        # ── Navigate through steps ──────────────────────────────────

        for _ in range(3):
            next_clicked = self.safe_click(
                By.CSS_SELECTOR,
                "button[data-test='next-button'], button.next-btn",
                timeout=3,
            )
            if not next_clicked:
                # Try generic "Next" text
                next_clicked = self.safe_click(
                    By.XPATH,
                    "//button[contains(text(),'Next')]",
                    timeout=2,
                )
            if not next_clicked:
                break
            time.sleep(2)
            self.wait_for_page_load()
            self._fill_label_questions()

        # ── Highlight submit (DO NOT CLICK) ─────────────────────────

        self.highlight_submit_button(
            By.CSS_SELECTOR,
            "button[data-test='submit-button'], button[type='submit']",
        )
        self.highlight_submit_button(
            By.XPATH,
            "//button[contains(text(),'Submit')] | //button[contains(text(),'Apply')]",
        )

        print(f"  [+] SmartRecruiters: filled {filled_count} core fields.")
        return "filled" if filled_count >= 2 else "error"

    def _fill_label_questions(self):
        """Fill questions by matching label text."""
        keyword_map = {
            "authorized": "Yes",
            "authorised": "Yes",
            "right to work": "Yes",
            "visa": "Yes",
            "sponsorship": "No",
            "salary": str(self.data["desired_salary"]),
            "experience": self.data["years_of_experience"],
            "notice": "0",
            "gender": self.data["gender"],
            "race": self.data["ethnicity"],
            "ethnicity": self.data["ethnicity"],
            "veteran": self.data["veteran_status"],
            "disability": self.data["disability_status"],
        }
        for keyword, value in keyword_map.items():
            try:
                xpath = (
                    f"//label[contains(translate(text(),"
                    f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                    f"'{keyword}')]"
                )
                labels = self.driver.find_elements(By.XPATH, xpath)
                for label in labels:
                    parent = label.find_element(By.XPATH, "./..")
                    # Try input
                    try:
                        inp = parent.find_element(By.CSS_SELECTOR, "input:not([type='file']):not([type='hidden'])")
                        if inp.is_displayed():
                            inp.clear()
                            inp.send_keys(value)
                            break
                    except Exception:
                        pass
                    # Try select
                    try:
                        sel = parent.find_element(By.CSS_SELECTOR, "select")
                        if sel.is_displayed():
                            from selenium.webdriver.support.ui import Select
                            select = Select(sel)
                            for option in select.options:
                                if value.lower() in option.text.lower():
                                    select.select_by_visible_text(option.text)
                                    break
                            break
                    except Exception:
                        pass
            except Exception:
                pass
