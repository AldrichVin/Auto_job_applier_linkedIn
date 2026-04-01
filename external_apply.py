"""
External Job Auto-Apply Script

Reads external job URLs from the LinkedIn bot's CSV and auto-fills
application forms on Seek, Indeed, and major ATS platforms.

Does NOT submit applications — pauses for user review and manual submit.

Usage:
    python external_apply.py
    python external_apply.py --dry-run
    python external_apply.py --platform greenhouse --limit 5
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from config.personals import (
    first_name, middle_name, last_name,
    phone_number, current_city, street, state, zipcode, country,
    ethnicity, gender, disability_status, veteran_status,
)
from config.questions import (
    years_of_experience, require_visa, website, linkedIn,
    us_citizenship, desired_salary, current_ctc, notice_period,
    linkedin_headline, linkedin_summary, cover_letter,
    recent_employer, confidence_level,
)
from platforms.detect import detect_platform, detect_platform_name

def _create_chrome_session():
    """Create a clean Chrome session independent of the LinkedIn bot."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait

    options = Options()
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized")
    # Use a temp profile to avoid conflicts with existing Chrome sessions
    temp_profile = Path.home() / ".external_apply_chrome_profile"
    options.add_argument(f"--user-data-dir={temp_profile}")

    try:
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        wait = WebDriverWait(driver, 10)
        actions = ActionChains(driver)
        print("[+] Chrome session created.")
        return driver, wait, actions
    except Exception as exc:
        print(f"[!] Chrome error: {exc}")
        # Retry without custom profile
        try:
            options2 = Options()
            options2.add_argument("--disable-extensions")
            options2.add_argument("--start-maximized")
            driver = webdriver.Chrome(options=options2)
            driver.maximize_window()
            wait = WebDriverWait(driver, 10)
            actions = ActionChains(driver)
            print("[+] Chrome session created (guest profile).")
            return driver, wait, actions
        except Exception as exc2:
            print(f"[!] Chrome retry failed: {exc2}")
            return None, None, None


# ── Constants ───────────────────────────────────────────────────────────

SOURCE_CSV = Path("all excels/all_applied_applications_history.csv")
TRACKING_CSV = Path("all excels/external_apply_tracking.csv")
RESUME_PATH = r"C:\Users\aldri\Downloads\Job Hunt\AldrichVincentLiem_Resume.pdf"

TRACKING_FIELDS = [
    "Job ID", "Title", "Company", "External URL", "Platform",
    "Status", "Timestamp", "Screenshot Path", "Error",
]


def build_user_data() -> dict:
    """Consolidate all config into a single dict for handlers."""
    full_name = " ".join(filter(None, [first_name, middle_name, last_name]))
    return {
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": "aldrichvin040205@gmail.com",
        "phone": "+61" + phone_number.lstrip("0") if not phone_number.startswith("+") else phone_number,
        "city": current_city,
        "state": state,
        "zipcode": zipcode,
        "country": country,
        "street": street,
        "years_of_experience": years_of_experience,
        "require_visa": require_visa,
        "visa_details": "Temporary Graduate Visa subclass 485, expires 11 March 2028. Full working rights.",
        "desired_salary": desired_salary,
        "current_ctc": current_ctc,
        "notice_period": notice_period,
        "current_employer": recent_employer,
        "website": website,
        "linkedin": linkedIn,
        "linkedin_headline": linkedin_headline,
        "linkedin_summary": linkedin_summary.strip(),
        "cover_letter": cover_letter.strip(),
        "resume_path": RESUME_PATH,
        "gender": gender,
        "ethnicity": ethnicity,
        "disability_status": disability_status,
        "veteran_status": veteran_status,
        "us_citizenship": us_citizenship,
        "confidence_level": confidence_level,
        "education_degree": "Bachelor of Computer Science",
        "education_university": "Monash University",
        "github": "https://github.com/AldrichVin",
        "postcode": "3006",
        "aboriginal_or_tsi": "No",
        "industry": "Retail",
        "sub_industry": "Fashion / Apparel",
        "department": "Analytics",
        "role_category": "Data Analyst",
        "current_job_title": "Data Analyst Intern",
        "experience_level": "Entry Level",
        "preferred_job_type": "Permanent, but open to contract roles",
        "notice_period_label": "Immediately Available",
        "current_salary": "60000",
        "salary_currency": "AUD",
        "prefix": "Mr",
        "address_line1": "2704/58 Clarke St, Southbank",
        "preferred_contact_method": "Email",
        "referral_source": "LinkedIn",
        "login_email": "aldrichvin05@gmail.com",
        "login_password": "AldrichVin040205@",
    }


