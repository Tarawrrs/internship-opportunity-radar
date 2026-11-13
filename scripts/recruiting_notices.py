"""Campus recruiting boards, an employer RSS feed and a reviewed recruiting flyer."""

from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import html
import json
import re
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlsplit

from job_sources import (
    Batch, Posting, SOURCE_ERRORS, clean_html, date_value, deadline_in, fetch_payload, fetch_text,
    notice_location, parse_xml, public_url,
)

INTERNSHIP_NOTICE = re.compile(r"實習|寒假.{0,12}工讀|\bintern(?:ship)?\b", re.I)
ROLLING = re.compile(r"隨到隨審|額滿為止|until (?:the position is )?filled|rolling basis", re.I)
DATE = r"20\d\d-\d{2}-\d{2}"
ANCHOR = r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>'


def board_rows(board, body):
    if board == "ntu-career":
        pattern = rf'<a\b[^>]*href="([^"]*/board/detail/sn/\d+)"[^>]*>(.*?)</a>\s*</h5>.*?<span class="date">[^<]*<i[^>]*></i>\s*({DATE})'
        return re.findall(pattern, body, re.S)
    if board == "ncu-career":
        rows = []
        for link, card in re.findall(ANCHOR, body, re.S):
            if not re.search(r"/internship/show/\d+$", link):
                continue
            day = re.search(DATE, card)
            title = re.search(r'<h5 class="card-title[^"]*"[^>]*>(.*?)</h5>', card, re.S)
            if day and title:
                rows.append((link, title[1], day[0]))
        return rows
    if board == "nccu-career":
        pattern = r'<a class="tt" href="([^"]*/job/view/\d+)">([^<]*(?:<(?!/a>)[^<]*)*)</a>\s*<span class="loc">([^<]+)</span>'
        return re.findall(pattern, body, re.S)
    pattern = rf'<tr>\s*<td>\s*<div>\s*<a href="(/news/\d+/)">([^<]+)</a>(?:(?!</tr>).)*?({DATE})'
    return re.findall(pattern, body, re.S)


def campus_article(board, raw):
    patterns = {
        "ntu-career": r'<article class="article">(.*?)</article>',
        "ncu-career": r'<div id="js-article-body"[^>]*>(.*?)<div id="article-sidebar"',
        "nycu-career": r'<h2 class="ui header">.*?</h2>(.*?)<footer',
        "nccu-career": r'<h1[^>]*>.*?</h1>(.*?)<footer',
    }
    match = re.search(patterns[board], raw, re.S)
    if not match:
        raise ValueError("Unexpected campus announcement format")
    return match[1]


def application_link(raw, base):
    for href, label in re.findall(ANCHOR, raw, re.S):
        target = urljoin(base, html.unescape(href))
        if re.search(r"104\.com\.tw/(?:job|company)/|careers\.apac\.deloitte\.com/job/", target):
            return public_url(target)
        if target.startswith("https://") and re.search(r"立即申請|立即應徵|線上申請|^Apply(?: now)?$", clean_html(label), re.I):
            return public_url(target, keep_query=True)
    text = clean_html(raw)
    if found := re.search(r'https://(?:www\.104\.com\.tw/(?:job|company)/[a-z0-9]+|careers\.apac\.deloitte\.com/job/[^\s<>"\u3000]+)', text, re.I):
        return public_url(found[0])
    return ""


def notice_title(title):
    return re.sub(r"^(?:轉知\s*[:：]?\s*|【實習(?:機會)?】\s*|\[實習\]\s*)+", "", title).strip()


