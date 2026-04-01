"""URL-to-platform routing logic."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from platforms.base import BasePlatformHandler
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.action_chains import ActionChains

# Pattern list: (url_substring, module_name, class_name)
PLATFORM_PATTERNS: list[tuple[str, str, str]] = [
    ("seek.com.au", "platforms.seek", "SeekHandler"),
    ("indeed.com", "platforms.indeed", "IndeedHandler"),
    ("myworkdayjobs.com", "platforms.workday", "WorkdayHandler"),
    ("myworkdaysite.com", "platforms.workday", "WorkdayHandler"),
    ("myworkday.com", "platforms.workday", "WorkdayHandler"),
    ("greenhouse.io", "platforms.greenhouse", "GreenhouseHandler"),
    ("jobs.lever.co", "platforms.lever", "LeverHandler"),
    ("lever.co/apply", "platforms.lever", "LeverHandler"),
    ("jobs.smartrecruiters.com", "platforms.smartrecruiters", "SmartRecruitersHandler"),
    ("michaelpage.com", "platforms.michaelpage", "MichaelPageHandler"),
    ("pagepersonnel.com", "platforms.michaelpage", "MichaelPageHandler"),
    ("jobs.dayforcehcm.com", "platforms.dayforce", "DayforceHandler"),
    ("app.dataannotation.tech", "platforms.dataannotation", "DataAnnotationHandler"),
    ("telusinternational.ai", "platforms.telus", "TelusHandler"),
    ("jobs.telusdigital.com", "platforms.telus", "TelusHandler"),
]


def detect_platform_name(url: str) -> str:
    """Return the platform name for a URL, or 'generic'."""
    url_lower = url.lower()
    for pattern, module_name, _ in PLATFORM_PATTERNS:
        if pattern in url_lower:
            return module_name.split(".")[-1]
    return "generic"


def detect_platform(
    url: str,
    driver: "WebDriver",
    wait: "WebDriverWait",
    actions: "ActionChains",
    user_data: dict,
) -> "BasePlatformHandler":
    """Detect which platform a URL belongs to and return the appropriate handler."""
    import importlib

    url_lower = url.lower()
    for pattern, module_name, class_name in PLATFORM_PATTERNS:
        if pattern in url_lower:
            try:
                module = importlib.import_module(module_name)
                handler_class = getattr(module, class_name)
                return handler_class(driver, wait, actions, user_data)
            except (ImportError, AttributeError) as exc:
                print(f"  [!] Handler {class_name} not yet implemented: {exc}")
                break

    # Fallback to generic handler
    from platforms.generic import GenericHandler
    return GenericHandler(driver, wait, actions, user_data)
