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
        return 0
