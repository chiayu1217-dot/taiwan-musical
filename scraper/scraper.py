import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OPENTIX_URL = (
    "https://www.opentix.life/search/%20/ABOUT_TO_BEGIN"
    "?category=%E6%88%B2%E5%8A%87-%E9%9F%B3%E6%A8%82%E5%8A%87&type=programs"
)

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "shows.json"

REGION_KEYWORDS = {
    "台北": ["台北", "水源", "國家戲劇", "中山堂", "信義", "松菸", "城市舞台", "新舞臺", "牯嶺街"],
    "台中": ["台中", "臺中", "中正堂", "歌劇院"],
    "高雄": ["高雄", "衛武營", "大東", "駁二"],
}


def guess_region(venue: str) -> str:
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw in venue for kw in keywords):
            return region
    return "其他"


def normalize_price(raw: str) -> str:
    if not raw or raw.strip() in ("免費", "免費入場", "0"):
        return ""
    nums = re.findall(r"\d+", raw)
    if len(nums) >= 2:
        return f"{nums[0]}-{nums[-1]}"
    if len(nums) == 1:
        return nums[0]
    return ""


def build_show_id(program_id: str, date: str, time_str: str) -> str:
    time_compact = time_str.replace(":", "")
    return f"{program_id}-{date}-{time_compact}"


def scrape_shows() -> list[dict]:
    shows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        print(f"Loading: {OPENTIX_URL}")
        page.goto(OPENTIX_URL, wait_until="domcontentloaded", timeout=30000)
        # Wait for program links to appear (React app needs time to hydrate)
        try:
            page.wait_for_selector("a[href*='/program/']", timeout=15000)
        except Exception:
            pass  # proceed even if selector not found; program_links will be empty
        time.sleep(1)

        program_links = page.eval_on_selector_all(
            "a[href*='/program/']",
            "els => [...new Set(els.map(e => e.href))]"
        )
        print(f"Found {len(program_links)} program links")

        for link in program_links:
            try:
                shows.extend(scrape_program(browser, link))
                time.sleep(1.5)
            except Exception as e:
                print(f"Error scraping {link}: {e}")

        browser.close()
    return shows


def scrape_program(browser, url: str) -> list[dict]:
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)  # give React time to render session data

        program_id = url.rstrip("/").split("/")[-1]

        title_el = page.query_selector("h1, .program-title, [class*='title']")
        title = title_el.inner_text().strip() if title_el else "未知節目"

        sessions = page.eval_on_selector_all(
            "[class*='session'], [class*='performance'], [class*='schedule']",
            """els => els.map(el => ({
                text: el.innerText,
                html: el.innerHTML
            }))"""
        )

        results = []
        for session in sessions:
            text = session["text"]
            date_match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
            if not date_match:
                continue
            date_str = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"

            time_match = re.search(r"(\d{1,2}):(\d{2})", text)
            time_str = f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else "00:00"

            venue_match = re.search(r"(劇院|劇場|舞台|中心|堂|廳|廣場|藝廊|場館)[^\n]*", text)
            venue = venue_match.group(0).strip() if venue_match else "待確認"

            price_match = re.search(r"(NT\$|NT |新台幣|免費)?[\d,]+\s*[-~至到]\s*[\d,]+", text)
            price = normalize_price(price_match.group(0)) if price_match else ""

            results.append({
                "id": build_show_id(program_id, date_str, time_str),
                "title": title,
                "region": guess_region(venue),
                "venue": venue,
                "date": date_str,
                "time": time_str,
                "price": price,
                "url": url,
            })

        return results
    finally:
        page.close()


if __name__ == "__main__":
    shows = scrape_shows()

    if not shows:
        print("No shows scraped — keeping existing data")
    else:
        OUTPUT_PATH.write_text(
            json.dumps(shows, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Wrote {len(shows)} sessions to {OUTPUT_PATH}")