def read_campus_post(source, link, title, published, listed_location=""):
    article = campus_article(source.board, fetch_text(link))
    body = clean_html(re.sub(r"<!--.*?-->", "", article, flags=re.S))
    location = notice_location(body) or listed_location
    company_match = re.match(r"^[【\[]([^】\]]{2,24})[】\]]", title)
    company = company_match[1] if company_match else "企業／用人單位見公告"
    if source.board == "nccu-career":
        employer = re.search(r"任職機構名稱\s*[:：]\s*([^\n]+)", body)
        published_at = re.search(r"刊登日期\s*[:：]\s*([^\n]+)", body)
        published = date_value(published_at[1]) if published_at else None
        company = employer[1] if employer else company
        if re.search(r"政大限定|限政大|僅限政治大學", title + "\n" + body):
            return []
    deadline = deadline_in(body, published)
    deadline_time = ""
    for line in body.splitlines():
        if deadline and deadline_in(line, published) == deadline:
            time = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", line)
            if time:
                deadline_time = f"{int(time[1]):02d}:{time[2]}"
                break
    rolling = bool(ROLLING.search(body))
    if re.search(r"台灣福斯|Volkswagen Group Taiwan", title, re.I):
        company = "台灣福斯集團"
    if "勤業眾信" in title:
        company = "勤業眾信 Deloitte"
    identifier = urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1]
    if source.board == "nycu-career" and identifier == "4285":
        # Taipei Da'an is listed on both employer postings. The campus circular
        # provides the dates and eligibility and links to the specific requisitions.
        roles = {"96qkj": ("AI數位金融", "數位金融產品、AI 防詐、資料分析與法遵內控，依部門安排。"),
                 "96qk5": ("法人金融", "融資、資金管理、貿易融資與避險，依部門安排。")}
        sections = re.split(r"(?=\d\.\s*【實習轉MA】)", body)
        return [Posting(f"feib-{job_id}", f"{role}實習生", "遠東商銀", link, "台北市大安區",
                        section, posted=published, deadline=deadline_in(section, published),
                        period="2027/01/04–06/21 · 寒假每週 40 小時，學期每週 16 小時",
                        eligibility="大學或碩士在學，大四與碩二優先。時薪 NT$250。",
                        note=note, application_url=f"https://www.104.com.tw/job/{job_id}")
                for job_id, (role, note) in roles.items() for section in sections
                if f"104.com.tw/job/{job_id}" in section and "2027/1/4 ~ 2027/6/21" in section]
    if source.board == "ntu-career" and identifier == "4786" and "2027/1/11" in body and "2027/7/9" in body:
        # These two employer requisitions list Nangang. Other teams on the circular may be in Xizhi.
        roles = (
            ("63355", "Group FIN / Finance Intern", "財務實習生", "財務作業、報表及部門專案支援。"),
            ("6t41k", "VWPC / Sales & Product Intern", "銷售與產品企劃實習生", "競品追蹤、銷售 KPI 與管理報表。"),
        )
        return [Posting(f"vw-{key}", name, company, link, "台北市南港區",
                        "實習期間：2027/1/11–2027/7/9\n" + note, posted=published, rolling_open=rolling,
                        period="2027/01/11–07/09 · 每週至少 3 天到班",
                        eligibility="須具在學身分並能以中文與英文溝通，詳各組原公告。",
                        note=note, application_url=f"https://www.104.com.tw/job/{key}")
                for key, anchor, name, note in roles if anchor in body]
    if source.board == "ncu-career" and identifier == "962" and "2027/1/11" in body and "2027/7/9" in body:
        # The NTU circular supplies the two individually located positions above.
        return []
    if not location:
        return []
    mixed = bool(re.search(r"台北|臺北|\bTaipei\b", location, re.I) and re.search(
        r"新北|桃園|新竹|台中|臺中|台南|臺南|高雄|new taipei", location, re.I))
    return [Posting(f"{source.board}-{identifier}", title, company, link, location, body,
                    commitment="intern" if source.board == "nccu-career" else "",
                    posted=published, deadline=deadline, rolling_open=rolling, deadline_time=deadline_time,
                    application_url=application_link(article, link), location_needs_check=mixed)]


