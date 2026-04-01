"""Michael Page job application handler (michaelpage.com.au)."""

import time

from selenium.webdriver.common.by import By

from platforms.base import BasePlatformHandler


class MichaelPageHandler(BasePlatformHandler):
    """Fill application forms on Michael Page career pages."""

    PLATFORM_NAME = "michaelpage"

    def apply(self, url: str, job_info: dict) -> str:
        print("  [>] Michael Page: navigating to application page...")
        self.driver.get(url)
        self.wait_for_page_load()
        time.sleep(3)

        try:
            self._step_1_apply_method()
            self._step_2_personal_information()
            self._step_3_employment_details()
        except Exception as exc:
            print(f"  [!] Michael Page error: {exc}")
            return "error"

        # Highlight submit button without clicking
        self.highlight_submit_button(
            By.XPATH,
            "//button[contains(text(),'Apply Now')]",
        )

        print("  [+] Michael Page: form filled successfully.")
        return "filled"

    def _step_1_apply_method(self) -> None:
        """Click 'Apply with CV' and enter email address."""
        print("  [>] Step 1: Apply method...")

        self.safe_click(
            By.XPATH,
            "//a[contains(text(),'Apply with CV')]",
            timeout=10,
        )
        time.sleep(2)

        self.safe_fill(
            By.XPATH,
            "//label[text()='Enter your email address']/following::input[1]",
            self.data["email"],
        )
        time.sleep(1)

        self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Navigate to personal information')]",
            timeout=5,
        )
        time.sleep(3)

    def _step_2_personal_information(self) -> None:
        """Fill personal information fields and upload CV."""
        print("  [>] Step 2: Personal information...")

        self.safe_fill(
            By.XPATH,
            "//label[text()='First name']/following::input[1]",
            self.data["first_name"],
        )

        self.safe_fill(
            By.XPATH,
            "//label[text()='Surname']/following::input[1]",
            self.data["last_name"],
        )

        self.safe_fill(
            By.XPATH,
            "//label[text()='Phone Number']/following::input[1]",
            self.data["phone"],
        )

        self.safe_fill(
            By.XPATH,
            "//label[text()='Postcode']/following::input[1]",
            self.data["postcode"],
        )

        self.safe_fill(
            By.XPATH,
            "//label[text()='City or town you live in']/following::input[1]",
            self.data["city"],
        )

        self._select_no_for_aboriginal_question()
        self._upload_cv()

        time.sleep(1)

        self.safe_click(
            By.XPATH,
            "//button[contains(text(),'Navigate to employment information')]",
            timeout=5,
        )
        time.sleep(3)

    def _select_no_for_aboriginal_question(self) -> None:
        """Select 'No' for the Aboriginal/Torres Strait Islander question."""
        try:
            self.driver.execute_script("""
                const radios = document.querySelectorAll('input[type="radio"]');
                for (const radio of radios) {
                    const label = radio.closest('label')
                        || document.querySelector(`label[for="${radio.id}"]`);
                    if (label && label.textContent.trim() === 'No') {
                        radio.click();
                        break;
                    }
                }
            """)
            print("  [+] Selected 'No' for Aboriginal/Torres Strait Islander question.")
        except Exception as exc:
            print(f"  [!] Could not select Aboriginal question radio: {exc}")

    def _upload_cv(self) -> None:
        """Upload CV via the hidden file input."""
        try:
            self.driver.execute_script("""
                const fileInput = document.getElementById('edit-field-cv-0-upload');
                if (fileInput) {
                    fileInput.style.display = 'block';
                }
            """)
            time.sleep(1)

            self.safe_upload(
                By.ID,
                "edit-field-cv-0-upload",
                self.data["resume_path"],
                timeout=5,
            )
            print("  [+] CV uploaded successfully.")
            time.sleep(3)
        except Exception as exc:
            print(f"  [!] CV upload error: {exc}")

    def _step_3_employment_details(self) -> None:
        """Fill employment detail dropdowns and fields."""
        print("  [>] Step 3: Employment details...")

        # Industry
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select Industry"]',
            "Technology & Telecoms",
        )
        time.sleep(1)

        # Sub Industry (enabled after Industry is selected)
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select Sub Industry"]',
            "Technology",
        )
        time.sleep(1)

        # Department
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select Department"]',
            "Analytics",
        )
        time.sleep(1)

        # Role
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select Role"]',
            "Data Analyst",
        )
        time.sleep(1)

        # Current Job Title
        self.safe_fill(
            By.XPATH,
            "//label[text()='Current (or most recent) Job Title']/following::input[1]",
            self.data["current_job_title"],
        )

        # Experience Level
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select Experience level"]',
            "Entry Level",
        )

        # Preferred job type
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select Preferred job type"]',
            "Permanent, but open to contract roles",
        )

        # Notice period
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select your notice Period"]',
            "Immediately Available",
        )

        # Currency
        self.safe_select(
            By.CSS_SELECTOR,
            'select[aria-label="Select Currency type"]',
            "AUD",
        )

        # Annual salary
        self.safe_fill(
            By.CSS_SELECTOR,
            "input[name*='annual_salary']",
            str(self.data["current_salary"]),
        )

        # Privacy consent — check all unchecked checkboxes
        self._check_consent_boxes()

    def _check_consent_boxes(self) -> None:
        """Check all unchecked consent/privacy checkboxes."""
        try:
            checkboxes = self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='checkbox']"
            )
            for checkbox in checkboxes:
                if not checkbox.is_selected():
                    try:
                        self._scroll_into_view(checkbox)
                        checkbox.click()
                        print("  [+] Checked consent checkbox.")
                    except Exception:
                        try:
                            self.driver.execute_script(
                                "arguments[0].click();", checkbox
                            )
                            print("  [+] Checked consent checkbox via JS.")
                        except Exception:
                            pass
        except Exception as exc:
            print(f"  [!] Checkbox error: {exc}")
