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

        # ── Try to fill any visible form fields ─────────────────────

        filled = self._try_fill_form(job_info)

        if filled > 0:
            print(f"  [+] Generic: filled {filled} fields.")
            return "filled"

        print(f"  [i] Generic: opened page, filled {filled} fields. Manual apply needed.")
        return "manual"

    def _click_apply_button(self) -> bool:
        """Try clicking various common Apply button patterns."""
        selectors = [
            (By.XPATH, "//a[contains(translate(text(),'APPLY','apply'),'apply')]"),
            (By.XPATH, "//button[contains(translate(text(),'APPLY','apply'),'apply')]"),
            (By.XPATH, "//a[contains(translate(text(),'APPLY','apply'),'apply for')]"),
            (By.XPATH, "//button[contains(translate(text(),'APPLY','apply'),'apply for')]"),
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
        filled += self._try_fill_input(["city", "location", "suburb"], self.data["city"])

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
