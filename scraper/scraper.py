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
    "台北": ["台北", "臺北", "水源", "國家戲劇", "中山堂", "信義", "松菸", "城市舞台", "新舞臺", "牯嶺街", "南村", "PLAYground"],
    "台中": ["台中", "臺中", "中正堂", "歌劇院"],
    "高雄": ["高雄", "衛武營", "大東", "駁二"],
    "新竹": ["新竹", "竹科"],
    "屏東": ["屏東"],
    "苗栗": ["苗栗"],
}

REGION_TEXT_MAP = {
    "臺北": "台北",
    "台北": "台北",
    "臺中": "台中",
    "台中": "台中",
    "高雄": "高雄",
    "新竹": "新竹",
    "屏東": "屏東",
    "苗栗": "苗栗",
}


def guess_region(venue: str) -> str:
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw in venue for kw in keywords):
            return region
    return "其他"


def normalize_price(raw: str) -> str:
    if not raw or raw.strip() in ("免費", "免費入場", "0"):
        return ""
    # Match numbers with optional commas (e.g. 1,500)
    nums = [n.replace(",", "") for n in re.findall(r"\d[\d,]*", raw)]
    if len(nums) >= 2:
        return f"{nums[0]}-{nums[-1]}"
    if len(nums) == 1:
        return nums[0]
    return ""


def build_show_id(event_id: str, date: str, time_str: str) -> str:
    time_compact = time_str.replace(":", "")
    return f"{event_id}-{date}-{time_compact}"


def parse_region_from_text(text: str) -> str:
    """Parse region from search result card text (e.g. '臺北', '高雄')."""
    for raw, normalized in REGION_TEXT_MAP.items():
        if raw in text:
            return normalized
    return "其他"


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
        try:
            page.wait_for_selector("a[href*='/event/']", timeout=15000)
        except Exception:
            pass
        time.sleep(2)

        # Click "顯示更多" until all results are loaded
        while True:
            try:
                more_btn = page.query_selector("button:has-text('顯示更多')")
                if not more_btn:
                    break
                more_btn.click()
                time.sleep(1.5)
            except Exception:
                break

        # Collect event metadata from search result cards
        event_meta = page.evaluate("""
            () => {
                const links = [...document.querySelectorAll('a[href*="/event/"]')];
                const seen = new Set();
                const results = [];
                for (const a of links) {
                    const href = a.href;
                    if (seen.has(href)) continue;
                    seen.add(href);
                    // Walk up to find unique card container
                    let container = a;
                    for (let i = 0; i < 8; i++) {
                        container = container.parentElement;
                        if (!container) break;
                        const evtLinks = container.querySelectorAll('a[href*="/event/"]');
                        if (evtLinks.length === 1) break;
                    }
                    const text = container ? container.innerText : a.innerText;
                    results.push({ href, text });
                }
                return results;
            }
        """)

        print(f"Found {len(event_meta)} events")

        for meta in event_meta:
            try:
                url = meta["href"]
                card_text = meta["text"]
                event_id = url.rstrip("/").split("/")[-1]

                # Parse price from card text: $1,500 - $2,400
                price_match = re.search(r"\$[\d,]+\s*-\s*\$[\d,]+", card_text)
                price = normalize_price(price_match.group(0)) if price_match else ""

                # Parse region from card text
                region_from_card = parse_region_from_text(card_text)

                shows.extend(scrape_event(browser, url, event_id, price, region_from_card))
                time.sleep(1)
            except Exception as e:
                print(f"Error scraping {meta.get('href')}: {e}")

        browser.close()
    return shows


def scrape_event(browser, url: str, event_id: str, price: str, region_from_card: str) -> list[dict]:
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        try:
            page.wait_for_selector("h1", timeout=8000)
        except Exception:
            pass
        time.sleep(2)

        # Title
        title_el = page.query_selector("h1")
        title = title_el.inner_text().strip() if title_el else "未知節目"

        # Sessions: each span.mr-2 contains date+time, its parent text has venue
        sessions_data = page.evaluate("""
            () => {
                const spans = [...document.querySelectorAll('span.mr-2')];
                const dateSpans = spans.filter(s => /\\d{4}\\/\\d{1,2}\\/\\d{1,2}/.test(s.innerText));
                return dateSpans.map(s => ({
                    datetime: s.innerText.trim(),
                    parentText: s.parentElement ? s.parentElement.innerText.trim() : ''
                }));
            }
        """)

        results = []
        seen_ids = set()

        for session in sessions_data:
            dt_text = session["datetime"]
            parent_text = session["parentText"]

            # Parse date: 2026/6/10 (三) 19:30
            date_match = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", dt_text)
            if not date_match:
                continue
            date_str = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"

            # Parse time
            time_match = re.search(r"(\d{1,2}):(\d{2})", dt_text)
            time_str = f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else "00:00"

            # Extract venue from parent text (lines after the datetime line)
            lines = [l.strip() for l in parent_text.split("\n") if l.strip()]
            venue = "待確認"
            for line in lines:
                # Skip the datetime line and ticket type lines
                if re.search(r"\d{4}/\d{1,2}/\d{1,2}", line):
                    continue
                if "電子票" in line or "實體票" in line:
                    continue
                if len(line) > 2:
                    venue = line
                    break

            region = guess_region(venue) if venue != "待確認" else region_from_card

            show_id = build_show_id(event_id, date_str, time_str)
            if show_id in seen_ids:
                continue
            seen_ids.add(show_id)

            results.append({
                "id": show_id,
                "title": title,
                "region": region,
                "venue": venue,
                "date": date_str,
                "time": time_str,
                "price": price,
                "url": url,
            })

        # Fallback: if no sessions found via span.mr-2, use card data
        if not results:
            print(f"  No sessions found for {title}, skipping")

        return results
    finally:
        page.close()


if __name__ == "__main__":
    shows = scrape_shows()

    if not shows:
        print("No shows scraped — keeping existing data")
    else:
        # Deduplicate by id
        seen = {}
        for show in shows:
            seen[show["id"]] = show
        deduped = list(seen.values())
        OUTPUT_PATH.write_text(
            json.dumps(deduped, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Wrote {len(deduped)} sessions to {OUTPUT_PATH}")
