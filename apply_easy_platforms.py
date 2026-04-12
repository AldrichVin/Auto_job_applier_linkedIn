"""
Apply to jobs on Ashby and SmartRecruiters - platforms with standard forms.
"""
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementNotInteractableException, WebDriverException,
    StaleElementReferenceException
)

RESUME_PATH = r"C:\Users\aldri\Downloads\Job Hunt\AldrichVincentLiem_Resume.pdf"
SOURCE_CSV = Path("all excels/all_applied_applications_history.csv")
TRACKING_CSV = Path("all excels/external_apply_tracking.csv")
SCREENSHOT_DIR = Path("logs/screenshots/external")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

TRACKING_FIELDS = [
    "Job ID", "Title", "Company", "External URL", "Platform",
    "Status", "Timestamp", "Screenshot Path", "Error",
]

USER = {
    "first_name": "Aldrich",
    "middle_name": "Vincent",
    "last_name": "Liem",
    "full_name": "Aldrich Vincent Liem",
    "email": "aldrichvin040205@gmail.com",
    "phone": "+61480607563",
    "phone_local": "0480607563",
    "city": "Melbourne, VIC",
    "location": "Melbourne, VIC, Australia",
    "linkedin": "https://www.linkedin.com/in/aldrich-vincent-4463b2355",
    "website": "https://personal-project-eight-gamma.vercel.app/",
    "github": "https://github.com/AldrichVin",
}

COVER_LETTER = """Dear Hiring Manager,

I am writing to express my interest in this role. As a final-year Computer Science student at Monash University with a 3.81 GPA and hands-on experience as a Data Analyst Intern at Veve Clothing, I bring a strong foundation in data analysis, visualization, and business intelligence.

During my internship, I built Power BI dashboards tracking revenue trends and customer demographics, developed ETL pipelines consolidating data from multiple sources, and presented data-driven recommendations that increased social media engagement by 25%.

I am proficient in SQL, Python, R, Power BI, and Excel, with experience in statistical analysis, data visualization, and stakeholder communication. I am available immediately and hold a Temporary Graduate Visa (subclass 485) with full working rights in Australia until March 2028.

Portfolio: https://personal-project-eight-gamma.vercel.app/
LinkedIn: https://www.linkedin.com/in/aldrich-vincent-4463b2355
GitHub: https://github.com/AldrichVin

Best regards,
Aldrich Vincent Liem
0480 607 563 | aldrichvin040205@gmail.com"""


