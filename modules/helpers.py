'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''


# Imports

import os
import sys
import json
import pathlib

from time import sleep
from random import randint
from datetime import datetime, timedelta
try:
    from pyautogui import alert as _pyautogui_alert
except (ImportError, KeyError, Exception):
    _pyautogui_alert = None
from pprint import pprint

from config.settings import logs_folder_path


def show_alert(message: str, title: str = "Alert", button: str = "OK"):
    """Show alert dialog with pyautogui, fallback to print if unavailable."""
    if _pyautogui_alert:
        try:
            return _pyautogui_alert(message, title, button)
        except Exception:
            pass
    print(f"[ALERT] {title}: {message}")
    return button


#### Common functions ####

#< Directories related
def make_directories(paths: list[str]) -> None:
    '''
    Function to create missing directories
    '''
    for path in paths:
        path = os.path.expanduser(path) # Expands ~ to user's home directory
        path = path.replace("//","/")
        
        # If path looks like a file path, get the directory part
        if '.' in os.path.basename(path):
            path = os.path.dirname(path)

        if not path: # Handle cases where path is empty after dirname
            continue

        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True) # exist_ok=True avoids race condition
        except Exception as e:
            print(f'Error while creating directory "{path}": ', e)


def get_default_temp_profile() -> str:
    # Thanks to https://github.com/vinodbavage31 for suggestion!
    home = pathlib.Path.home()
    if sys.platform.startswith('win'):
        return "--user-data-dir=C:\\temp\\auto-job-apply-profile"
    elif sys.platform.startswith('linux'):
        return str(home / ".auto-job-apply-profile")
    return str(home / "Library" / "Application Support" / "Google" / "Chrome" / "auto-job-apply-profile")


def find_default_profile_directory() -> str | None:
    '''
    Dynamically finds the default Google Chrome 'User Data' directory path
    across Windows, macOS, and Linux, regardless of OS version.

    Returns the absolute path as a string, or None if the path is not found.
    '''
    
    home = pathlib.Path.home()
    
    # Windows
    if sys.platform.startswith('win'):
        paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\Google\Chrome\User Data"),
            os.path.expandvars(r"%USERPROFILE%\Local Settings\Application Data\Google\Chrome\User Data")
        ]
    # Linux
    elif sys.platform.startswith('linux'):
        paths = [
            str(home / ".config" / "google-chrome"),
            str(home / ".var" / "app" / "com.google.Chrome" / "data" / ".config" / "google-chrome"),
        ]
    # MacOS ## For some reason, opening with profile in MacOS is not creating a session for undetected-chromedriver!
    # elif sys.platform == 'darwin':
    #     paths = [
    #         str(home / "Library" / "Application Support" / "Google" / "Chrome")
    #     ]
    else:
        return None

    # Check each potential path and return the first one that exists
    for path_str in paths:
        if os.path.exists(path_str):
            return path_str
            
    return None
#>


#< Logging related
def critical_error_log(possible_reason: str, stack_trace: Exception) -> None:
    '''
    Function to log and print critical errors along with datetime stamp
    '''
    print_lg(possible_reason, stack_trace, datetime.now(), from_critical=True)


def get_log_path():
    '''
    Function to replace '//' with '/' for logs path
    '''
    try:
        path = logs_folder_path+"/log.txt"
        return path.replace("//","/")
    except Exception as e:
        critical_error_log("Failed getting log path! So assigning default logs path: './logs/log.txt'", e)
        return "logs/log.txt"


__logs_file_path = get_log_path()


