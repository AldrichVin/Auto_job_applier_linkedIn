"""Base class for all platform handlers."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

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

SCREENSHOT_DIR = Path("logs/screenshots/external")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class BasePlatformHandler(ABC):
    """Abstract base class for platform-specific form fillers."""

    PLATFORM_NAME = "unknown"

    def __init__(
        self,
        driver: WebDriver,
        wait: WebDriverWait,
        actions: ActionChains,
        user_data: dict,
    ):
        self.driver = driver
        self.wait = wait
        self.actions = actions
        self.data = user_data

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
