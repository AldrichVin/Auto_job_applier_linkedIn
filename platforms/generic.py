"""Generic fallback handler — opens the URL and attempts basic form filling."""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from platforms.base import BasePlatformHandler


class GenericHandler(BasePlatformHandler):
    """Fallback handler for unsupported platforms.

    Attempts to click Apply buttons and fill common form fields.
    """

    PLATFORM_NAME = "generic"

    def apply(self, url: str, job_info: dict) -> str:
        title = job_info.get("title", "Unknown")
        company = job_info.get("company", "Unknown")
        print(f"  [i] Generic handler for: {title} @ {company}")

        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(2)

        # ── Check for expired/closed listings ──────────────────────
        if self._is_job_closed():
            print("  [!] Job listing appears closed/expired.")
            return "error"

        # ── Try to click Apply button ───────────────────────────────

        apply_clicked = self._click_apply_button()
        if apply_clicked:
            time.sleep(3)
            self.wait_for_page_load()

            # Check if a new tab opened
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.wait_for_page_load()
                time.sleep(2)

        # ── Handle login/signup if needed ──────────────────────────
        if self._is_login_page():
            print("  [i] Login/signup page detected — attempting auto-login...")
            self._handle_login_signup()
            time.sleep(3)
            self.wait_for_page_load()

        # ── Try to fill any visible form fields (multi-step) ────────

        total_filled = 0
        for step in range(5):  # up to 5 form steps
            filled = self._try_fill_form(job_info)
            total_filled += filled

            # Try clicking Next / Continue button to advance
            if not self._click_next_button():
                break
            time.sleep(3)
            self.wait_for_page_load()

        if total_filled > 0:
            print(f"  [+] Generic: filled {total_filled} fields.")
            return "filled"

        print(f"  [i] Generic: opened page, filled {total_filled} fields. Manual apply needed.")
        return "manual"

    def _click_apply_button(self) -> bool:
        """Try clicking various common Apply button patterns."""
        selectors = [
            (By.XPATH, "//a[contains(translate(text(),'APPLY','apply'),'apply')]"),
            (By.XPATH, "//button[contains(translate(text(),'APPLY','apply'),'apply')]"),
            (By.XPATH, "//a[contains(translate(text(),'APPLY','apply'),'apply for')]"),
            (By.XPATH, "//button[contains(translate(text(),'APPLY','apply'),'apply for')]"),
            (By.XPATH, "//a[contains(translate(text(),'START','start'),'start new application')]"),
            (By.XPATH, "//button[contains(translate(text(),'START','start'),'start new application')]"),
            (By.XPATH, "//a[contains(translate(text(),'BEGIN','begin'),'begin')]"),
            (By.XPATH, "//button[contains(translate(text(),'BEGIN','begin'),'begin')]"),
            (By.CSS_SELECTOR, "a[href*='apply'], a[class*='apply'], button[class*='apply']"),
            (By.CSS_SELECTOR, "a[data-action*='apply'], button[data-action*='apply']"),
            (By.CSS_SELECTOR, ".apply-btn, .btn-apply, .apply-button, .job-apply"),
            (By.CSS_SELECTOR, "a[id*='apply'], button[id*='apply']"),
        ]

        for by, selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        text = el.text.strip().lower()
                        if any(skip in text for skip in ["login", "sign in", "save", "alert", "back"]):
                            continue
                        self._scroll_into_view(el)
                        el.click()
                        print(f"  [+] Clicked apply button: '{el.text.strip()[:50]}'")
                        return True
            except Exception:
                continue

        print("  [!] Could not find an Apply button.")
        return False

    def _try_fill_form(self, job_info: dict) -> int:
        """Try to fill common form fields on any page. Returns count of filled fields."""
        filled = 0

        # Name fields
        filled += self._try_fill_input(["first.?name", "fname", "given.?name"], self.data["first_name"])
        filled += self._try_fill_input(["last.?name", "lname", "surname", "family.?name"], self.data["last_name"])
        filled += self._try_fill_input(["full.?name", "your.?name", "applicant.?name"], self.data["full_name"])

        # Email
        filled += self._try_fill_input(["email", "e-mail"], self.data["email"])

        # Phone
        filled += self._try_fill_input(["phone", "mobile", "tel", "contact.?number"], self.data["phone"])

        # Location
        filled += self._try_fill_input(["city", "location", "suburb", "town"], self.data["city"])

        # Postcode
        filled += self._try_fill_input(["post.?code", "zip.?code", "postal"], self.data["postcode"])

        # Address
        filled += self._try_fill_input(["address", "street"], self.data["address_line1"])

        # Current job title
        filled += self._try_fill_input(["job.?title", "current.?title", "position.?title"], self.data["current_job_title"])

        # LinkedIn
        filled += self._try_fill_input(["linkedin"], self.data["linkedin"])

        # Website / portfolio
        filled += self._try_fill_input(["website", "portfolio", "url"], self.data["website"])

        # Resume upload
        try:
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            for fi in file_inputs:
                try:
                    fi.send_keys(self.data["resume_path"])
                    filled += 1
                    print("  [+] Uploaded resume to file input.")
                    time.sleep(2)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # Cover letter textarea
        cover_text = job_info.get("cover_letter") or self.data["cover_letter"]
        if cover_text:
            filled += self._try_fill_textarea(["cover", "letter", "message", "additional"], cover_text)

        return filled

    def _try_fill_input(self, keywords: list[str], value: str) -> int:
        """Try to find and fill an input matching any of the keywords. Returns 1 if filled, 0 if not."""
        import re
        for kw in keywords:
            try:
                for attr in ["name", "id", "placeholder", "aria-label"]:
                    selector = f"input[{attr}]"
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        attr_val = (el.get_attribute(attr) or "").lower()
                        if re.search(kw, attr_val) and el.is_displayed():
                            el_type = (el.get_attribute("type") or "").lower()
                            if el_type in ("file", "hidden", "submit", "checkbox", "radio"):
                                continue
                            el.clear()
                            el.send_keys(value)
                            return 1
            except Exception:
                continue

            # Try by label text
            try:
                xpath = (
                    f"//label[contains(translate(text(),"
                    f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
                    f"'{kw.replace('.?', '')}')]/..//input[not(@type='file') and not(@type='hidden') and not(@type='checkbox')]"
                )
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed():
                        el.clear()
                        el.send_keys(value)
                        return 1
            except Exception:
                continue
        return 0

    def _try_fill_textarea(self, keywords: list[str], value: str) -> int:
        """Try to fill a textarea matching any keyword. Returns 1 if filled."""
        import re
        for kw in keywords:
            try:
                for attr in ["name", "id", "placeholder", "aria-label"]:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, f"textarea[{attr}]")
                    for el in elements:
                        attr_val = (el.get_attribute(attr) or "").lower()
                        if re.search(kw, attr_val) and el.is_displayed():
                            el.clear()
                            el.send_keys(value)
                            return 1
            except Exception:
                continue

        # Fallback: try any visible textarea
        try:
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            for ta in textareas:
                if ta.is_displayed() and not ta.get_attribute("readonly"):
                    ta.clear()
                    ta.send_keys(value)
                    return 1
        except Exception:
            pass
        return 0

    def _click_next_button(self) -> bool:
        """Try clicking Next / Continue / Proceed buttons to advance multi-step forms."""
        next_selectors = [
            (By.XPATH, "//button[contains(translate(text(),'NEXT','next'),'next')]"),
            (By.XPATH, "//button[contains(translate(text(),'CONTINUE','continue'),'continue')]"),
            (By.XPATH, "//a[contains(translate(text(),'NEXT','next'),'next')]"),
            (By.XPATH, "//a[contains(translate(text(),'CONTINUE','continue'),'continue')]"),
            (By.XPATH, "//button[contains(translate(text(),'PROCEED','proceed'),'proceed')]"),
            (By.CSS_SELECTOR, "button.next, button.btn-next, button[data-action='next']"),
            (By.CSS_SELECTOR, "a.next, a.btn-next"),
        ]

        for by, selector in next_selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        text = el.text.strip().lower()
                        if any(skip in text for skip in ["login", "sign in", "back", "previous"]):
                            continue
                        self._scroll_into_view(el)
                        el.click()
                        print(f"  [>] Clicked next button: '{el.text.strip()[:50]}'")
                        return True
            except Exception:
                continue

        return False

    def _is_login_page(self) -> bool:
        """Check if the current page is a login or signup form."""
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            login_phrases = [
                "sign in", "log in", "login", "sign up", "signup",
                "create an account", "create account", "register",
            ]
            # Must also have an email/password input
            has_email_input = bool(self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='email'], input[name*='email' i], input[placeholder*='email' i]"
            ))
            has_password_input = bool(self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='password']"
            ))
            return (has_email_input or has_password_input) and any(p in page_text for p in login_phrases)
        except Exception:
            return False

    def _handle_login_signup(self) -> None:
        """Attempt to fill login/signup forms with stored credentials."""
        login_email = self.data.get("login_email", self.data["email"])
        login_password = self.data.get("login_password", "")

        # Fill email
        for selector in [
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[name*='email' i]"),
            (By.CSS_SELECTOR, "input[placeholder*='email' i]"),
            (By.XPATH, "//label[contains(translate(text(),'EMAIL','email'),'email')]/..//input"),
        ]:
            try:
                elements = self.driver.find_elements(selector[0], selector[1])
                for el in elements:
                    if el.is_displayed():
                        el.clear()
                        el.send_keys(login_email)
                        print(f"  [+] Filled login email: {login_email}")
                        break
            except Exception:
                continue

        # Fill password if field exists
        if login_password:
            try:
                pw_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                for pw in pw_inputs:
                    if pw.is_displayed():
                        pw.clear()
                        pw.send_keys(login_password)
                        print("  [+] Filled login password.")
                        break
            except Exception:
                pass

        # Fill first/last name if signup form
        self._try_fill_input(["first.?name", "fname", "given.?name"], self.data["first_name"])
        self._try_fill_input(["last.?name", "lname", "surname", "family.?name"], self.data["last_name"])

        time.sleep(1)

        # Click submit/login/signup/continue button
        for xpath in [
            "//button[contains(translate(text(),'SIGN','sign'),'sign up')]",
            "//button[contains(translate(text(),'SIGN','sign'),'sign in')]",
            "//button[contains(translate(text(),'LOG','log'),'log in')]",
            "//button[contains(translate(text(),'CREATE','create'),'create')]",
            "//button[contains(translate(text(),'REGISTER','register'),'register')]",
            "//button[contains(translate(text(),'CONTINUE','continue'),'continue')]",
            "//button[contains(translate(text(),'SUBMIT','submit'),'submit')]",
            "//input[@type='submit']",
        ]:
            try:
                buttons = self.driver.find_elements(By.XPATH, xpath)
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        print(f"  [+] Clicked login/signup button: '{btn.text.strip()[:40]}'")
                        time.sleep(3)

                        # Check if OTP/verification is needed
                        page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                        if any(kw in page_text for kw in ["verification code", "otp", "enter the code", "check your email"]):
                            print("  [i] OTP/verification code required — waiting for user...")
                            try:
                                import pyautogui
                                pyautogui.confirm(
                                    f"A verification code was sent to {login_email}.\n\n"
                                    "Enter the code in the browser, then click OK.",
                                    "OTP Required",
                                    ["OK - Done", "Skip"],
                                )
                            except Exception:
                                input("  Press Enter after entering OTP...")
                            time.sleep(2)
                        return
            except Exception:
                continue

    def _is_job_closed(self) -> bool:
        """Check if the page indicates the job listing is closed or expired."""
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            closed_phrases = [
                "applications for this job have closed",
                "this job is no longer available",
                "this position has been filled",
                "job has expired",
                "listing has expired",
                "no longer accepting applications",
                "this vacancy has closed",
                "role has been filled",
            ]
            return any(phrase in page_text for phrase in closed_phrases)
        except Exception:
            return False
