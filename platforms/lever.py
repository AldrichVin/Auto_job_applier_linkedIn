"""Lever ATS handler (jobs.lever.co)."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class LeverHandler(BasePlatformHandler):
    """Fill application forms on Lever-hosted career pages."""

    PLATFORM_NAME = "lever"

    def apply(self, url: str, job_info: dict) -> str:
        # Ensure we're on the /apply page
        apply_url = url if "/apply" in url else url.rstrip("/") + "/apply"
        print("  [>] Lever: navigating to application page...")
        self.driver.get(apply_url)
        self.wait_for_page_load()
        time.sleep(2)

        filled_count = 0

        # ── Standard fields ─────────────────────────────────────────

        # Full name (Lever uses a single "name" field)
        if self.safe_fill(By.CSS_SELECTOR, "input[name='name']", self.data["full_name"]):
            filled_count += 1

        # Email
        if self.safe_fill(By.CSS_SELECTOR, "input[name='email']", self.data["email"]):
            filled_count += 1

        # Phone
        if self.safe_fill(By.CSS_SELECTOR, "input[name='phone']", self.data["phone"]):
            filled_count += 1

        # Current company
        self.safe_fill(By.CSS_SELECTOR, "input[name='org']", self.data["current_employer"], timeout=3)

        # LinkedIn URL
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name='urls[LinkedIn]'], input[name*='linkedin'], input[name*='LinkedIn']",
            self.data["linkedin"],
            timeout=3,
        )

        # Portfolio / website
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name='urls[Portfolio]'], input[name*='portfolio'], input[name*='website']",
            self.data["website"],
            timeout=3,
        )

        # GitHub
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name='urls[GitHub]'], input[name*='github']",
            "https://github.com/AldrichVin",
            timeout=3,
        )

        # ── Resume upload ───────────────────────────────────────────

        resume_uploaded = self.safe_upload(
            By.CSS_SELECTOR,
            "input[type='file'][name='resume'], input[type='file']",
            self.data["resume_path"],
            timeout=3,
        )
        if resume_uploaded:
            filled_count += 1
            time.sleep(2)

        # ── Cover letter / additional info ──────────────────────────

        cover_text = job_info.get("cover_letter") or self.data["cover_letter"]
        if cover_text:
            self.fill_text_area(
                By.CSS_SELECTOR,
                "textarea[name='comments'], textarea[name='coverLetter'], textarea.application-answer",
                cover_text,
                timeout=3,
            )

        # ── Custom questions ────────────────────────────────────────

        self._fill_custom_questions()

        # ── Highlight submit (DO NOT CLICK) ─────────────────────────

        self.highlight_submit_button(
            By.CSS_SELECTOR,
            "button[type='submit'], button.postings-btn--submit, input[type='submit']",
        )

        print(f"  [+] Lever: filled {filled_count} core fields.")
        return "filled" if filled_count >= 3 else "error"

    def _fill_custom_questions(self):
        """Fill custom questions in Lever's application-question blocks."""
        try:
            question_blocks = self.driver.find_elements(
                By.CSS_SELECTOR, "div.application-question, div.custom-question"
            )
            for block in question_blocks:
                label_text = ""
                try:
                    label = block.find_element(By.CSS_SELECTOR, "label, .application-label")
                    label_text = label.text.lower()
                except Exception:
                    continue

                value = self._get_answer_for_question(label_text)
                if not value:
                    continue

                # Try input field
                try:
                    inp = block.find_element(By.CSS_SELECTOR, "input:not([type='file']):not([type='hidden'])")
                    if inp.is_displayed():
                        inp.clear()
                        inp.send_keys(value)
                        continue
                except Exception:
                    pass

                # Try textarea
                try:
                    ta = block.find_element(By.CSS_SELECTOR, "textarea")
                    if ta.is_displayed():
                        ta.clear()
                        ta.send_keys(value)
                        continue
                except Exception:
                    pass

                # Try select
                try:
                    sel = block.find_element(By.CSS_SELECTOR, "select")
                    if sel.is_displayed():
                        from selenium.webdriver.support.ui import Select
                        select = Select(sel)
                        for option in select.options:
                            if value.lower() in option.text.lower():
                                select.select_by_visible_text(option.text)
                                break
                except Exception:
                    pass

        except Exception:
            pass

    def _get_answer_for_question(self, question_text: str) -> str:
        """Return an answer based on question keyword matching."""
        q = question_text.lower()
        if any(kw in q for kw in ["salary", "compensation", "pay"]):
            return str(self.data["desired_salary"])
        if any(kw in q for kw in ["experience", "years"]):
            return self.data["years_of_experience"]
        if any(kw in q for kw in ["visa", "sponsor", "authorized", "authorised", "work right"]):
            return "Yes" if self.data["require_visa"] == "No" else "No"
        if any(kw in q for kw in ["notice", "start date", "available"]):
            return "Immediately" if self.data["notice_period"] == 0 else f"{self.data['notice_period']} days"
        if any(kw in q for kw in ["gender"]):
            return self.data["gender"]
        if any(kw in q for kw in ["race", "ethnic"]):
            return self.data["ethnicity"]
        if any(kw in q for kw in ["veteran"]):
            return self.data["veteran_status"]
        if any(kw in q for kw in ["disability", "disabled"]):
            return self.data["disability_status"]
        if any(kw in q for kw in ["linkedin"]):
            return self.data["linkedin"]
        if any(kw in q for kw in ["website", "portfolio"]):
            return self.data["website"]
        if any(kw in q for kw in ["location", "city", "where"]):
            return self.data["city"]
        return ""