def generate_cover_letter(job_info: dict, user_data: dict) -> str:
    """Generate a tailored cover letter based on job title, company, and description.

    Falls back to the default cover letter from config if no match.
    """
    title = job_info.get("title", "").lower()
    company = job_info.get("company", "").lower()

    # Check for gaming / product analyst roles
    is_gaming = any(kw in company for kw in ["tripledot", "game", "gaming", "zynga", "supercell", "king", "playdots", "rovio"])
    is_product = "product" in title

    if is_gaming or is_product:
        return _gaming_product_analyst_letter(job_info, user_data)

    # Default: return the standard cover letter
    return user_data["cover_letter"]


def _gaming_product_analyst_letter(job_info: dict, user_data: dict) -> str:
    company_name = job_info.get("company", "your company").strip()
    role_title = job_info.get("title", "Product Analyst").strip()
    return f"""Dear Hiring Team at {company_name},

I am writing to express my strong interest in the {role_title} position. As a final-year Computer Science student at Monash University (GPA: 3.81/4.0) with hands-on experience in data analysis, I am drawn to the opportunity to apply analytical thinking to player behavior and product decisions in mobile gaming.

During my internship as a Data Analyst at Veve Clothing, I built interactive Power BI dashboards tracking revenue trends and customer demographics, developed ETL pipelines consolidating data from multiple sources, and presented data-driven recommendations to stakeholders that increased social media engagement by 25%. This experience taught me to translate complex data into actionable insights — a skill directly applicable to optimizing game KPIs and player experiences.

My academic projects demonstrate the technical depth this role requires:

- NBA Player Ranking System: Built a statistical modeling pipeline analyzing player performance metrics (scoring, efficiency, consistency) using MongoDB, Flask, and Docker. This mirrors the player behavior segmentation and engagement analysis central to product analytics in gaming — identifying patterns, building meaningful segments, and ranking by composite metrics.

- MonEquip Data Warehousing: Designed a star schema data warehouse with interactive Power BI dashboards using advanced SQL (CTEs, window functions, stored procedures). Conducted pre/post analysis on equipment utilization trends — directly analogous to measuring the impact of product changes and A/B tests.

- Australia Weather Visualization: Built an end-to-end ETL pipeline processing 10+ years of data with geospatial visualizations, demonstrating my ability to work with large-scale datasets and create compelling visual narratives.

- DataPraktis: Developed a full-stack marketplace (Next.js, PostgreSQL, TypeScript) connecting SMBs with data analysts, giving me product-side experience in user journey design and understanding how data drives feature decisions.

I am proficient in SQL, Python, R, Power BI, and Excel, with experience in statistical analysis, data visualization, and A/B testing concepts. I am particularly excited about the opportunity to analyze player engagement, monetization, and retention patterns — the analytical challenge of understanding what makes players love a game deeply resonates with me.

I hold a Temporary Graduate Visa (subclass 485) with full working rights in Australia until March 2028 and am available to start immediately.

Portfolio: {user_data['website']}
LinkedIn: {user_data['linkedin']}
GitHub: {user_data['github']}

I would welcome the opportunity to discuss how my analytical skills and passion for data-driven decision-making align with {company_name}'s mission.

Best regards,
Aldrich Vincent Liem
{user_data['phone']} | {user_data['email']}"""


# ── CSV helpers ─────────────────────────────────────────────────────────

def load_external_jobs(csv_path: Path) -> list[dict]:
    """Read LinkedIn bot CSV, return rows with real external URLs."""
    if not csv_path.exists():
        print(f"[!] Source CSV not found: {csv_path}")
        return []

    jobs: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            link = row.get("External Job link", "").strip()
            if link and link != "Easy Applied" and link.startswith("http"):
                jobs.append({
                    "job_id": row.get("Job ID", ""),
                    "title": row.get("Title", "Unknown"),
                    "company": row.get("Company", "Unknown"),
                    "external_url": link,
                    "job_link": row.get("Job Link", ""),
                    "cover_letter": row.get("Cover Letter", ""),
                })
    return jobs


