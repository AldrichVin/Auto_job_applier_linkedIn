"""Indeed (au.indeed.com) handler."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class IndeedHandler(BasePlatformHandler):
    """Fill application forms on Indeed."""

    PLATFORM_NAME = "indeed"
    LOGIN_URL = "https://secure.indeed.com/auth"

    def login(self) -> bool:
        from config.external_secrets import indeed_username, indeed_password

        if not indeed_username or not indeed_password:
            print("  [!] Indeed credentials not set. Set INDEED_USERNAME and INDEED_PASSWORD env vars.")
            print("  [i] Continuing without login.")
            return True

        print("  [>] Indeed: logging in...")
        self.driver.get(self.LOGIN_URL)
        self.wait_for_page_load()
        time.sleep(2)

        # Email
        filled = self.safe_fill(By.CSS_SELECTOR, "input[type='email'], input[name='__email']", indeed_username)
        if not filled:
            self.safe_fill(By.XPATH, "//input[@type='email' or contains(@id,'email')]", indeed_username)

        # Click continue (Indeed does email-first, then password)
        self.safe_click(By.CSS_SELECTOR, "button[type='submit'], button[data-testid*='continue']")
        time.sleep(3)

        # Password
        self.safe_fill(By.CSS_SELECTOR, "input[type='password']", indeed_password)
        self.safe_click(By.CSS_SELECTOR, "button[type='submit']")
        time.sleep(3)
        self.wait_for_page_load()

        # Check for CAPTCHA or 2FA — poll for up to 120s
        current = self.driver.current_url.lower()
        if "auth" in current or "captcha" in current or "challenge" in current:
            print("  [!] Indeed may need CAPTCHA or 2FA. Polling 120s...")
            for _ in range(24):
                time.sleep(5)
                current = self.driver.current_url.lower()
                if not any(kw in current for kw in ["auth", "captcha", "challenge"]):
                    break
            else:
                print("  [!] Indeed login timeout.")

        print("  [+] Indeed: login complete.")
        return True

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Indeed: navigating to job page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(2)

        # Click "Apply now" button
        self.safe_click(
            By.CSS_SELECTOR,
            "button[id*='applyButton'], a[id*='applyButton'], "
            "button.jobsearch-IndeedApplyButton, button[data-testid*='apply']",
            timeout=5,
        )
        time.sleep(3)
        self.wait_for_page_load()

        filled_count = 0

        # Indeed's apply form is multi-step. Fill what we can on each page.
        # Step through up to 5 pages.
        for step in range(5):
            print(f"  [>] Indeed: filling step {step + 1}...")
            fields_on_page = self._fill_current_page(job_info)
            filled_count += fields_on_page

            # Check if we're on the final review/submit page
            submit_btn = self._find_submit_button()
            if submit_btn:
                # We're at the end — highlight and stop
                self.highlight_submit_button(
                    By.CSS_SELECTOR,
                    "button[data-testid='submit-button'], button[type='submit']:last-of-type",
                )
                break

            # Click "Continue" to go to next step
            continued = self.safe_click(
                By.CSS_SELECTOR,
                "button[data-testid='continue-button'], button[id*='continue'], "
                "button.ia-continueButton, button[type='button']:not([data-testid='back'])",
                timeout=3,
            )
            if not continued:
                break
            time.sleep(2)
            self.wait_for_page_load()

        print(f"  [+] Indeed: filled {filled_count} fields across steps.")
        return "filled" if filled_count >= 1 else "error"

    def _fill_current_page(self, job_info: dict) -> int:
        """Fill fields on the current Indeed application page. Returns count."""
        filled = 0

        # Name fields
        if self.safe_fill(By.CSS_SELECTOR, "input[id*='firstName'], input[name*='firstName']", self.data["first_name"], timeout=2):
            filled += 1
        if self.safe_fill(By.CSS_SELECTOR, "input[id*='lastName'], input[name*='lastName']", self.data["last_name"], timeout=2):
            filled += 1

        # Email
        if self.safe_fill(By.CSS_SELECTOR, "input[type='email'], input[id*='email']", self.data["email"], timeout=2):
            filled += 1

        # Phone
        if self.safe_fill(By.CSS_SELECTOR, "input[type='tel'], input[id*='phone']", self.data["phone"], timeout=2):
            filled += 1

        # Location
        self.safe_fill(By.CSS_SELECTOR, "input[id*='city'], input[name*='city'], input[id*='location']", self.data["city"], timeout=2)

        # Resume upload
        if self.safe_upload(By.CSS_SELECTOR, "input[type='file']", self.data["resume_path"], timeout=2):
            filled += 1
            time.sleep(2)

        # Cover letter / message
        cover_text = job_info.get("cover_letter") or self.data["cover_letter"]
        if cover_text:
            self.fill_text_area(
                By.CSS_SELECTOR,
                "textarea[id*='cover'], textarea[name*='cover'], textarea[id*='message'], textarea",
                cover_text,
                timeout=2,
            )

        # Common questions
        self._fill_questions()

        return filled

    def _fill_questions(self):
        """Fill common Indeed application questions."""
        # Work authorization
        self._try_fill_or_select("authorized", "Yes")
        self._try_fill_or_select("authorised", "Yes")
        self._try_fill_or_select("right to work", "Yes")
        self._try_fill_or_select("visa", "Yes")
        self._try_fill_or_select("sponsorship", "No")

        # Experience
        self._try_fill_or_select("experience", self.data["years_of_experience"])
        self._try_fill_or_select("years", self.data["years_of_experience"])

        # Salary
        self._try_fill_or_select("salary", str(self.data["desired_salary"]))

        # Start date
        self._try_fill_or_select("start", "Immediately")
        self._try_fill_or_select("notice", "0")

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
                try:
                    inp = parent.find_element(By.CSS_SELECTOR, "input:not([type='file']):not([type='hidden'])")
                    if inp.is_displayed():
                        inp.clear()
                        inp.send_keys(value)
                        return
                except Exception:
                    pass
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

    def _find_submit_button(self) -> bool:
        """Check if we're on the final submit page."""
        try:
            elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                "button[data-testid='submit-button'], button[type='submit']"
            )
            for el in elements:
                text = el.text.lower()
                if "submit" in text or "apply" in text:
                    return True
        except Exception:
            pass
        return False