def read_campus(source, today):
    pages = [source.endpoint]
    if source.board == "nycu-career":
        pages += [f"{source.endpoint}?page={page}" for page in range(2, 6)]
    result = Batch()
    entries = {}
    with ThreadPoolExecutor(max_workers=4) as workers:
        for url, request in zip(pages, [workers.submit(fetch_text, url) for url in pages]):
            try:
                page = request.result()
                rows = board_rows(source.board, page)
                if not rows:
                    raise ValueError("Unexpected campus board format")
                if source.board == "ntu-career" and url == source.endpoint:
                    for page_url in list(dict.fromkeys(re.findall(
                        r'href="(https://career\.ntu\.edu\.tw/board/index/tab/2/page/[2-5])"', page
                    )))[:4]:
                        rows.extend(board_rows(source.board, fetch_text(page_url)))
                for link, raw_title, marker in rows:
                    link = public_url(urljoin(source.url, link), urlsplit(source.url).hostname)
                    listed_location = clean_html(marker) if source.board == "nccu-career" else ""
                    title = notice_title(clean_html(raw_title))
                    if source.board == "nccu-career" and re.search(r"政大限定|限政大|僅限政治大學", html.unescape(raw_title)):
                        continue
                    entries[link] = (title, date_value(marker), listed_location)
            except SOURCE_ERRORS as error:
                result.issues.append(f"公告列表第 {pages.index(url) + 1} 頁：{type(error).__name__}")
        result.examined = len(entries)
        recent = [(link, title, published, location) for link, (title, published, location) in entries.items()
                  if (published and 0 <= (today - published).days <= 55 and INTERNSHIP_NOTICE.search(title))
                  or (source.board == "nccu-career" and re.search(r"台北|臺北|\bTaipei\b|遠端", location, re.I))]
        recent.sort(key=lambda row: row[2] or today, reverse=True)
        if len(recent) > 30:
            result.issues.append(f"逐篇讀取最新 30／{len(recent)} 則實習公告")
        requests = [(link, workers.submit(read_campus_post, source, link, title, day, location))
                    for link, title, day, location in recent[:30]]
        for link, request in requests:
            try:
                result.postings.extend(request.result())
            except SOURCE_ERRORS as error:
                result.issues.append(f"公告 {urlsplit(link).path}：{type(error).__name__}")
    if result.issues and not result.examined:
        raise ValueError("No campus announcements could be read")
    return result


def read_bank(source, today):
    root = parse_xml(fetch_text(source.endpoint))
    if root.find("channel") is None:
        raise ValueError("Expected the employer RSS channel")
    items = root.findall("./channel/item")
    result = Batch(examined=len(items))
    for row in items:
        title = row.findtext("title", "")
        match = re.fullmatch(r"(.+?)\s+\((Taipei, TW)\)", title, re.I)
        if not match or not INTERNSHIP_NOTICE.search(match[1]):
            continue
        link = public_url(row.findtext("link"), urlsplit(source.url).hostname)
        identifier = urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1]
        body = clean_html(row.findtext("description", ""))
        result.postings.append(Posting(f"sc-{identifier}", match[1], "渣打銀行", link, match[2], body,
                                       posted=date_value(row.findtext("pubDate"))))
    return result


def read_workday(source, today):
    result = Batch()
    rows = []
    for offset in range(0, 240, 20):
        data = json.dumps({"searchText": "Taipei", "appliedFacets": {}, "limit": 20, "offset": offset}).encode()
        request = Request(source.endpoint + "/jobs", data, headers={"Content-Type": "application/json", "Accept": "application/json"})
        with urlopen(request, timeout=16) as response:
            page = json.load(response)
        rows.extend(page["jobPostings"])
        if len(rows) >= page["total"] or not page["jobPostings"]:
            break
    result.examined = len(rows)
    if len(rows) < page["total"]:
        result.issues.append("已達台北搜尋單次上限")
    for row in rows:
        title = row["title"]
        if not re.search(r"實習|工讀|\bintern(?:ship)?\b", title, re.I):
            continue
        path = row["externalPath"]
        if not re.fullmatch(r"/job/[a-zA-Z0-9_./%~-]+", path) or ".." in path:
            continue
        try:
            detail = json.loads(fetch_text(source.endpoint + path))["jobPostingInfo"]
            if detail.get("canApply") is not True:
                continue
            # Workday's startDate denotes publication of the posting.
            location = detail.get("location") or row.get("locationsText") or ""
            url = public_url(detail["externalUrl"], urlsplit(source.url).hostname)
            content = clean_html(detail.get("jobDescription", ""))
            result.postings.append(Posting(f"workday-{source.board}-{detail['jobReqId']}", title, source.name,
                                           url, location, content, "intern",
                                           posted=date_value(detail.get("startDate")), deadline=date_value(detail.get("endDate"))))
        except SOURCE_ERRORS as error:
            result.issues.append(f"{path.rsplit('/', 1)[-1]} · {type(error).__name__}")
    return result


