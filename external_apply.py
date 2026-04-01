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
        "phone": phone_number,
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
    }


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
    args = parser.parse_args()

    # Load jobs and filter
    print("\n=== External Job Auto-Apply ===\n")
    all_jobs = load_external_jobs(SOURCE_CSV)
    processed_ids = load_processed_ids(TRACKING_CSV)

    jobs = [j for j in all_jobs if j["job_id"] not in processed_ids]

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

    # Verify resume exists
    if not Path(RESUME_PATH).exists():
        print(f"[!] Resume not found at: {RESUME_PATH}")
        print("    Please update RESUME_PATH in external_apply.py")
        sys.exit(1)

    # Create Chrome session
    from modules.open_chrome import createChromeSession
    driver, wait, actions = None, None, None
    try:
        driver, wait, actions = createChromeSession()
    except Exception as exc:
        print(f"[!] Failed to create Chrome session: {exc}")
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

            handler = detect_platform(url, driver, wait, actions, user_data)

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

            # Pause for user to review and submit manually
            if status in ("filled", "manual"):
                try:
                    import pyautogui
                    decision = pyautogui.confirm(
                        f"Form filled for:\n\n"
                        f"  {title} @ {company}\n"
                        f"  Platform: {platform_name}\n\n"
                        f"Review the form and click Submit manually.\n"
                        f"Then click OK to continue to the next job.",
                        "External Apply - Review & Submit",
                        ["OK - Next Job", "Stop - End Session"],
                    )
                    if decision == "Stop - End Session":
                        print("\n[i] User ended session.")
                        break
                except Exception:
                    input("  Press Enter to continue to the next job...")

    except KeyboardInterrupt:
        print("\n\n[i] Interrupted by user.")
    finally:
        # Print summary
        print("\n\n=== Summary ===")
        print(f"  Forms filled:     {stats['filled']}")
        print(f"  Manual (opened):  {stats['manual']}")
        print(f"  Errors:           {stats['error']}")
        print(f"  Skipped:          {stats['skipped']}")
        total = sum(stats.values())
        print(f"  Total processed:  {total}")
        print(f"\nTracking saved to: {TRACKING_CSV}")

        # Close browser
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
