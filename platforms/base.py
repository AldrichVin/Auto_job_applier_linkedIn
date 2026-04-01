"""Base class for all platform handlers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)

if TYPE_CHECKING:
    from openai import OpenAI

SCREENSHOT_DIR = Path("logs/screenshots/external")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class BasePlatformHandler(ABC):
    """Abstract base class for platform-specific form fillers."""

    PLATFORM_NAME = "unknown"

    # Labels to skip when filling unknown fields (already handled by known-field logic)
    _SKIP_LABELS = re.compile(
        r"first.?name|last.?name|surname|email|phone|mobile|tel|resume|cv|upload|file",
        re.IGNORECASE,
    )

    def __init__(
        self,
        driver: WebDriver,
        wait: WebDriverWait,
        actions: ActionChains,
        user_data: dict,
        ai_client: "OpenAI | None" = None,
        ai_cache: dict | None = None,
    ):
        self.driver = driver
        self.wait = wait
        self.actions = actions
        self.data = user_data
        self.ai_client = ai_client
        self.ai_cache = ai_cache if ai_cache is not None else {}

    @abstractmethod
    def apply(self, url: str, job_info: dict) -> str:
        """Navigate to URL, fill form fields, return status string.

        Must NOT click the submit/apply button.
        Returns: 'filled', 'error', 'skipped', or 'manual'.
        """

    def login(self) -> bool:
        """Override if the platform requires authentication. Returns True on success."""
        return True

    # ── Shared utility methods ──────────────────────────────────────────

    def safe_fill(
        self,
        by: str,
        locator: str,
        value: str,
        clear_first: bool = True,
        timeout: int = 5,
    ) -> bool:
        """Find an input element and type a value. Returns True on success."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, locator))
            )
            self._scroll_into_view(element)
            if clear_first:
                element.clear()
            element.send_keys(value)
            return True
        except (NoSuchElementException, TimeoutException, ElementNotInteractableException) as exc:
            print(f"  [!] Could not fill '{locator}': {exc.__class__.__name__}")
            return False

    def safe_select(
        self, by: str, locator: str, value: str, timeout: int = 5
    ) -> bool:
        """Find a <select> element and choose an option by visible text."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, locator))
            )
            select = Select(element)
            try:
                select.select_by_visible_text(value)
            except NoSuchElementException:
                # Try partial match
                for option in select.options:
                    if value.lower() in option.text.lower():
                        select.select_by_visible_text(option.text)
                        return True
                return False
            return True
        except (NoSuchElementException, TimeoutException) as exc:
            print(f"  [!] Could not select '{locator}': {exc.__class__.__name__}")
            return False

    def safe_upload(
        self, by: str, locator: str, file_path: str, timeout: int = 5
    ) -> bool:
        """Find a file input and upload a file."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, locator))
            )
            element.send_keys(file_path)
            return True
        except (NoSuchElementException, TimeoutException) as exc:
            print(f"  [!] Could not upload to '{locator}': {exc.__class__.__name__}")
            return False

    def safe_click(self, by: str, locator: str, timeout: int = 5) -> bool:
        """Find and click an element."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, locator))
            )
            self._scroll_into_view(element)
            element.click()
            return True
        except (NoSuchElementException, TimeoutException, ElementNotInteractableException) as exc:
            print(f"  [!] Could not click '{locator}': {exc.__class__.__name__}")
            return False

    def fill_text_area(
        self, by: str, locator: str, text: str, timeout: int = 5
    ) -> bool:
        """Fill a textarea with long text (cover letter, etc.)."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, locator))
            )
            self._scroll_into_view(element)
            element.clear()
            element.send_keys(text)
            return True
        except (NoSuchElementException, TimeoutException, ElementNotInteractableException) as exc:
            print(f"  [!] Could not fill textarea '{locator}': {exc.__class__.__name__}")
            return False

    def take_screenshot(self, job_id: str, label: str = "filled") -> str:
        """Save a screenshot and return the file path."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
        filename = f"{job_id}_{self.PLATFORM_NAME}_{label}_{timestamp}.png"
        filepath = SCREENSHOT_DIR / filename
        self.driver.save_screenshot(str(filepath))
        print(f"  [+] Screenshot saved: {filepath}")
        return str(filepath)

    def wait_for_page_load(self, timeout: int = 15):
        """Wait for the page to finish loading."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def highlight_submit_button(self, by: str, locator: str, timeout: int = 5) -> bool:
        """Find the submit button and highlight it visually WITHOUT clicking."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, locator))
            )
            self._scroll_into_view(element)
            self.driver.execute_script(
                "arguments[0].style.border = '4px solid red';"
                "arguments[0].style.boxShadow = '0 0 15px red';",
                element,
            )
            return True
        except (NoSuchElementException, TimeoutException):
            return False

    # ── Private helpers ─────────────────────────────────────────────────

    def _scroll_into_view(self, element: WebElement):
        """Scroll element into viewport."""
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            element,
        )

    # ── AI-powered field filling ───────────────────────────────────────

    def ai_answer_field(
        self,
        question_text: str,
        options: list[str] | None = None,
        question_type: str = "text",
        job_info: dict | None = None,
    ) -> str | None:
        """Use AI to answer a form question. Returns answer or None."""
        cache_key = question_text.strip().lower()
        if cache_key in self.ai_cache:
            return self.ai_cache[cache_key]

        if not self.ai_client:
            return None

        try:
            from modules.ai.openaiConnections import ai_answer_question

            result = ai_answer_question(
                client=self.ai_client,
                question=question_text,
                options=options,
                question_type=question_type,
                user_information_all=self._build_user_info_string(),
                job_description=job_info.get("description", "") if job_info else None,
                stream=False,
            )
            answer = result if isinstance(result, str) else str(result)
            self.ai_cache[cache_key] = answer
            return answer
        except Exception as exc:
            print(f"  [!] AI answer error for '{question_text[:50]}': {exc}")
            return None

    def _build_user_info_string(self) -> str:
        """Format user data into a resume-like string for AI context."""
        d = self.data
        return (
            f"Name: {d.get('full_name', '')}\n"
            f"Email: {d.get('email', '')}\n"
            f"Phone: {d.get('phone', '')}\n"
            f"Location: {d.get('city', '')}, {d.get('state', '')}, {d.get('country', '')}\n"
            f"Address: {d.get('address_line1', '')}\n"
            f"Postcode: {d.get('postcode', '')}\n"
            f"Education: {d.get('education_degree', '')} from {d.get('education_university', '')}\n"
            f"Current Role: {d.get('current_job_title', '')}\n"
            f"Experience: {d.get('years_of_experience', '')} years\n"
            f"Visa: {d.get('visa_details', d.get('require_visa', ''))}\n"
            f"Desired Salary: {d.get('desired_salary', '')} {d.get('salary_currency', '')}\n"
            f"Notice Period: {d.get('notice_period_label', d.get('notice_period', ''))}\n"
            f"LinkedIn: {d.get('linkedin', '')}\n"
            f"Website: {d.get('website', '')}\n"
            f"GitHub: {d.get('github', '')}\n"
        )

    def fill_unknown_fields(self, job_info: dict | None = None) -> int:
        """Find empty visible form fields, extract labels, fill with AI. Returns count."""
        if not self.ai_client:
            return 0

        filled = 0
        try:
            # Get all form field info via JS
            fields = self.driver.execute_script("""
                const results = [];
                const inputs = document.querySelectorAll(
                    'input, textarea, select'
                );
                for (const el of inputs) {
                    if (el.offsetParent === null) continue;  // hidden
                    const type = (el.type || '').toLowerCase();
                    if (['file', 'hidden', 'submit', 'button', 'image', 'reset'].includes(type)) continue;
                    if (type === 'checkbox' || type === 'radio') continue;
                    // Skip if already has a value
                    if (el.value && el.value.trim()) continue;

                    // Extract label text
                    let label = '';
                    if (el.id) {
                        const labelEl = document.querySelector(`label[for="${el.id}"]`);
                        if (labelEl) label = labelEl.textContent.trim();
                    }
                    if (!label) {
                        const parentLabel = el.closest('label');
                        if (parentLabel) label = parentLabel.textContent.trim();
                    }
                    if (!label) label = el.getAttribute('aria-label') || '';
                    if (!label) label = el.getAttribute('placeholder') || '';
                    if (!label) label = el.getAttribute('name') || '';

                    if (!label) continue;

                    // Get select options if applicable
                    let options = null;
                    if (el.tagName === 'SELECT') {
                        options = Array.from(el.options)
                            .map(o => o.text.trim())
                            .filter(t => t && t !== '--' && t !== 'Select');
                    }

                    results.push({
                        tag: el.tagName,
                        type: type,
                        id: el.id,
                        name: el.name,
                        label: label,
                        options: options,
                        index: results.length
                    });
                }
                return results;
            """)

            if not fields:
                return 0

            for field in fields:
                label = field["label"]
                if self._SKIP_LABELS.search(label):
                    continue

                q_type = "text"
                if field["tag"] == "TEXTAREA":
                    q_type = "textarea"
                elif field["tag"] == "SELECT":
                    q_type = "single_select"

                answer = self.ai_answer_field(
                    label,
                    options=field.get("options"),
                    question_type=q_type,
                    job_info=job_info,
                )
                if not answer:
                    continue

                # Fill the field
                try:
                    if field["tag"] == "SELECT":
                        selector = f"#{field['id']}" if field["id"] else f"[name='{field['name']}']"
                        self.safe_select(By.CSS_SELECTOR, selector, answer)
                    else:
                        selector = f"#{field['id']}" if field["id"] else f"[name='{field['name']}']"
                        self.safe_fill(By.CSS_SELECTOR, selector, answer)
                    filled += 1
                    print(f"  [AI] Filled '{label[:40]}' → '{answer[:40]}'")
                except Exception:
                    pass

        except Exception as exc:
            print(f"  [!] fill_unknown_fields error: {exc}")

        return filled