CAPITAL_DEADLINE = dt.date(2026, 11, 30)
CAPITAL_DIGEST = "ecb7144af55531cce92e461e11a4bb52d7ec5f205973558d0cf3733a53f52635"


def read_capital_flyer(source, today):
    if today > CAPITAL_DEADLINE:
        return Batch()
    payload, _ = fetch_payload(source.endpoint)
    if hashlib.sha256(payload).hexdigest() != CAPITAL_DIGEST:
        raise ValueError("Recruiting flyer changed since manual review")
    common = dict(company="群益金鼎證券", url=source.url, deadline=CAPITAL_DEADLINE, posted=dt.date(2026, 11, 3))
    return Batch([
        Posting("capital-2027-winter-settlement", "結算部北區寒假工讀", location="台北可選｜大安、敦南、中山、古亭、忠孝",
                description="文件掃描、協助開戶與臨櫃服務。", winter_status="winter-only",
                period="寒假約 2 個月 · 起迄日請洽用人單位", note="投遞時選台北市據點；簡章同時列有其他縣市。",
                eligibility="簡章的結算部欄未列特定科系或年級，請核對分行與排班。", **common),
        Posting("capital-2027-winter-trading", "證券自營／期貨自營實習", location="台北市大安區",
                description="自營交易、金融市場觀察、統計分析、量化研究與資料分析。",
                winter_status="flexible", period="約 3 個月 · 每週 2–4 天 · 起聘日請洽各組",
                note="同一簡章有證券與期貨自營兩組，可分別核對工作內容與條件。", **common),
    ], examined=1)


def read_richemont_leads(source, today):
    # The employer's listings were individually checked on this date. The sites
    # return a JavaScript shell or block the runner, so only retain recent leads.
    checked = dt.date(2026, 11, 13)
    if not 0 <= (today - checked).days < 7:
        return Batch()
    roles = (
        ("968pa", "Vacheron Constantin CRM Intern", "CRM 報表、資料品質檢查與客群分析。", "學期每週 2–3 天",
         "https://tanji.104.com.tw/job/7234be6c-b5d7-4719-baf6-13e0034a3aa5"),
        ("96obx", "Cartier Marketing Insight & Client Data Intern", "行銷 ROI、顧客資料及市場洞察報表。", "學期每週至少 3 天",
         "https://www.104.com.tw/job/96obx"),
        ("968mw", "Roger Dubuis Brand Intern", "品牌零售營運、合作通路和活動成效報表。", "學期每週至少 3 天",
         "https://tanji.104.com.tw/job/dad13170-e358-46cb-8bf1-a88f2db40321"),
    )
    return Batch([
        Posting(f"richemont-{key}", title, "歷峯集團 Richemont", url, "台北市松山區",
                "Internship Period: 2027/01/04–2027/03/30\n" + note, updated=checked,
                period=f"2027/01/04–03/30 · 寒假每週 5 天，{hours}",
                note=note, eligibility="時薪 NT$220。資格、名額與投遞狀態見職缺原文。",
                application_url=f"https://www.104.com.tw/job/{key}",
                verification_note="11/13 人工核對職缺內容，請點原公告確認仍收件。")
        for key, title, note, hours, url in roles
    ])


NOTICE_READERS = {"campus": read_campus, "bank": read_bank, "reviewed": read_capital_flyer,
                  "manual-leads": read_richemont_leads, "workday": read_workday}
