"""Generic fallback handler — opens the URL without filling any forms."""

from platforms.base import BasePlatformHandler


class GenericHandler(BasePlatformHandler):
    """Fallback handler for unsupported platforms.

    Simply opens the URL in the browser so the user can apply manually.
    """

    PLATFORM_NAME = "generic"

    def apply(self, url: str, job_info: dict) -> str:
        title = job_info.get("title", "Unknown")
        company = job_info.get("company", "Unknown")
        print(f"  [i] No handler for this platform. Opening URL for manual apply.")
        print(f"      Job: {title} @ {company}")
        print(f"      URL: {url}")

        self.driver.get(url)
        self.wait_for_page_load()
        self.take_screenshot(job_info.get("job_id", "unknown"), "manual")

        return "manual"
