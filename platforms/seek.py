"""Seek.com.au handler."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class SeekHandler(BasePlatformHandler):
    """Fill application forms on Seek.com.au."""

    PLATFORM_NAME = "seek"
    LOGIN_URL = "https://www.seek.com.au/oauth/login"

    def login(self) -> bool:
        from config.external_secrets import seek_username, seek_password

        if not seek_username or not seek_password:
            print("  [!] Seek credentials not set. Set SEEK_USERNAME and SEEK_PASSWORD env vars.")
            print("  [i] Continuing without login — forms may require manual auth.")
            return True  # Don't block, just warn

        print("  [>] Seek: logging in...")
        self.driver.get(self.LOGIN_URL)
        self.wait_for_page_load()
        time.sleep(2)

        # Email field
        if not self.safe_fill(By.ID, "emailAddress", seek_username):
            self.safe_fill(By.CSS_SELECTOR, "input[type='email']", seek_username)

        # Password field
        if not self.safe_fill(By.ID, "password", seek_password):
            self.safe_fill(By.CSS_SELECTOR, "input[type='password']", seek_password)

        # Click sign in
        clicked = self.safe_click(By.CSS_SELECTOR, "button[data-cy='login'], button[type='submit']")
        if clicked:
            time.sleep(3)
            self.wait_for_page_load()

        # Verify login — poll for up to 120s
        if "login" in self.driver.current_url.lower():
            print("  [!] Seek login may need attention (CAPTCHA/2FA). Polling 120s...")
            for _ in range(24):
                time.sleep(5)
                if "login" not in self.driver.current_url.lower():
                    break
            else:
                print("  [!] Seek login timeout.")

        print("  [+] Seek: login complete.")
        return True

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Seek: navigating to job page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(2)

        # Click "Quick apply" or "Apply" button
        apply_clicked = self.safe_click(
            By.CSS_SELECTOR,
            "a[data-automation='job-detail-apply'], button[data-automation='job-detail-apply'], "
            "a[href*='apply'], button:has-text('Apply')",
            timeout=5,
        )
        if not apply_clicked:
            # Try XPath fallback
            self.safe_click(By.XPATH, "//a[contains(text(),'Apply')] | //button[contains(text(),'Apply')]")

        time.sleep(3)
        self.wait_for_page_load()

        filled_count = 0

        # ── Fill form fields ────────────────────────────────────────

        # Seek pre-fills most fields when logged in. Fill what's empty.
        # First name
        if self.safe_fill(By.CSS_SELECTOR, "input[data-testid='first-name'], input[name='firstName']", self.data["first_name"], timeout=3):
            filled_count += 1
        # Last name
        if self.safe_fill(By.CSS_SELECTOR, "input[data-testid='last-name'], input[name='lastName']", self.data["last_name"], timeout=3):
            filled_count += 1
        # Email
        if self.safe_fill(By.CSS_SELECTOR, "input[data-testid='email'], input[name='email'], input[type='email']", self.data["email"], timeout=3):
            filled_count += 1
        # Phone
        if self.safe_fill(By.CSS_SELECTOR, "input[data-testid='phone'], input[name='phone'], input[type='tel']", self.data["phone"], timeout=3):
            filled_count += 1

        # ── Resume upload ───────────────────────────────────────────

        resume_uploaded = self.safe_upload(
            By.CSS_SELECTOR,
            "input[type='file']",
            self.data["resume_path"],
            timeout=3,
        )
        if resume_uploaded:
            filled_count += 1
            time.sleep(2)

        # ── Cover letter ────────────────────────────────────────────

        cover_text = job_info.get("cover_letter") or self.data["cover_letter"]
        if cover_text:
            self.fill_text_area(
                By.CSS_SELECTOR,
                "textarea[data-testid='cover-letter'], textarea[name*='cover'], textarea",
                cover_text,
                timeout=3,
            )

        # ── Custom questions ────────────────────────────────────────

        self._fill_seek_questions()

        # ── Highlight submit (DO NOT CLICK) ─────────────────────────

        self.highlight_submit_button(
            By.CSS_SELECTOR,
            "button[data-testid='submit-application'], button[type='submit']",
        )

        print(f"  [+] Seek: filled {filled_count} core fields.")
        return "filled" if filled_count >= 1 else "error"

    def _fill_seek_questions(self):
        """Fill common Seek application questions."""
        # Work authorization
        self._try_fill_or_select("right to work", "Yes")
        self._try_fill_or_select("authorized", "Yes")
        self._try_fill_or_select("authorised", "Yes")
        self._try_fill_or_select("visa", "Yes")

        # Salary expectations
        self._try_fill_or_select("salary", str(self.data["desired_salary"]))

        # Experience
        self._try_fill_or_select("experience", self.data["years_of_experience"])

        # Notice period
        self._try_fill_or_select("notice", "Immediately" if self.data["notice_period"] == 0 else f"{self.data['notice_period']} days")
        self._try_fill_or_select("start", "Immediately")

    def _try_fill_or_select(self, label_keyword: str, value: str):
        """Try to find and fill an input or select near a label."""
        try:
            xpath = (
                f"//label[contains(translate(text(),"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                f"'{label_keyword.lower()}')]"
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
                        return
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
                                return
                except Exception:
                    pass
        except Exception:
            pass
