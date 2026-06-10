import datetime
import json
import re
import time
import urllib.request
from pathlib import Path

SEARCH_API = "https://search.opentix.life/search"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "shows.json"
PAGE_SIZE = 15

# Shows categorized differently in opentix API (not under 戲劇-音樂劇)
# but are still musicals — add their sessions manually here
SUPPLEMENTAL_SHOWS = [
    {
        "event_id": "2054129876962353153",
        "title": "新北市生音藝術節-韓國音樂劇《或許是美好結局》世巡首站",
        "venue": "新北市藝文中心演藝廳",
        "region": "北部",
        "price": "1400-4800",
        "image_url": "https://s3.resource.opentix.life/upload/program/1779438031759xYpDvXFGFq.jpeg",
        "sessions": [
            "2026-07-31 19:30", "2026-08-01 14:30", "2026-08-01 19:30",
            "2026-08-02 14:30", "2026-08-02 19:30", "2026-08-04 19:30",
            "2026-08-05 19:30", "2026-08-06 19:30", "2026-08-07 19:30",
            "2026-08-08 14:30", "2026-08-08 19:30", "2026-08-09 14:30",
        ],
    },
]

REGION_KEYWORDS = {
    "北部": ["台北", "臺北", "新北", "基隆", "桃園", "新竹", "水源", "國家戲劇", "國家音樂廳", "台北中山堂", "臺北中山堂", "信義", "松菸", "城市舞台", "新舞臺", "牯嶺街", "南村", "PLAYground", "臺灣戲曲中心", "陽明交通大學", "交通大學光復", "樹林", "文山"],
    "中部": ["台中", "臺中", "苗栗", "彰化", "南投", "雲林", "中正堂", "臺中國家歌劇院", "幽谷書屋"],
    "南部": ["高雄", "嘉義", "台南", "臺南", "屏東", "衛武營", "大東", "駁二", "恆春"],
    "東部": ["宜蘭", "花蓮", "台東", "臺東"],
    "離島": ["澎湖", "金門", "馬祖"],
}

REGION_TEXT_MAP = {
    "臺北": "北部", "台北": "北部",
    "新北": "北部", "基隆": "北部",
    "桃園": "北部", "新竹": "北部",
    "臺中": "中部", "台中": "中部",
    "苗栗": "中部", "彰化": "中部",
    "南投": "中部", "雲林": "中部",
    "高雄": "南部", "嘉義": "南部",
    "台南": "南部", "臺南": "南部",
    "屏東": "南部",
    "宜蘭": "東部", "花蓮": "東部", "台東": "東部", "臺東": "東部",
    "澎湖": "離島", "金門": "離島", "馬祖": "離島",
}


def guess_region(venue: str) -> str:
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw in venue for kw in keywords):
            return region
    return "其他"


def normalize_price(raw: str) -> str:
    if not raw or raw.strip() in ("免費", "免費入場", "0"):
        return ""
    nums = [n.replace(",", "") for n in re.findall(r"\d[\d,]*", raw)]
    if len(nums) >= 2:
        return f"{nums[0]}-{nums[-1]}"
    if len(nums) == 1:
        return nums[0]
    return ""


def build_show_id(event_id: str, date: str, time_str: str) -> str:
    return f"{event_id}-{date}-{time_str.replace(':', '')}"


def _api_post(offset: int) -> dict:
    payload = json.dumps({
        "language": "zh-CHT",
        "categoryFilter": ["戲劇-音樂劇"],
        "offset": offset,
        "sortBy": "ABOUT_TO_BEGIN",
    }).encode("utf-8")
    req = urllib.request.Request(
        SEARCH_API,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Origin": "https://www.opentix.life",
            "Referer": "https://www.opentix.life/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_sessions(src: dict) -> list[dict]:
    """Parse all city sessions from one API source object."""
    event_id = str(src["id"])
    title = src.get("title", "未知節目")
    image_url = src.get("imageUrl", "")
    url = f"https://www.opentix.life/event/{event_id}"

    sessions = []
    seen_ids = set()

    for venue_data in src.get("eventVenues", []):
        venue_name = venue_data.get("name", "待確認")
        city = venue_data.get("city", "")

        region = guess_region(venue_name)
        if region == "其他" and city:
            region = REGION_TEXT_MAP.get(city, "其他")

        for t in venue_data.get("times", []):
            start_ms = t.get("start", 0)
            if not start_ms:
                continue

            tz_tw = datetime.timezone(datetime.timedelta(hours=8))
            dt = datetime.datetime.fromtimestamp(start_ms / 1000, tz=tz_tw)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")

            v_min = t.get("minPrice", 0)
            v_max = t.get("maxPrice", 0)
            price = normalize_price(f"{v_min}-{v_max}") if v_min else ""

            show_id = build_show_id(event_id, date_str, time_str)
            if show_id in seen_ids:
                continue
            seen_ids.add(show_id)

            sessions.append({
                "id": show_id,
                "title": title,
                "region": region,
                "venue": venue_name,
                "date": date_str,
                "time": time_str,
                "price": price,
                "url": url,
                "image_url": image_url,
            })

    return sessions


def scrape_shows() -> list[dict]:
    shows = []
    offset = 0
    total = None

    print("Fetching from search API...")
    while total is None or offset < total:
        data = _api_post(offset)
        total = data["result"]["hitsCount"]
        items = data["result"]["found"]
        print(f"  offset={offset}: {len(items)} items (total={total})")

        for item in items:
            shows.extend(parse_sessions(item["source"]))

        offset += PAGE_SIZE
        if offset < total:
            time.sleep(0.3)

    # Add supplemental shows not in the API category
    for sup in SUPPLEMENTAL_SHOWS:
        event_id = sup["event_id"]
        url = f"https://www.opentix.life/event/{event_id}"
        for session_str in sup["sessions"]:
            date_str, time_str = session_str.split(" ")
            shows.append({
                "id": build_show_id(event_id, date_str, time_str),
                "title": sup["title"],
                "region": sup["region"],
                "venue": sup["venue"],
                "date": date_str,
                "time": time_str,
                "price": sup["price"],
                "url": url,
                "image_url": sup["image_url"],
            })

    return shows


if __name__ == "__main__":
    shows = scrape_shows()

    if not shows:
        print("No shows scraped — keeping existing data")
    else:
        seen = {}
        for show in shows:
            seen[show["id"]] = show
        deduped = list(seen.values())
        OUTPUT_PATH.write_text(
            json.dumps(deduped, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Wrote {len(deduped)} sessions to {OUTPUT_PATH}")