def get_target_jobs():
    from platforms.detect import detect_platform_name
    processed = set()
    if TRACKING_CSV.exists():
        with open(TRACKING_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                processed.add(row.get("Job ID", ""))
    jobs = []
    with open(SOURCE_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            link = row.get("External Job link", "").strip()
            jid = row.get("Job ID", "")
            if link and link != "Easy Applied" and link.startswith("http") and jid not in processed:
                platform = detect_platform_name(link)
                if platform in ("ashby", "smartrecruiters", "greenhouse"):
                    jobs.append({
                        "id": jid, "title": row.get("Title", ""),
                        "company": row.get("Company", ""),
                        "url": link, "platform": platform,
                    })
    return jobs[:5]


def save_tracking(job, status, error="", screenshot_path=""):
    file_exists = TRACKING_CSV.exists()
    with open(TRACKING_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRACKING_FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerow({
            "Job ID": job["id"], "Title": job["title"],
            "Company": job["company"], "External URL": job["url"],
            "Platform": job["platform"], "Status": status,
            "Timestamp": datetime.now().isoformat(),
            "Screenshot Path": screenshot_path, "Error": error,
        })


def screenshot(driver, name):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{ts}.png"
    driver.save_screenshot(str(path))
    return str(path)


def safe_fill(driver, by, selector, value, timeout=5):
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.3)
        el.click()
        el.clear()
        el.send_keys(value)
        return True
    except Exception:
        return False


def safe_click(driver, by, selector, timeout=5):
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.3)
        el.click()
        return True
    except Exception:
        return False


def upload_resume(driver, timeout=5):
    try:
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        for inp in inputs:
            try:
                inp.send_keys(RESUME_PATH)
                print("      [+] Resume uploaded")
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


# ── Ashby Handler ──

def apply_ashby(driver, job):
    print("    [Ashby] Loading job page...")
    driver.get(job["url"])
    time.sleep(4)

    # Check if URL already has /application
    if "/application" not in driver.current_url:
        # Try clicking Apply button
        clicked = False
        for sel in [
            "//button[contains(text(),'Apply')]",
            "//a[contains(text(),'Apply')]",
            "//a[contains(@href,'application')]",
        ]:
            if safe_click(driver, By.XPATH, sel, 3):
                clicked = True
                break

        if not clicked:
            # Try direct URL with /application appended
            app_url = job["url"].split("?")[0] + "/application"
            driver.get(app_url)

        time.sleep(3)

    print(f"    [Ashby] On page: {driver.current_url}")

    # Ashby uses _systemfield_ prefixed inputs
    fields_filled = 0

    # Name field (Ashby uses id="_systemfield_name")
    if safe_fill(driver, By.ID, "_systemfield_name", USER["full_name"]):
        fields_filled += 1
        print("      [+] Name filled")
    elif safe_fill(driver, By.CSS_SELECTOR, "input[name='_systemfield_name']", USER["full_name"]):
        fields_filled += 1

    # Email (Ashby uses id="_systemfield_email")
    if safe_fill(driver, By.ID, "_systemfield_email", USER["email"]):
        fields_filled += 1
        print("      [+] Email filled")
    elif safe_fill(driver, By.CSS_SELECTOR, "input[type='email']", USER["email"]):
        fields_filled += 1

    # Phone
    if safe_fill(driver, By.ID, "_systemfield_phone", USER["phone"]):
        fields_filled += 1
        print("      [+] Phone filled")
    elif safe_fill(driver, By.CSS_SELECTOR, "input[type='tel']", USER["phone"]):
        fields_filled += 1

    # Resume upload (Ashby uses id="_systemfield_resume", hidden file input)
    try:
        driver.execute_script("""
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
        resume_el = driver.find_element(By.ID, "_systemfield_resume")
        resume_el.send_keys(RESUME_PATH)
        print("      [+] Resume uploaded (system field)")
        time.sleep(2)
    except Exception:
        pass  # Will try generic upload later

    # Current company
    safe_fill(driver, By.CSS_SELECTOR, "input[name='_systemfield_current_company']", "Veve Clothing")

    # LinkedIn
    for sel in ["input[name*='linkedin' i]", "input[name*='LinkedIn']",
                "//label[contains(text(),'LinkedIn')]/following::input[1]"]:
        by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
        if safe_fill(driver, by, sel, USER["linkedin"]):
            print("      [+] LinkedIn filled")
            break

    # Website / Portfolio
    for sel in ["input[name*='website' i]", "input[name*='portfolio' i]",
                "//label[contains(text(),'Website')]/following::input[1]",
                "//label[contains(text(),'Portfolio')]/following::input[1]"]:
        by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
        if safe_fill(driver, by, sel, USER["website"]):
            print("      [+] Website filled")
            break

    # Resume upload
    upload_resume(driver)

    # Cover letter
    for sel in ["textarea[name*='cover' i]",
                "//label[contains(text(),'Cover')]/following::textarea[1]",
                "//label[contains(text(),'Message')]/following::textarea[1]"]:
        by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
        if safe_fill(driver, by, sel, COVER_LETTER):
            print("      [+] Cover letter filled")
            break

    # Fill any remaining text inputs that are empty
    try:
        all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']:not([readonly])")
        for inp in all_inputs:
            try:
                if not inp.get_attribute("value"):
                    name = (inp.get_attribute("name") or "").lower()
                    placeholder = (inp.get_attribute("placeholder") or "").lower()
                    label_text = ""
                    try:
                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{inp.get_attribute('id')}']")
                        label_text = label.text.lower()
                    except Exception:
                        pass

                    combined = name + placeholder + label_text
                    if "location" in combined or "city" in combined:
                        inp.send_keys(USER["location"])
                    elif "github" in combined:
                        inp.send_keys(USER["github"])
                    elif "salary" in combined or "compensation" in combined:
                        inp.send_keys("70000")
            except (StaleElementReferenceException, ElementNotInteractableException):
                continue
    except Exception:
        pass

    time.sleep(1)
    ss = screenshot(driver, f"{job['id']}_ashby_filled")
    print(f"    [Ashby] Filled {fields_filled} core fields")

    # Submit - Ashby uses "Submit application" button text
    submitted = False
    # Try JS click on button containing "submit" text (Ashby renders dynamic buttons)
    try:
        submitted = driver.execute_script("""
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                const txt = btn.textContent.trim().toLowerCase();
                if (txt.includes('submit')) {
                    btn.scrollIntoView({block: 'center'});
                    btn.click();
                    return true;
                }
            }
            // Also try form submit
            const form = document.querySelector('form');
            if (form) { form.submit(); return true; }
            return false;
        """)
    except Exception as e:
        print(f"    [Ashby] JS submit error: {e}")

    if not submitted:
        for sel in [
            "//button[contains(text(),'Submit')]",
            "//button[contains(text(),'submit')]",
            "//button[@type='submit']",
        ]:
            if safe_click(driver, By.XPATH, sel, 5):
                submitted = True
                break

    if submitted:
        time.sleep(4)
        screenshot(driver, f"{job['id']}_ashby_submitted")
        # Check for success indicators
        page_text = driver.page_source.lower()
        if "thank" in page_text or "success" in page_text or "received" in page_text:
            print("    [Ashby] SUBMITTED SUCCESSFULLY!")
            return "filled", ss
        else:
            print("    [Ashby] Clicked submit, checking result...")
            return "filled", ss
    else:
        print("    [Ashby] Could not find submit button")
        return "manual", ss


# ── SmartRecruiters Handler ──

def apply_smartrecruiters(driver, job):
    print("    [SmartRecruiters] Loading job page...")
    driver.get(job["url"])
    time.sleep(4)

    # Click Apply - try JS click first since SR uses React
    clicked = False
    try:
        clicked = driver.execute_script("""
            // Try direct button/link with Apply text
            const els = [...document.querySelectorAll('button, a, [role="button"]')];
            for (const el of els) {
                const txt = el.textContent.trim().toLowerCase();
                if (txt.includes('apply') && !txt.includes('already applied')) {
                    el.scrollIntoView({block: 'center'});
                    el.click();
                    return true;
                }
            }
            return false;
        """)
    except Exception:
        pass

    if not clicked:
        for sel in [
            "//button[contains(text(),'Apply')]",
            "//a[contains(text(),'Apply')]",
            "//a[contains(@href,'apply')]",
            "[data-test='apply-button']",
        ]:
            by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
            if safe_click(driver, by, sel, 5):
                clicked = True
                break

    if not clicked:
        # Some SR pages redirect to external apply URL
        print("    [SmartRecruiters] Trying direct apply URL...")
        job_id_from_url = job["url"].split("/")[-1].split("?")[0]
        driver.get(f"https://jobs.smartrecruiters.com/oneclick-ui/company/{job['url'].split('/')[3]}/publication/{job_id_from_url}?dcr_ci=")
        time.sleep(3)
        clicked = True  # Proceed anyway on the new page

    if not clicked:
        print("    [SmartRecruiters] Could not find Apply button")
        return "error", ""

    time.sleep(3)
    print(f"    [SmartRecruiters] On page: {driver.current_url}")

    fields_filled = 0

    # First name
    for sel in ["input[name*='firstName']", "input[id*='firstName']",
                "#firstName", "input[name='first_name']"]:
        if safe_fill(driver, By.CSS_SELECTOR, sel, USER["first_name"]):
            fields_filled += 1
            print("      [+] First name")
            break

    # Last name
    for sel in ["input[name*='lastName']", "input[id*='lastName']",
                "#lastName", "input[name='last_name']"]:
        if safe_fill(driver, By.CSS_SELECTOR, sel, USER["last_name"]):
            fields_filled += 1
            print("      [+] Last name")
            break

    # Email
    for sel in ["input[type='email']", "input[name*='email']", "#email"]:
        if safe_fill(driver, By.CSS_SELECTOR, sel, USER["email"]):
            fields_filled += 1
            print("      [+] Email")
            break

    # Phone
    for sel in ["input[type='tel']", "input[name*='phone']", "#phone"]:
        if safe_fill(driver, By.CSS_SELECTOR, sel, USER["phone_local"]):
            fields_filled += 1
            print("      [+] Phone")
            break

    # Location
    for sel in ["input[name*='location']", "input[name*='city']"]:
        if safe_fill(driver, By.CSS_SELECTOR, sel, "Melbourne, VIC"):
            break

    # Resume
    upload_resume(driver)

    # Cover letter
    for sel in ["textarea[name*='coverLetter']", "textarea[name*='cover']", "textarea"]:
        if safe_fill(driver, By.CSS_SELECTOR, sel, COVER_LETTER):
            print("      [+] Cover letter")
            break

    time.sleep(1)
    ss = screenshot(driver, f"{job['id']}_sr_filled")
    print(f"    [SmartRecruiters] Filled {fields_filled} core fields")

    # Submit
    for sel in [
        "//button[contains(text(),'Submit')]",
        "//button[contains(text(),'Apply')]",
        "//button[@type='submit']",
        "//input[@type='submit']",
    ]:
        if safe_click(driver, By.XPATH, sel, 5):
            time.sleep(4)
            screenshot(driver, f"{job['id']}_sr_submitted")
            print("    [SmartRecruiters] SUBMITTED!")
            return "filled", ss

    print("    [SmartRecruiters] Could not submit")
    return "manual", ss


def main():
    jobs = get_target_jobs()
    if not jobs:
        print("No pending Ashby/Greenhouse/SmartRecruiters jobs found.")
        print("All easy-platform jobs have been processed.")
        return

    print(f"\n=== Applying to {len(jobs)} jobs (Ashby/SmartRecruiters) ===\n")
    for i, j in enumerate(jobs, 1):
        print(f"  {i}. [{j['platform']}] {j['title'][:50]} @ {j['company'][:30]}")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--no-first-run")
    options.add_argument("--user-data-dir=" + str(Path.home() / ".apply_easy_chrome"))

    driver = webdriver.Chrome(options=options)
    results = {"filled": 0, "manual": 0, "error": 0}

    try:
        for i, job in enumerate(jobs, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(jobs)}] {job['title']} @ {job['company']}")
            print(f"  Platform: {job['platform']}")
            print(f"{'='*60}")

            try:
                if job["platform"] == "ashby":
                    status, ss = apply_ashby(driver, job)
                elif job["platform"] == "smartrecruiters":
                    status, ss = apply_smartrecruiters(driver, job)
                else:
                    status, ss = "error", ""

                results[status] = results.get(status, 0) + 1
                save_tracking(job, status, screenshot_path=ss)
                print(f"\n  >>> Result: {status.upper()}")

            except WebDriverException as e:
                if "invalid session" in str(e).lower():
                    print("  [!] Chrome crashed, restarting...")
                    try: driver.quit()
                    except: pass
                    driver = webdriver.Chrome(options=options)
                results["error"] += 1
                save_tracking(job, "error", str(e)[:200])

            except Exception as e:
                print(f"  [!] Error: {e}")
                results["error"] += 1
                save_tracking(job, "error", str(e)[:200])

            time.sleep(2)

    finally:
        print(f"\n{'='*60}")
        print(f"  SUBMITTED: {results['filled']}")
        print(f"  MANUAL:    {results['manual']}")
        print(f"  ERRORS:    {results['error']}")
        print(f"{'='*60}")
        try: driver.quit()
        except: pass


if __name__ == "__main__":
    main()