def print_lg(*msgs: str | dict, end: str = "\n", pretty: bool = False, flush: bool = False, from_critical: bool = False) -> None:
    '''
    Function to log and print. **Note that, `end` and `flush` parameters are ignored if `pretty = True`**
    '''
    try:
        for message in msgs:
            try:
                pprint(message) if pretty else print(message, end=end, flush=flush)
            except UnicodeEncodeError:
                safe_msg = str(message).encode('ascii', errors='replace').decode('ascii')
                pprint(safe_msg) if pretty else print(safe_msg, end=end, flush=flush)
            with open(__logs_file_path, 'a+', encoding="utf-8") as file:
                file.write(str(message) + end)
    except Exception as e:
        trail = f'Skipped saving this message to log.txt!' if from_critical else "We'll try one more time to log..."
        show_alert(f"log.txt in {logs_folder_path} is open or is occupied by another program! Please close it! {trail}", "Failed Logging")
        if not from_critical:
            critical_error_log("Log.txt is open or is occupied by another program!", e)
#>


def buffer(speed: int=0) -> None:
    '''
    Function to wait within a period of selected random range.
    * Will not wait if input `speed <= 0`
    * Will wait within a random range of 
      - `0.6 to 1.0 secs` if `1 <= speed < 2`
      - `1.0 to 1.8 secs` if `2 <= speed < 3`
      - `1.8 to speed secs` if `3 <= speed`
    '''
    if speed<=0:
        return
    elif speed <= 1 and speed < 2:
        return sleep(randint(6,10)*0.1)
    elif speed <= 2 and speed < 3:
        return sleep(randint(10,18)*0.1)
    else:
        return sleep(randint(18,round(speed)*10)*0.1)
    

def manual_login_retry(is_logged_in: callable, limit: int = 2) -> None:
    '''
    Function to ask and validate manual login
    '''
    count = 0
    while not is_logged_in():
        print_lg("Seems like you're not logged in!")
        button = "Confirm Login"
        message = 'After you successfully Log In, please click "{}" button below.'.format(button)
        if count > limit:
            button = "Skip Confirmation"
            message = 'If you\'re seeing this message even after you logged in, Click "{}". Seems like auto login confirmation failed!'.format(button)
        count += 1
        if show_alert(message, "Login Required", button) and count > limit: return



def calculate_date_posted(time_string: str) -> datetime | None | ValueError:
    '''
    Function to calculate date posted from string.
    Returns datetime object | None if unable to calculate | ValueError if time_string is invalid
    Valid time string examples:
    * 10 seconds ago
    * 15 minutes ago
    * 2 hours ago
    * 1 hour ago
    * 1 day ago
    * 10 days ago
    * 1 week ago
    * 1 month ago
    * 1 year ago
    '''
    import re
    time_string = time_string.strip()
    now = datetime.now()

    match = re.search(r'(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', time_string, re.IGNORECASE)

    if match:
        try:
            value = int(match.group(1))
            unit = match.group(2).lower()

            if 'second' in unit:
                return now - timedelta(seconds=value)
            elif 'minute' in unit:
                return now - timedelta(minutes=value)
            elif 'hour' in unit:
                return now - timedelta(hours=value)
            elif 'day' in unit:
                return now - timedelta(days=value)
            elif 'week' in unit:
                return now - timedelta(weeks=value)
            elif 'month' in unit:
                return now - timedelta(days=value * 30)  # Approximation
            elif 'year' in unit:
                return now - timedelta(days=value * 365)  # Approximation
        except (ValueError, IndexError):
            # Fallback for cases where parsing fails
            pass
    
    # If regex doesn't match, or parsing failed, return None.
    # This will skip jobs where the date can't be determined, preventing crashes.
    return None


def convert_to_lakhs(value: str) -> str:
    '''
    Converts str value to lakhs, no validations are done except for length and stripping.
    Examples:
    * "100000" -> "1.00"
    * "101,000" -> "10.1," Notice ',' is not removed 
    * "50" -> "0.00"
    * "5000" -> "0.05" 
    '''
    value = value.strip()
    l = len(value)
    if l > 0:
        if l > 5:
            value = value[:l-5] + "." + value[l-5:l-3]
        else:
            value = "0." + "0"*(5-l) + value[:2]
    return value


