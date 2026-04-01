"""Greenhouse ATS handler (boards.greenhouse.io, job-boards.greenhouse.io)."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class GreenhouseHandler(BasePlatformHandler):
    """Fill application forms on Greenhouse-hosted career pages."""

    PLATFORM_NAME = "greenhouse"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Greenhouse: navigating to application page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(2)

        # Some Greenhouse pages show the job description first with an
        # "Apply for this job" button. Click it if present.
        self.safe_click(By.CSS_SELECTOR, "a.btn--apply, a[href*='#app'], button.btn--apply", timeout=3)
        time.sleep(1)

        # ── Fill standard fields ────────────────────────────────────

        filled_count = 0

        # Name fields
        if self.safe_fill(By.ID, "first_name", self.data["first_name"]):
            filled_count += 1
        if self.safe_fill(By.ID, "last_name", self.data["last_name"]):
            filled_count += 1

        # Email
        if self.safe_fill(By.ID, "email", self.data["email"]):
            filled_count += 1

        # Phone
        if self.safe_fill(By.ID, "phone", self.data["phone"]):
            filled_count += 1

        # Location / address fields (varies by config)
        self.safe_fill(By.CSS_SELECTOR, "input[name*='location'], input[id*='location']", self.data["city"], timeout=3)

        # LinkedIn URL
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name*='linkedin'], input[id*='linkedin'], input[autocomplete*='linkedin']",
            self.data["linkedin"],
            timeout=3,
        )

        # Website / portfolio
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name*='website'], input[id*='website'], input[name*='portfolio']",
            self.data["website"],
            timeout=3,
        )

        # ── Resume upload ───────────────────────────────────────────

        # Greenhouse uses a hidden file input. Try multiple selectors.
        resume_uploaded = self.safe_upload(
            By.CSS_SELECTOR,
            "input[type='file'][name*='resume'], input[type='file']#resume, "
            "input[type='file'][data-field='resume']",
            self.data["resume_path"],
            timeout=3,
        )
        if not resume_uploaded:
            # Some Greenhouse forms use a different file input
            resume_uploaded = self.safe_upload(
                By.XPATH,
                "//label[contains(translate(text(),'RESUME','resume'),'resume')]/..//input[@type='file']",
                self.data["resume_path"],
                timeout=3,
            )
        if resume_uploaded:
            filled_count += 1
            time.sleep(2)  # Wait for upload processing

        # ── Cover letter ────────────────────────────────────────────

        cover_text = job_info.get("cover_letter") or self.data["cover_letter"]
        if cover_text:
            cl_filled = self.fill_text_area(
                By.CSS_SELECTOR,
                "textarea#cover_letter, textarea[name*='cover_letter']",
                cover_text,
                timeout=3,
            )
            if not cl_filled:
                # Try file upload for cover letter
                self.safe_upload(
                    By.XPATH,
                    "//label[contains(translate(text(),'COVER','cover'),'cover')]/..//input[@type='file']",
                    self.data["resume_path"],  # Fallback: upload resume as CL too
                    timeout=3,
                )

        # ── Custom questions ────────────────────────────────────────

        self._fill_custom_questions()

        # ── Highlight submit button (DO NOT CLICK) ──────────────────

        self.highlight_submit_button(
            By.CSS_SELECTOR,
            "button[type='submit'], input[type='submit'], button.btn--submit",
        )

        print(f"  [+] Greenhouse: filled {filled_count} core fields.")
        return "filled" if filled_count >= 3 else "error"

    def _fill_custom_questions(self):
        """Attempt to fill custom application questions."""
        # Greenhouse renders custom questions as additional form fields
        # with IDs like job_application_answers_attributes_0_text_value

        # Try to answer work authorization / visa questions
        self._try_fill_by_label("authorized", "Yes")
        self._try_fill_by_label("visa", self.data["require_visa"])
        self._try_fill_by_label("sponsorship", self.data["require_visa"])
        self._try_fill_by_label("salary", str(self.data["desired_salary"]))
        self._try_fill_by_label("experience", self.data["years_of_experience"])
        self._try_fill_by_label("notice", str(self.data["notice_period"]))

        # Gender / diversity questions
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
                f"'{label_keyword.lower()}')]/..//input[not(@type='file') and not(@type='hidden')]"
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
