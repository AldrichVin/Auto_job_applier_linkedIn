"""Ashby ATS handler (jobs.ashbyhq.com)."""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from platforms.base import BasePlatformHandler


class AshbyHandler(BasePlatformHandler):
    """Fill application forms on Ashby-hosted career pages."""

    PLATFORM_NAME = "ashby"

    # Keywords mapped to user data for custom text fields
    _KEYWORD_MAP_KEYS = {
        "phone": "phone",
        "mobile": "phone",
        "linkedin": "linkedin",
        "website": "website",
        "portfolio": "website",
        "github": "github",
        "salary": "desired_salary",
        "notice": "_notice_period",
        "start date": "_notice_period",
        "experience": "years_of_experience",
    }

    def apply(self, url: str, job_info: dict) -> str:
        # Navigate directly to the application page
        app_url = url.rstrip("/")
        if "/application" not in app_url:
            app_url += "/application"

        print("  [>] Ashby: navigating to application form...")
        self.driver.get(app_url)
        self.wait_for_page_load()
        time.sleep(4)  # Ashby forms need time to render React components

        filled_count = 0

        # ── System fields (stable IDs) ─────────────────────────────
        if self.safe_fill(By.ID, "_systemfield_name", self.data["full_name"], timeout=8):
            filled_count += 1
        if self.safe_fill(By.ID, "_systemfield_email", self.data["email"], timeout=5):
            filled_count += 1

        # ── Resume upload ──────────────────────────────────────────
        try:
            self.driver.execute_script("""
                const inp = document.getElementById('_systemfield_resume');
                if (inp) {
                    inp.style.display = 'block';
                    inp.style.opacity = '1';
                    inp.style.position = 'static';
                    inp.style.width = 'auto';
                    inp.style.height = 'auto';
                }
            """)
            time.sleep(1)
            resume_input = self.driver.find_element(By.ID, "_systemfield_resume")
            resume_input.send_keys(self.data["resume_path"])
            filled_count += 1
            print("  [+] Resume uploaded.")
            time.sleep(2)
        except Exception as exc:
            print(f"  [!] Resume upload failed: {exc}")

        # ── Custom fields ──────────────────────────────────────────
        filled_count += self._fill_custom_fields(job_info)

        # ── AI fallback for remaining unknown fields ────────────────
        self.fill_unknown_fields(job_info)

        # ── Highlight submit (user clicks manually) ─────────────────
        if not self.highlight_submit_button(
            By.CSS_SELECTOR,
            "button[class*='submit'], button:has(> span)",
        ):
            # Fallback: highlight by text
            self.driver.execute_script("""
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.trim().toLowerCase().includes('submit application')) {
                        btn.style.border = '4px solid red';
                        btn.style.boxShadow = '0 0 15px red';
                        btn.scrollIntoView({block: 'center'});
                        break;
                    }
                }
            """)

        self.take_screenshot("ashby", "filled")
        print(f"  [+] Ashby: filled {filled_count} fields.")
        return "filled" if filled_count >= 2 else "error"

    def _fill_custom_fields(self, job_info: dict) -> int:
        """Fill custom fields by extracting labels and matching to user data."""
        filled = 0

        try:
            # Get all form field info via JS
            fields = self.driver.execute_script("""
                const results = [];
                // Get all label-like elements
                const containers = document.querySelectorAll('[class*="field"], [class*="question"]');
                // Also get direct form inputs
                const inputs = document.querySelectorAll(
                    'input:not([type="hidden"]):not([type="file"]):not([type="submit"]), textarea'
                );
                for (const inp of inputs) {
                    if (inp.offsetParent === null) continue;
                    if (inp.id && inp.id.startsWith('_systemfield_')) continue;
                    if (inp.value && inp.value.trim()) continue;

                    // Find label text
                    let label = '';
                    // Walk up to find label text
                    let parent = inp.parentElement;
                    for (let i = 0; i < 5 && parent; i++) {
                        const labelEls = parent.querySelectorAll('label, [class*="label"], [class*="title"]');
                        for (const lbl of labelEls) {
                            const txt = lbl.textContent.trim();
                            if (txt && txt.length > 2 && txt.length < 200) {
                                label = txt;
                                break;
                            }
                        }
                        if (label) break;
                        // Also check preceding siblings
                        const prev = parent.previousElementSibling;
                        if (prev && prev.textContent.trim().length < 200) {
                            label = prev.textContent.trim();
                            if (label) break;
                        }
                        parent = parent.parentElement;
                    }

                    if (!label) {
                        label = inp.getAttribute('aria-label') || inp.placeholder || inp.name || '';
                    }

                    results.push({
                        id: inp.id,
                        name: inp.name,
                        type: inp.type,
                        tag: inp.tagName,
                        role: inp.getAttribute('role'),
                        label: label.replace(/\\*$/, '').trim(),
                        placeholder: inp.placeholder
                    });
                }
                return results;
            """)

            if not fields:
                return 0

            for field in fields:
                label = field["label"].lower()
                role = field.get("role", "")

                # Handle location combobox
                if role == "combobox" and any(kw in label for kw in ["location", "located", "city", "where"]):
                    self._fill_location_combobox(field)
                    filled += 1
                    continue

                # Match against keyword map
                for keyword, data_key in self._KEYWORD_MAP_KEYS.items():
                    if keyword in label:
                        if data_key == "_notice_period":
                            value = "Immediately Available"
                        else:
                            value = str(self.data.get(data_key, ""))
                        if value:
                            self._fill_field_by_id_or_name(field, value)
                            filled += 1
                        break

            # Handle Yes/No boolean questions
            filled += self._handle_boolean_questions()

            # Handle cover letter
            filled += self._handle_cover_letter(job_info)

        except Exception as exc:
            print(f"  [!] Custom fields error: {exc}")

        return filled

    def _fill_location_combobox(self, field: dict) -> None:
        """Fill a location combobox by typing and selecting the first match."""
        try:
            selector = f"#{field['id']}" if field["id"] else f"input[role='combobox']"
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            element.clear()
            element.send_keys(self.data.get("city", "Melbourne"))
            time.sleep(2)  # Wait for autocomplete results

            # Click the first matching option
            clicked = self.driver.execute_script("""
                const options = document.querySelectorAll('[role="option"]');
                for (const opt of options) {
                    const text = opt.textContent.trim().toLowerCase();
                    if (text.includes(arguments[0].toLowerCase())) {
                        opt.click();
                        return true;
                    }
                }
                // Click first option as fallback
                if (options.length > 0) {
                    options[0].click();
                    return true;
                }
                return false;
            """, self.data.get("city", "Melbourne"))

            if clicked:
                print(f"  [+] Location combobox filled.")
            else:
                # Fallback: press Enter to select first option
                element.send_keys(Keys.RETURN)
                print(f"  [+] Location combobox filled (Enter key).")
        except Exception as exc:
            print(f"  [!] Location combobox error: {exc}")

    def _fill_field_by_id_or_name(self, field: dict, value: str) -> None:
        """Fill a field by its ID or name."""
        try:
            if field["id"]:
                el = self.driver.find_element(By.ID, field["id"])
            elif field["name"]:
                el = self.driver.find_element(By.NAME, field["name"])
            else:
                return
            el.clear()
            el.send_keys(str(value))
            print(f"  [+] Filled '{field['label'][:40]}' -> '{str(value)[:40]}'")
        except Exception:
            pass

    def _handle_boolean_questions(self) -> int:
        """Find and answer Yes/No boolean button questions."""
        filled = 0
        try:
            # Find all question containers that have Yes/No buttons
            result = self.driver.execute_script("""
                const filled = [];
                // Find text nodes that look like questions
                const allText = document.querySelectorAll('p, span, div, label');
                for (const el of allText) {
                    const text = el.textContent.trim().toLowerCase();
                    if (text.length < 10 || text.length > 300) continue;

                    // Find Yes/No buttons nearby
                    const parent = el.closest('[class*="field"], [class*="question"]')
                        || el.parentElement;
                    if (!parent) continue;

                    const buttons = parent.querySelectorAll('button');
                    let yesBtn = null, noBtn = null;
                    for (const btn of buttons) {
                        const btnText = btn.textContent.trim().toLowerCase();
                        if (btnText === 'yes') yesBtn = btn;
                        if (btnText === 'no') noBtn = btn;
                    }

                    if (!yesBtn || !noBtn) continue;

                    // Determine answer based on question content
                    let answer = 'yes';  // default
                    if (text.includes('sponsor') || text.includes('visa required')) {
                        answer = 'no';
                    }

                    const btn = answer === 'yes' ? yesBtn : noBtn;
                    // Skip if already selected (has active/selected styling)
                    const style = window.getComputedStyle(btn);
                    if (style.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
                        style.backgroundColor !== 'rgb(255, 255, 255)' &&
                        style.backgroundColor !== 'transparent') {
                        continue;  // Already clicked
                    }

                    btn.click();
                    filled.push(text.substring(0, 50) + ' -> ' + answer);
                }
                return filled;
            """)

            if result:
                for entry in result:
                    print(f"  [+] Boolean: {entry}")
                    filled += 1
        except Exception as exc:
            print(f"  [!] Boolean questions error: {exc}")

        return filled

    def _handle_cover_letter(self, job_info: dict) -> int:
        """Fill cover letter textarea if present."""
        cover_text = self.data.get("cover_letter", "")
        if job_info and job_info.get("cover_letter"):
            cover_text = job_info["cover_letter"]
        if not cover_text:
            return 0

        try:
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            for ta in textareas:
                if ta.offsetParent is None:
                    continue
                # Check nearby label
                label = self.driver.execute_script("""
                    let parent = arguments[0].parentElement;
                    for (let i = 0; i < 5 && parent; i++) {
                        const text = parent.textContent.trim().toLowerCase();
                        if (text.includes('cover') || text.includes('letter') ||
                            text.includes('why') || text.includes('message')) {
                            return text.substring(0, 100);
                        }
                        parent = parent.parentElement;
                    }
                    return '';
                """, ta)
                if label:
                    ta.clear()
                    ta.send_keys(cover_text)
                    print("  [+] Cover letter filled.")
                    return 1
        except Exception:
            pass
        return 0
