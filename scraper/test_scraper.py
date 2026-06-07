import pytest
from scraper import guess_region, normalize_price, build_show_id

def test_guess_region_taipei():
    assert guess_region("水源劇場") == "台北"
    assert guess_region("國家戲劇院") == "台北"
    assert guess_region("中山堂") == "台北"
    assert guess_region("松菸文創園區") == "台北"

def test_guess_region_taichung():
    assert guess_region("台中國家歌劇院") == "台中"
    assert guess_region("臺中中正堂") == "台中"

def test_guess_region_kaohsiung():
    assert guess_region("衛武營國家藝術文化中心") == "高雄"
    assert guess_region("大東文化藝術中心") == "高雄"

def test_guess_region_other():
    assert guess_region("新竹市文化局演藝廳") == "其他"
    assert guess_region("") == "其他"

def test_normalize_price_range():
    assert normalize_price("500元 - 1200元") == "500-1200"
    assert normalize_price("NT$800~2000") == "800-2000"

def test_normalize_price_free():
    assert normalize_price("免費") == ""
    assert normalize_price("") == ""

def test_build_show_id():
    result = build_show_id("abc123", "2026-06-07", "14:30")
    assert result == "abc123-2026-06-07-1430"
