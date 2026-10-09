"""天气查询 handler：wttr.in 免费服务（免 Key，支持中文城市名）。

约定导出 run(task, context) -> str。task 可能是城市名或整句提问，内部提取城市。
"""
import json
import re
import time
import urllib.parse
import urllib.request

TIMEOUT = 15
UA = {"User-Agent": "curl/8"}
# "今天广州天气怎么样" / "查一下上海的气温" / "北京天气" / "杭州"
_CITY_RE = re.compile(r"(?:查询|查一下|看看|查|在)?([一-龥]{2,6}?)(?:的)?(?:今天|明天|后天|现在|目前)?(?:的)?(?:天气|气温|温度|下雨)")
_FILLERS = ("今天", "明天", "后天", "现在", "目前", "请问", "帮我")


def _extract_city(task: str) -> str:
    m = _CITY_RE.search(task)
    if m:
        city = m.group(1)
        for w in _FILLERS:
            city = city.replace(w, "")
        if city:
            return city
    # 兜底：整个 task 就是个短地名
    if len(task.strip()) <= 6 and re.fullmatch(r"[一-龥A-Za-z ]+", task.strip()):
        return task.strip()
    return ""


def _fetch_json(city: str):
    url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
    req = urllib.request.Request(url, headers=UA)
    last_exc = None
    for attempt in range(2):  # wttr 免费服务偶发抽风，重试一次
        try:
            return json.load(urllib.request.urlopen(req, timeout=TIMEOUT))
        except Exception as e:  # noqa: BLE001
            last_exc = e
            time.sleep(1)
    raise last_exc


def run(task: str, context: dict) -> str:
    city = _extract_city(task)
    if not city:
        return "错误：未识别到城市名，请只传城市名（如：北京）"
    try:
        d = _fetch_json(city)
    except Exception as e:  # noqa: BLE001
        return f"天气查询失败（{city}）: {type(e).__name__}: {e}"

    cc = d["current_condition"][0]
    lines = [
        f"城市: {city}",
        f"当前实况: {cc['temp_C']}°C（体感 {cc['FeelsLikeC']}°C），"
        f"湿度 {cc['humidity']}%，{cc['weatherDesc'][0]['value'].strip()}，"
        f"风速 {cc['windspeedKmph']}km/h",
    ]
    for day in d.get("weather", [])[:3]:
        lines.append(
            f"{day['date']} 预报: {day['mintempC']}~{day['maxtempC']}°C，"
            f"降水概率 {day['hourly'][4].get('chanceofrain', '?')}%"
        )
    return "\n".join(lines)