def convert_to_json(data) -> dict:
    '''
    Function to convert data to JSON, if unsuccessful, returns `{"error": "Unable to parse the response as JSON", "data": data}`
    '''
    try:
        result_json = json.loads(data)
        return result_json
    except json.JSONDecodeError:
        return {"error": "Unable to parse the response as JSON", "data": data}


def truncate_for_csv(data, max_length: int = 131000, suffix: str = "...[TRUNCATED]") -> str:
    '''
    Function to truncate data for CSV writing to avoid field size limit errors.
    * Takes in `data` of any type and converts to string
    * Takes in `max_length` of type `int` - maximum allowed length (default: 131000, leaving room for suffix)
    * Takes in `suffix` of type `str` - text to append when truncated
    * Returns truncated string if data exceeds max_length
    '''
    try:
        # Convert data to string
        str_data = str(data) if data is not None else ""
        
        # If within limit, return as-is
        if len(str_data) <= max_length:
            return str_data
        
        # Truncate and add suffix
        truncated = str_data[:max_length - len(suffix)] + suffix
        return truncated
    except Exception as e:
        return f"[ERROR CONVERTING DATA: {e}]"


# ── Cookie Persistence ─────────────────────────────────────────────────
import re as _re
import logging as _logging

COOKIE_DIR = pathlib.Path(".auth")


def save_cookies(driver, platform: str) -> None:
    """Save browser cookies for a platform to disk."""
    COOKIE_DIR.mkdir(exist_ok=True)
    cookies = driver.get_cookies()
    cookie_file = COOKIE_DIR / f"{platform}_cookies.json"
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    print_lg(f"  [+] Cookies saved for {platform} ({len(cookies)} cookies)")


def load_cookies(driver, platform: str, domain: str) -> bool:
    """Load saved cookies for a platform. Returns True if cookies were loaded."""
    cookie_file = COOKIE_DIR / f"{platform}_cookies.json"
    if not cookie_file.exists():
        return False
    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        driver.get(domain)
        for cookie in cookies:
            cookie.pop("sameSite", None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        driver.refresh()
        print_lg(f"  [+] Cookies loaded for {platform} ({len(cookies)} cookies)")
        return True
    except Exception as exc:
        print_lg(f"  [!] Cookie load failed for {platform}: {exc}")
        return False


# ── Question Bank ──────────────────────────────────────────────────────

class QuestionBank:
    """Regex-pattern matched Q&A bank for common screening questions."""

    def __init__(self, json_path: str = "config/question_bank.json"):
        self.entries: list[dict] = []
        self._load(json_path)

    def _load(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data.get("questions", []):
                compiled = [_re.compile(p, _re.IGNORECASE) for p in entry.get("patterns", [])]
                self.entries.append({
                    "compiled_patterns": compiled,
                    "answer": entry["answer"],
                    "type": entry.get("type", "text"),
                })
        except FileNotFoundError:
            pass
        except Exception as exc:
            print_lg(f"  [!] Question bank load error: {exc}")

    def match(self, question_text: str) -> str | None:
        """Return answer if question matches any pattern, else None."""
        text = question_text.strip().lower()
        for entry in self.entries:
            for pattern in entry["compiled_patterns"]:
                if pattern.search(text):
                    return entry["answer"]
        return None


# ── Structured Logging ─────────────────────────────────────────────────

_structured_logger = _logging.getLogger("autoapply")
try:
    _structured_handler = _logging.FileHandler(
        logs_folder_path.rstrip("/") + "/structured.log", encoding="utf-8"
    )
    _structured_handler.setFormatter(_logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))
    _structured_logger.addHandler(_structured_handler)
    _structured_logger.setLevel(_logging.DEBUG)
except Exception:
    pass


def log_structured(message: str, level: str = "INFO") -> None:
    """Write to structured log file with timestamp and level."""
    log_level = getattr(_logging, level.upper(), _logging.INFO)
    _structured_logger.log(log_level, str(message))