def load_processed_ids(tracking_path: Path) -> set[str]:
    """Return set of Job IDs already processed."""
    if not tracking_path.exists():
        return set()

    processed: set[str] = set()
    with open(tracking_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed.add(row.get("Job ID", ""))
    return processed


def save_tracking_record(tracking_path: Path, record: dict):
    """Append one row to the tracking CSV."""
    file_exists = tracking_path.exists()
    with open(tracking_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKING_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="External job auto-apply script")
    parser.add_argument("--dry-run", action="store_true", help="List jobs without opening browser")
    parser.add_argument("--platform", type=str, default="", help="Only process jobs from this platform (e.g., greenhouse, seek)")
    parser.add_argument("--limit", type=int, default=0, help="Max number of jobs to process")
    parser.add_argument("--auto", action="store_true", help="Non-blocking batch mode (no pauses except OTP)")
    args = parser.parse_args()

    # Load jobs and filter
    print("\n=== External Job Auto-Apply ===\n")
    all_jobs = load_external_jobs(SOURCE_CSV)
    processed_ids = load_processed_ids(TRACKING_CSV)

    jobs = [j for j in all_jobs if j["job_id"] not in processed_ids]

    # Deduplicate by URL (keep first occurrence)
    seen_urls: set[str] = set()
    unique_jobs: list[dict] = []
    for j in jobs:
        url_key = j["external_url"].split("?")[0]  # Strip query params for dedup
        if url_key not in seen_urls:
            seen_urls.add(url_key)
            unique_jobs.append(j)
        else:
            # Auto-mark duplicates as skipped
            save_tracking_record(TRACKING_CSV, {
                "Job ID": j["job_id"], "Title": j["title"], "Company": j["company"],
                "External URL": j["external_url"], "Platform": detect_platform_name(j["external_url"]),
                "Status": "skipped", "Timestamp": datetime.now().isoformat(),
                "Screenshot Path": "", "Error": "Duplicate URL",
            })
    jobs = unique_jobs

    if args.platform:
        jobs = [
            j for j in jobs
            if detect_platform_name(j["external_url"]) == args.platform
        ]

    if args.limit > 0:
        jobs = jobs[:args.limit]

    print(f"Source CSV: {SOURCE_CSV}")
    print(f"Total external jobs in CSV: {len(all_jobs)}")
    print(f"Already processed: {len(processed_ids)}")
    print(f"Jobs to process this run: {len(jobs)}")

    if not jobs:
        print("\nNo new external jobs to process.")
        return

    # Dry run — just list jobs
    if args.dry_run:
        print("\n-- DRY RUN --\n")
        for i, job in enumerate(jobs, 1):
            platform = detect_platform_name(job["external_url"])
            print(f"  {i}. [{platform}] {job['title']} @ {job['company']}")
            print(f"     {job['external_url'][:100]}")
        print(f"\nTotal: {len(jobs)} jobs would be processed.")
        return

    # Build user data
    user_data = build_user_data()

    # Initialize AI client for answering unknown form questions
    ai_client = None
    ai_cache: dict = {}
    ai_cache_path = Path("logs/ai_answer_cache.json")
    if ai_cache_path.exists():
        try:
            with open(ai_cache_path, "r", encoding="utf-8") as f:
                ai_cache = json.load(f)
            print(f"[+] Loaded AI answer cache ({len(ai_cache)} entries)")
        except Exception:
            ai_cache = {}

    try:
        from config.secrets import use_AI, llm_api_url, llm_api_key, llm_model
        if use_AI:
            from openai import OpenAI
            ai_client = OpenAI(base_url=llm_api_url, api_key=llm_api_key)
            print(f"[+] AI client initialized (model: {llm_model})")
        else:
            print("[i] AI disabled in config (use_AI=False). Unknown fields will be skipped.")
    except ImportError:
        print("[i] AI not configured. Unknown form fields will be skipped.")
    except Exception as exc:
        print(f"[!] AI init failed: {exc}. Continuing without AI.")

    # Verify resume exists
    if not Path(RESUME_PATH).exists():
        print(f"[!] Resume not found at: {RESUME_PATH}")
        print("    Please update RESUME_PATH in external_apply.py")
        sys.exit(1)

    # Create a clean Chrome session (separate from LinkedIn bot)
    driver, wait, actions = _create_chrome_session()
    if not driver:
        print("[!] Failed to create Chrome session.")
        sys.exit(1)

    # Track stats
    stats = {"filled": 0, "error": 0, "skipped": 0, "manual": 0}

    # Login to platforms that require it
    logged_in_platforms: set[str] = set()

    try:
        for i, job in enumerate(jobs, 1):
            job_id = job["job_id"]
            url = job["external_url"]
            title = job["title"]
            company = job["company"]
            platform_name = detect_platform_name(url)

            print(f"\n[{i}/{len(jobs)}] {title} @ {company}")
            print(f"  Platform: {platform_name}")
            print(f"  URL: {url[:100]}")

            handler = detect_platform(url, driver, wait, actions, user_data, ai_client, ai_cache)

            # Login once per platform
            if platform_name not in logged_in_platforms and platform_name not in ("generic",):
                try:
                    if handler.login():
                        logged_in_platforms.add(platform_name)
                    else:
                        print(f"  [!] Login failed for {platform_name}, skipping all jobs on this platform")
                        save_tracking_record(TRACKING_CSV, {
                            "Job ID": job_id, "Title": title, "Company": company,
                            "External URL": url, "Platform": platform_name,
                            "Status": "error", "Timestamp": datetime.now().isoformat(),
                            "Screenshot Path": "", "Error": "Login failed",
                        })
                        stats["error"] += 1
                        continue
                except Exception as exc:
                    print(f"  [!] Login error for {platform_name}: {exc}")
                    logged_in_platforms.add(platform_name)  # Don't retry login

            # Generate tailored cover letter for this job
            job["cover_letter"] = generate_cover_letter(job, user_data)

            # Apply (fill form)
            screenshot_path = ""
            error_msg = ""
            try:
                status = handler.apply(url, job)
                screenshot_path = handler.take_screenshot(job_id)
            except Exception as exc:
                status = "error"
                error_msg = str(exc)[:500]
                print(f"  [!] Error: {exc}")
                try:
                    screenshot_path = handler.take_screenshot(job_id, "error")
                except Exception:
                    pass

            stats[status] = stats.get(status, 0) + 1

            # Save tracking record
            save_tracking_record(TRACKING_CSV, {
                "Job ID": job_id, "Title": title, "Company": company,
                "External URL": url, "Platform": platform_name,
                "Status": status, "Timestamp": datetime.now().isoformat(),
                "Screenshot Path": screenshot_path, "Error": error_msg,
            })

            # In auto mode: continue immediately. Otherwise: brief pause.
            if status in ("filled", "manual"):
                print(f"  [OK] Form ready for review. Screenshot: {screenshot_path}")
                if not args.auto:
                    import time
                    time.sleep(2)  # Brief pause between jobs

    except KeyboardInterrupt:
        print("\n\n[i] Interrupted by user.")
    finally:
        # Save AI answer cache
        if ai_cache:
            try:
                ai_cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(ai_cache_path, "w", encoding="utf-8") as f:
                    json.dump(ai_cache, f, indent=2)
                print(f"\n[+] AI answer cache saved ({len(ai_cache)} entries)")
            except Exception as exc:
                print(f"[!] Could not save AI cache: {exc}")

        # Print summary
        print("\n\n=== Summary ===")
        print(f"  Forms filled:     {stats['filled']}")
        print(f"  Manual (opened):  {stats['manual']}")
        print(f"  Errors:           {stats['error']}")
        print(f"  Skipped:          {stats['skipped']}")
        total = sum(stats.values())
        print(f"  Total processed:  {total}")
        print(f"\nTracking saved to: {TRACKING_CSV}")

        # Wait for user to review before closing browser
        if driver and not args.auto:
            try:
                input("\nPress Enter to close browser...")
            except Exception:
                pass
            try:
                driver.quit()
            except Exception:
                pass
        elif driver:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
