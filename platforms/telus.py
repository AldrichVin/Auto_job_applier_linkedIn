"""TELUS Digital AI handler (telusinternational.ai) — Password + OTP login."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class TelusHandler(BasePlatformHandler):
    """Handle TELUS Digital AI job applications.

    TELUS login flow:
    1. Enter email → Continue
    2. Password page (if account exists) or Signup page (new account)
    3. Complete sign-up: address → demographics → phone verification
    4. Redirect to job page / dashboard
    """

    PLATFORM_NAME = "telus"
    LOGIN_URL = "https://www.telusinternational.ai/snake"

    def login(self) -> bool:
        """Pre-login to TELUS before applying to jobs."""
        login_email = self.data.get("login_email", self.data["email"])
        login_password = self.data.get("login_password", "")

        print("  [>] TELUS: navigating to login page...")
        self.driver.get(self.LOGIN_URL)
        self.wait_for_page_load()
        time.sleep(3)

        # ── Fill email ──────────────────────────────────────────────
        filled = self._fill_email(login_email)
        if not filled:
            print("  [!] Could not fill email field.")
            return False

        print(f"  [+] Filled login email: {login_email}")
        time.sleep(1)

        # Click Continue
        self.safe_click(By.XPATH, "//button[contains(text(),'Continue')]", timeout=10)
        time.sleep(4)

        # ── Detect what page we landed on ───────────────────────────
        current_url = self.driver.current_url.lower()
        page_text = self._get_page_text()

        if "password" in page_text or "log in to access" in page_text:
            # Password login page
            print("  [i] Password login page detected.")
            return self._handle_password_login(login_password)
        elif "signup" in current_url or "create an account" in page_text:
            # New account signup
            print("  [i] Signup form detected.")
            self._handle_signup_form()
            return self._poll_for_login_complete(login_email)
        else:
            # OTP flow or already logged in
            return self._poll_for_login_complete(login_email)

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] TELUS: navigating to job page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        # ── Check for 404 / unavailable ────────────────────────────
        page_text = self._get_page_text()
        if any(phrase in page_text for phrase in [
            "page cannot be found", "not found", "not available for you",
            "do not meet the selection criteria",
        ]):
            print("  [!] Job not available or page not found.")
            return "error"

        # ── Check if login is needed ───────────────────────────────
        if "snake" in self.driver.current_url.lower() or "login" in self.driver.current_url.lower():
            print("  [i] Login required, attempting...")
            logged_in = self.login()
            if not logged_in:
                return "error"
            # Navigate back to job URL after login
            self.driver.get(url)
            self.wait_for_page_load()
            time.sleep(3)

        # ── Dismiss cookie popup ───────────────────────────────────
        self.safe_click(By.XPATH, "//button[contains(text(),'Okay, Got it')]", timeout=3)
        time.sleep(0.5)

        # ── Click "Log in to apply" or "Apply" ─────────────────────
        clicked = self._click_apply_button()
        if not clicked:
            # Already on the apply page or no button found
            page_text = self._get_page_text()
            if "not available" in page_text:
                print("  [!] Job not available for you.")
                return "error"

        time.sleep(3)
        self.wait_for_page_load()

        # ── Check if we need to complete sign-up ───────────────────
        current_url = self.driver.current_url.lower()
        if "profile" in current_url and "complete sign-up" in self._get_page_text():
            print("  [i] Need to complete sign-up first...")
            self._handle_complete_signup()
            # Navigate back to job
            self.driver.get(url)
            self.wait_for_page_load()
            time.sleep(3)

        # ── Fill application form if present ───────────────────────
        filled_count = self.fill_unknown_fields(job_info)

        if filled_count > 0:
            print(f"  [+] TELUS: filled {filled_count} fields.")
            return "filled"

        print("  [i] TELUS: page opened. May need manual interaction.")
        return "manual"

    def _click_apply_button(self) -> bool:
        """Try clicking various Apply/Login buttons on TELUS job pages."""
        # Try specific button text first
        for text in ["Log in to apply", "Apply", "Apply Now"]:
            if self.safe_click(By.XPATH, f"//button[contains(text(),'{text}')]", timeout=3):
                return True
            if self.safe_click(By.XPATH, f"//a[contains(text(),'{text}')]", timeout=2):
                return True

        # JS fallback — exact text matches only
        clicked = self.driver.execute_script("""
            const targets = ['log in to apply', 'log in / sign up', 'apply', 'apply now'];
            const els = document.querySelectorAll('button, a');
            for (const el of els) {
                const text = el.textContent.trim().toLowerCase();
                if (targets.includes(text)) {
                    el.click();
                    return true;
                }
            }
            return false;
        """)
        return bool(clicked)

    def _handle_password_login(self, password: str) -> bool:
        """Fill password and submit on the TELUS password login page."""
        if not password:
            print("  [!] No password configured for TELUS login.")
            print("  [i] Falling back to OTP — click 'Login with OTP instead' in browser.")
            return self._poll_for_login_complete("")

        # Fill password
        filled = self.safe_fill(By.CSS_SELECTOR, "input[type='password']", password, timeout=5)
        if not filled:
            filled = self.safe_fill(By.XPATH, "//input[@type='password']", password, timeout=3)
        if not filled:
            print("  [!] Could not fill password field.")
            return False

        print("  [+] Filled password.")
        time.sleep(1)

        # Click Login button
        self.safe_click(By.XPATH, "//button[contains(text(),'Login')]", timeout=5)
        time.sleep(4)
        self.wait_for_page_load()

        # ── Check if we need to complete sign-up ───────────────────
        current_url = self.driver.current_url.lower()
        page_text = self._get_page_text()

        if "complete sign-up" in page_text or "profile" in current_url:
            print("  [i] Post-login: complete sign-up required.")
            self._handle_complete_signup()

        # Verify login succeeded
        time.sleep(2)
        current_url = self.driver.current_url.lower()
        if "snake" not in current_url and "login" not in current_url:
            print("  [+] TELUS: logged in successfully.")
            return True

        # May still be on login page — poll
        return self._poll_for_login_complete("")

    def _handle_complete_signup(self) -> None:
        """Handle the multi-step TELUS 'Complete sign-up' form.

        Step 1: Address (country, city, address, postal code)
        Step 2: Demographics (DOB, country of birth, gender, education, language, years)
        Step 3: Phone verification (via Sumsub)
        """
        time.sleep(2)
        page_text = self._get_page_text()

        if "complete sign-up" not in page_text:
            return

        print("  [i] Filling 'Complete sign-up' form...")

        # ── Step 1: Address ────────────────────────────────────────
        # Country of Residence (combobox)
        self._fill_combobox("Country of Residence", self.data.get("country", "Australia"))

        # City, State
        city_state = f"{self.data.get('city', 'Melbourne')}, {self.data.get('state', 'Victoria')}"
        self._fill_combobox("City, State", city_state)

        # Address Line 1
        address = self.data.get("street", self.data.get("address_line1", ""))
        if address:
            self.safe_fill(By.XPATH, "//input[contains(@placeholder,'Address Line 1') or contains(@aria-label,'Address Line 1')]", address, timeout=3)

        # Postal code
        postcode = self.data.get("zipcode", self.data.get("postcode", "3000"))
        self.safe_fill(By.XPATH, "//input[contains(@placeholder,'Postal code') or contains(@aria-label,'Postal code')]", postcode, timeout=3)

        # Click Next Step
        time.sleep(1)
        self.safe_click(By.XPATH, "//button[contains(text(),'Next Step')]", timeout=5)
        time.sleep(3)
        self.wait_for_page_load()

        # ── Step 2: Demographics ───────────────────────────────────
        page_text = self._get_page_text()
        if "demographic" in page_text.lower() or "primary language" in page_text.lower():
            print("  [i] Filling demographics...")

            # Date of Birth
            dob = self.data.get("date_of_birth", "02/04/2005")
            self.safe_fill(By.XPATH, "//input[contains(@placeholder,'Date of Birth') or contains(@aria-label,'Date of Birth')]", dob, timeout=3)

            # Country of Birth
            self._fill_combobox("Country of Birth", self.data.get("country_of_birth", "Indonesia"))

            # Gender Identity
            self._fill_combobox("Gender Identity", self.data.get("gender", "Man"))

            # Highest Education
            self._fill_combobox("Highest Education", self.data.get("education_level", "Bachelor"))

            # Primary Language
            self._fill_combobox("Primary Language", "English")

            # Years in country of residence
            self._fill_combobox("yearsOfExperience", self.data.get("years_in_country", "5"))

            # Click Submit
            time.sleep(1)
            self.safe_click(By.XPATH, "//button[contains(text(),'Submit')]", timeout=5)
            time.sleep(3)
            self.wait_for_page_load()

        # ── Step 3: Phone verification (Sumsub iframe) ─────────────
        page_text = self._get_page_text()
        current_url = self.driver.current_url.lower()
        if "phone-verification" in current_url or "verification" in page_text.lower():
            print("  [i] Phone verification step detected.")
            self._handle_phone_verification()

    def _handle_phone_verification(self) -> None:
        """Handle Sumsub phone verification inside iframe."""
        # Try to switch to the Sumsub iframe
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if "sumsub" in src:
                    self.driver.switch_to.frame(iframe)
                    break
        except Exception:
            pass

        # Select country (should auto-detect Australia +61)
        # Fill phone number
        phone = self.data.get("phone", "0480607563")
        # Strip leading 0 for international format
        phone_digits = phone.lstrip("0").replace(" ", "")

        filled = self.safe_fill(By.CSS_SELECTOR, "input[type='tel'], input[placeholder*='Phone']", phone_digits, timeout=5)
        if not filled:
            # Try any visible input
            self.safe_fill(By.XPATH, "//input", phone_digits, timeout=3)

        if filled:
            print(f"  [+] Filled phone: +61 {phone_digits}")

        # Click Send verification code
        self.safe_click(By.XPATH, "//button[contains(text(),'Send verification code')]", timeout=5)
        time.sleep(2)

        # Switch back to main frame
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass

        # Poll for verification completion (user enters SMS code)
        print("  [i] SMS verification code sent. Enter it in the browser. Polling 180s...")
        for i in range(36):
            time.sleep(5)
            current_url = self.driver.current_url.lower()
            if "phone-verification" not in current_url and "profile" not in current_url:
                print("  [+] Phone verification complete.")
                return
            remaining = 180 - (i + 1) * 5
            if remaining > 0 and remaining % 30 == 0:
                print(f"  [i] Waiting for SMS code... {remaining}s remaining")

        print("  [!] Phone verification timeout after 180s.")

    def _fill_combobox(self, label: str, value: str) -> bool:
        """Fill an RC Select / Ant Design combobox by label text, type value, press Enter."""
        # Try by aria-label or placeholder
        for attr in ["aria-label", "placeholder"]:
            filled = self.safe_fill(By.CSS_SELECTOR, f"input[{attr}*='{label}']", value, timeout=3)
            if filled:
                time.sleep(1)
                # Press Enter to select first option via JS
                self.driver.execute_script("""
                    const event = new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', bubbles: true});
                    document.activeElement.dispatchEvent(event);
                """)
                time.sleep(0.5)
                return True

        # Try by nearby label text
        try:
            xpath = (
                f"//label[contains(text(),'{label}')]/following::input[1]"
                f" | //*[contains(text(),'{label}')]/following::input[1]"
            )
            elements = self.driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed():
                    el.clear()
                    el.send_keys(value)
                    time.sleep(1)
                    from selenium.webdriver.common.keys import Keys
                    el.send_keys(Keys.ENTER)
                    time.sleep(0.5)
                    return True
        except Exception:
            pass

        return False

    def _handle_signup_form(self) -> None:
        """Fill the TELUS signup form (first/middle/last name) and click Continue."""
        first_name = self.data.get("first_name", "")
        middle_name = self.data.get("middle_name", "")
        last_name = self.data.get("last_name", "")

        name_fields = [
            (["input[name*='first' i]", "input[placeholder*='First' i]", "input[id*='first' i]"], first_name),
            (["input[name*='middle' i]", "input[placeholder*='Middle' i]", "input[id*='middle' i]"], middle_name),
            (["input[name*='last' i]", "input[placeholder*='Last' i]", "input[id*='last' i]"], last_name),
        ]

        for selectors, value in name_fields:
            if not value:
                continue
            for sel in selectors:
                if self.safe_fill(By.CSS_SELECTOR, sel, value, timeout=3):
                    break

        print(f"  [+] Filled signup name: {first_name} {middle_name} {last_name}")
        time.sleep(1)

        # Click Continue
        self.safe_click(By.XPATH, "//button[contains(text(),'Continue')]", timeout=5)
        time.sleep(3)

    def _poll_for_login_complete(self, login_email: str) -> bool:
        """Poll for up to 180s waiting for login/OTP/verification to complete."""
        if login_email:
            print(f"  [i] Waiting for OTP/verification. Polling 180s...")
        for i in range(36):
            time.sleep(5)
            current_url = self.driver.current_url.lower()
            if not any(kw in current_url for kw in ["snake", "login", "signup", "verify", "otp"]):
                # Check if we need to complete sign-up
                page_text = self._get_page_text()
                if "complete sign-up" in page_text:
                    self._handle_complete_signup()
                print("  [+] TELUS: logged in successfully.")
                return True
            remaining = 180 - (i + 1) * 5
            if remaining > 0 and remaining % 30 == 0:
                print(f"  [i] Still waiting... {remaining}s remaining")

        print("  [!] TELUS login timeout after 180s.")
        return False

    def _fill_email(self, email: str) -> bool:
        """Fill the email input on the TELUS login page."""
        for selector in [
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//label[contains(text(),'Email')]/following::input[1]"),
            (By.XPATH, "//input[@type='text' or @type='email']"),
        ]:
            if self.safe_fill(selector[0], selector[1], email):
                return True
        return False

    def _get_page_text(self) -> str:
        """Get visible page text, lowercased."""
        try:
            return self.driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            return ""
