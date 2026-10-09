"""互联网搜索 handler：Bing 国内站 HTML 搜索（免 Key）。

约定导出 run(task, context) -> str。主 Agent 会把 task（搜索关键词）传进来。
"""
import html as html_mod
import re
import urllib.request
import urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MAX_RESULTS = 6
TIMEOUT = 15


def run(task: str, context: dict) -> str:
    """task = 搜索关键词；context 由系统注入（含 now）。"""
    query = task.strip()
    if not query:
        return "错误：搜索关键词为空"
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers=UA)
    try:
        page = urllib.request.urlopen(req, timeout=TIMEOUT).read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"搜索失败: {type(e).__name__}: {e}"

    items = re.findall(r'<li class="b_algo".*?</li>', page, re.S)
    if not items:
        return f"搜索“{query}”无结果（可能被风控），建议换个关键词"

    out = []
    for it in items[:MAX_RESULTS]:
        m = re.search(r'<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>', it, re.S)
        if not m:
            continue
        link = html_mod.unescape(m.group(1))
        title = _clean(m.group(2))
        snip = ""
        p = re.search(r"<p[^>]*>(.*?)</p>", it, re.S)
        if p:
            snip = _clean(p.group(1))
        out.append(f"[{len(out) + 1}] {title}\n链接: {link}\n摘要: {snip}")
    return "\n\n".join(out) if out else f"搜索“{query}”无可用结果"


def _clean(raw: str) -> str:
    """去标签 + 还原实体 + 压缩空白。"""
    text = re.sub(r"<[^>]+>", "", raw)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
