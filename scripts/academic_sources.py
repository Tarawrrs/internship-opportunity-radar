"""Public seminar calendars, edited working-paper feeds and journal metadata."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import datetime as dt
import hashlib
import html
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from job_sources import SOURCE_ERRORS, clean_html, date_value, fetch_json, fetch_text, parse_xml, public_url

APPLIED = "應用個經"
MICRO = "個體經濟"
MATH = "數理經濟"
GAME = "賽局理論"
EXPERIMENT = "實驗／行為經濟"
LING = "語言學"
TOPICS = {
    EXPERIMENT: r"實驗經濟|行為經濟|實驗設計|field experiment|laboratory experiment|randomi[sz]ed|behavioral economics|experiment(?:al)? economics",
    GAME: r"賽局|博弈|game theor|strategic interaction|bargaining|auction|nash equilibri|mechanism design",
    MATH: r"數理經濟|mathematical economics|general equilibrium|axiomat|fixed.point|choice theor|optimization|optimal transport",
    MICRO: r"個體經濟|微觀經濟|microeconomic|micro seminar|market design|industrial organization|mechanism design|contract theor|pricing|economies of scope",
    APPLIED: r"應用經濟|經濟史|實證|計量|applied economics|empirical|econometric|causal|treatment effect|quasi.experiment|labor|public policy|urban mobility|regression|estimation and inference|mergers|r&d",
    LING: r"語言學|語音|句法|語義|linguistic|phonolog|phonetic|morpholog|syntactic|syntax|psycholinguist|language acquisition",
}
ANCHOR = r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
RDF = {"rss": "http://purl.org/rss/1.0/", "dc": "http://purl.org/dc/elements/1.1/"}


@dataclass(frozen=True)
class AcademicSource:
    key: str
    name: str
    url: str
    reader: str
    institution: str = ""
    topics: tuple[str, ...] = ()


EVENT_SOURCES = (
    AcademicSource("ntu-econ-seminars", "台大經濟系", "https://econ.ntu.edu.tw/", "ntu_econ", "台大"),
    AcademicSource("ntu-creta", "台大 CRETA", "https://www.creta.org.tw/", "creta", "台大", (APPLIED,)),
    AcademicSource("sinica-econ-seminars", "中研院經濟所", "https://www.econ.sinica.edu.tw/pages/29", "sinica_econ", "中研院"),
    AcademicSource("sinica-ling-seminars", "中研院語言所", "https://www.ling.sinica.edu.tw/main/zh-tw", "sinica_ling", "中研院", (LING,)),
    AcademicSource("sinica-calendar", "中研院近期活動", "https://www.sinica.edu.tw/#Calendars", "sinica_calendar", "中研院"),
)
PAPER_SOURCES = (
    AcademicSource("nep-exp", "RePEc NEP · Experimental Economics", "https://nep.repec.org/nep-exp", "nep", topics=(EXPERIMENT,)),
    AcademicSource("nep-gth", "RePEc NEP · Game Theory", "https://nep.repec.org/nep-gth", "nep", topics=(GAME,)),
    AcademicSource("nep-mic", "RePEc NEP · Microeconomics", "https://nep.repec.org/nep-mic", "nep", topics=(MICRO,)),
    AcademicSource("nep-lab", "RePEc NEP · Labor Economics", "https://nep.repec.org/nep-lab", "nep", topics=(APPLIED,)),
    AcademicSource("0304-4068", "Journal of Mathematical Economics", "https://www.sciencedirect.com/journal/journal-of-mathematical-economics", "journal", topics=(MATH, MICRO)),
    AcademicSource("1945-7782", "AEJ · Applied Economics", "https://www.aeaweb.org/journals/applied-economics", "journal", topics=(APPLIED,)),
    AcademicSource("0022-2267", "Journal of Linguistics", "https://www.cambridge.org/core/journals/journal-of-linguistics", "journal", topics=(LING,)),
    AcademicSource("0097-8507", "Language", "https://www.cambridge.org/core/journals/language", "journal", topics=(LING,)),
)


def topics_for(text, defaults=()):
    return list(dict.fromkeys([*defaults, *(label for label, pattern in TOPICS.items() if re.search(pattern, text, re.I))]))


def identifier(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def date_time(text):
    return re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)


def clock_time(text, *, afternoon=False):
    if not (match := date_time(text)):
        return ""
    hour, minute = map(int, match.groups())
    if afternoon and 1 <= hour <= 7 and not re.search(r"上午|\bam\b", text, re.I):
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def event(source, link, title, day, start="", end="", venue="", speaker="", tags=(), event_type="演講／研討會", key=""):
    title = " ".join(title.split())
    if not title or re.search(r"(?:^|:\s*)(?:TBA|TBD|待定|待公布|未定)[.。]?$", title, re.I):
        return None
    if re.search(r"取消|延期|cancelled|canceled|postponed", title, re.I):
        return None
    return {
        "id": identifier(f"{source.key}|{key or title + '|' + day.isoformat()}"), "title": title,
        "date": day.isoformat(), "time": start, "endTime": end, "venue": venue, "speaker": speaker,
        "url": link, "type": event_type, "institution": source.institution, "sourceKey": source.key,
        "sourceName": source.name, "topics": topics_for(title, (*source.topics, *tags)) or ["其他學術活動"],
    }


def ntu_econ(source, today):
    home = fetch_text(source.url)
    found = re.search(r'href="(https://econ\.ntu\.edu\.tw/archives/\d+)"[^>]*>\s*研討會活動\s*</a>', home)
    if not found:
        raise ValueError("Seminar schedule link missing")
    url = found[1]
    page = fetch_text(url)
    results = {}
    examined = 0
    kinds = {"應": (APPLIED,), "產": (MICRO, APPLIED), "計": (APPLIED,), "理": (MICRO,)}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", page, re.S):
        cells = [clean_html(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) != 6 or not (day := date_value(cells[2])):
            continue
        examined += 1
        if day < today:
            continue
        speaker, title, _, _, venue, time = cells
        marker = re.match(r"^([應產計理總]|Brownbag|全/應)/\s*", speaker)
        tags = kinds.get(marker[1].split("/")[-1], ()) if marker else ()
        speaker = speaker[marker.end():] if marker else speaker.strip()
        start, _, end = re.sub(r"[–—～~]", "-", time).partition("-")
        # The timetable abbreviates afternoon hours as 1:30, 3:00, etc.
        start, end = clock_time(start, afternoon=True), clock_time(end, afternoon=True)
        if venue == "AEW Link" or re.search(r"online|webex|zoom", venue, re.I):
            venue = "線上｜活動公告"
        if item := event(source, url, title, day, start, end, venue, speaker, tags):
            clean_venue = re.sub(r"\(.*\)|\W", "", venue.lower()).replace("coss", "社科")
            key = (item["date"], item["time"], clean_venue) if clean_venue and start else (item["date"], item["title"])
            results.setdefault(key, item)
    if not examined:
        raise ValueError("No dated rows in NTU economics seminar table")
    return list(results.values()), examined, []


def creta(source, today):
    results = {}
    issues = []
    examined = 0
    for href, markup in re.findall(ANCHOR, fetch_text(source.url), re.S):
        if not re.fullmatch(r"\./news-[234]-\d+", href):
            continue
        title = clean_html(markup)
        date = re.match(r"^(20\d\d\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)\s*(.*)", title)
        if not date or not (day := date_value(date[1])):
            continue
        examined += 1
        if day < today or href in results:
            continue
        link = public_url(urljoin(source.url, href), urlsplit(source.url).hostname)
        subject = re.sub(r"^CRETA (?:Seminar|Workshop)\s*[-–:：]\s*", "", date[2], flags=re.I)
        start = end = venue = speaker = ""
        try:
            details = clean_html(fetch_text(link))
            time = re.search(r"^時間\s*[:：]\s*([^\n]+)", details, re.M)
            if time:
                first, _, last = re.sub(r"[–—～~]", "-", time[1]).partition("-")
                start, end = clock_time(first, afternoon="下午" in first), clock_time(last, afternoon="下午" in first)
            place = re.search(r"^地點\s*[:：]\s*([^\n]+)", details, re.M)
            venue = place[1][:150] if place else ""
            person = re.search(r"^(?:主講人|主講者|演講者)\s*[:：]\s*([^\n]+)", details, re.M)
            speaker = person[1][:150] if person else ""
        except SOURCE_ERRORS as error:
            issues.append(f"{day} · {type(error).__name__}")
        if item := event(source, link, subject, day, start, end, venue, speaker, key=href):
            results[href] = item
    if not examined:
        raise ValueError("No dated CRETA announcement titles")
    return list(results.values()), examined, issues


def sinica_calendar(source, today):
    home = fetch_text(source.url)
    calendar = home.partition('id="Calendars"')[2]
    links = re.findall(r'<a\s+title="([^"]+)"[^>]+href=[\x27"](/calendar_content/57/\d+)[\x27"]', calendar)
    if not links:
        raise ValueError("No Academy calendar listings")
    results, issues = [], []
    for raw_title, path in links:
        title = re.sub(r"\s*網路報名\s*$", "", clean_html(raw_title))
        if not topics_for(title) or re.search(r"網路調查|問卷|招募|徵選", title):
            continue
        url = public_url(urljoin(source.url, path), urlsplit(source.url).hostname)
        try:
            detail = fetch_text(url)
            header = re.search(r'class="calender_title">.*?<div class="h4">\s*<p>([^<]+)', detail, re.S)
            if not header or not (day := date_value(header[1])):
                raise ValueError("Academy calendar event date missing")
            if day < today:
                continue
            parts = re.findall(r"\b\d{1,2}:\d{2}\b", header[1])
            start, end = (parts + ["", ""])[:2]
            venue = re.search(r"<span>\s*地點\s*</span>\s*<p>(.*?)</p>", detail, re.S)
            speaker = re.search(r"<span>\s*演講人姓名\s*</span>\s*<p>(.*?)</p>", detail, re.S)
            if item := event(source, url, title, day, start, end,
                             clean_html(venue[1])[:150] if venue else "", clean_html(speaker[1])[:150] if speaker else "",
                             key=path):
                results.append(item)
        except SOURCE_ERRORS as error:
            issues.append(f"{path.rsplit('/', 1)[-1]} · {type(error).__name__}")
    return results, len(links), issues


def sinica_econ(source, today):
    results, issues = [], []
    examined = 0
    next_page = source.url
    for page_number in range(1, 4):
        try:
            page = fetch_text(next_page)
            sections = re.findall(r'<article class="thumb-custom[^"]*">(.*?)</article>', page, re.S)
            if not sections:
                raise ValueError("No seminar cards found")
        except SOURCE_ERRORS as error:
            if page_number == 1:
                raise
            issues.append(f"第 {page_number} 頁 · {type(error).__name__}")
            break
        for section in sections:
            link = re.search(r'<a\b[^>]*href="([^"]+/posts/\d+)"[^>]*>(.*?)</a>', section, re.S)
            day_time = re.search(r"article_time['\"]>\s*([^<]+)", section)
            if not link or not day_time or not (day := date_value(day_time[1])):
                continue
            examined += 1
            if day < today:
                continue
            url = public_url(urljoin(source.url, link[1]), urlsplit(source.url).hostname)
            speaker = re.search(r'<div class="d-inline-block text-default[^"]*"[^>]*>(.*?)</div>', section, re.S)
            title = clean_html(link[2])
            category = re.match(r"^【([^】]+)】\s*", title)
            subject = title[category.end():] if category else title
            if item := event(source, url, subject, day, clock_time(day_time[1]), speaker=clean_html(speaker[1]) if speaker else "",
                             tags=topics_for(category[1]) if category else (), key=urlsplit(url).path):
                results.append(item)
        found = re.search(r'<a rel="next"[^>]*href="([^"]+)"', page)
        if not found:
            break
        next_page = public_url(urljoin(source.url, found[1]), urlsplit(source.url).hostname, keep_query=True)
    if not examined:
        raise ValueError("No dated seminars in Sinica economics listing")

    def venue_for(item):
        try:
            details = fetch_text(item["url"])
            venue = re.search(r"<strong[^>]*>\s*地\s*點\s*[:：]\s*</strong>(.*?)</li>", details, re.S)
            return clean_html(venue[1])[:150] if venue else ""
        except SOURCE_ERRORS:
            return None

    with ThreadPoolExecutor(max_workers=4) as workers:
        for item, venue in zip(results, workers.map(venue_for, results)):
            if venue is None:
                issues.append(f"未能讀取地點 · {item['date']}")
            else:
                item["venue"] = venue
    return results, examined, issues


def sinica_ling(source, today):
    results, issues = [], []
    examined = 0
    home = fetch_text(source.url)
    details = {}
    for href, block in re.findall(ANCHOR, home, re.S):
        title = re.search(r'<div class="speach_tit">(.*?)</div>', block, re.S)
        if title:
            text = clean_html(block)
            times = re.findall(r"20\d\d-\d{2}-\d{2}\s+(\d{1,2}:\d{2})", text)
            speaker = re.search(r"主講人\s*\n([^\n]+)", text)
            details[clean_html(title[1])] = (times, speaker[1] if speaker else "")
    for kind, label in ((1, "演講"), (2, "研討會")):
        page = f"{source.url}?act=activity_list&c=list&type={kind}"
        try:
            cards = [(href, block) for href, block in re.findall(ANCHOR, fetch_text(page), re.S) if 'class="ac_time"' in block]
            if not cards:
                raise ValueError("No linguistics event cards")
        except SOURCE_ERRORS as error:
            issues.append(f"{label}列表 · {type(error).__name__}")
            continue
        for href, card in cards:
            title = re.search(r'<div class="ac_title">(.*?)</div>', card, re.S)
            when = re.search(r'<div class="ac_time">(.*?)</div>', card, re.S)
            if not title or not when or not (day := date_value(when[1])):
                continue
            examined += 1
            if day < today:
                continue
            title = clean_html(title[1])
            times, speaker = details.get(title, ([], ""))
            is_detail = bool(re.search(r"\?/sign/(?!www\.)[\w-]+/?$", href))
            link = public_url(urljoin(source.url, href), urlsplit(source.url).hostname, keep_query=True) if is_detail else page
            venue = ""
            if is_detail and (day - today).days <= 30:
                try:
                    found = re.search(r"<h3>\s*(?:會議地點|Venue)\s*</h3>\s*</div>\s*<p[^>]*>(.*?)</p>", fetch_text(link), re.S | re.I)
                    venue = clean_html(found[1])[:150] if found else ""
                except SOURCE_ERRORS:
                    issues.append(f"未能讀取地點 · {day}")
            start, end = (times + ["", ""])[:2]
            if item := event(source, link, title, day, start, end, venue, speaker, event_type=label):
                results.append(item)
    if not examined:
        raise ValueError("No dated Sinica linguistics events")
    return results, examined, issues


def paper(source, key, title, link, published, date_label, authors, type_label, extra_topics=""):
    return {
        "id": identifier(key.casefold()), "title": " ".join(title.split()), "date": published.isoformat(),
        "dateLabel": date_label, "url": link, "type": type_label, "authors": authors,
        "sourceName": source.name, "sourceKeys": [source.key],
        "topics": topics_for(f"{title} {extra_topics}", source.topics),
    }


def nep(source, today):
    root = parse_xml(fetch_text(f"https://nep.repec.org/rss/{source.key}.rss.xml"))
    issued = date_value(root.findtext("rss:channel/dc:date", namespaces=RDF))
    if not issued:
        raise ValueError("NEP issue date missing")
    entries = root.findall("rss:item", RDF)
    if not entries:
        raise ValueError("No papers in NEP report")
    results = []
    for row in entries[:14]:
        raw_link = row.findtext("rss:link", namespaces=RDF)
        key = parse_qs(urlsplit(raw_link or "").query).get("u", [""])[0]
        title = clean_html(row.findtext("rss:title", namespaces=RDF))
        if not title or not re.fullmatch(r"RePEc:[\w:./-]+", key, re.I):
            continue
        authors = [clean_html(a.text) for a in row.findall("dc:creator", RDF) if a.text]
        keywords = row.findtext("dc:subject", "", RDF) or ""
        results.append(paper(source, key, title, f"https://econpapers.repec.org/{key}", issued,
                             "選刊日期", authors[:6], "工作論文", keywords))
    return results, len(entries), []


def journal(source, today):
    query = urlencode({
        "filter": f"from-pub-date:{today - dt.timedelta(days=90)},until-pub-date:{today},type:journal-article",
        "sort": "published", "order": "desc", "rows": 12, "select": "DOI,title,published,published-online,author",
    })
    entries = fetch_json(f"https://api.crossref.org/journals/{source.key}/works?{query}")["message"]["items"]
    results = []
    for row in entries:
        title = clean_html((row.get("title") or [""])[0])
        if not title or re.search(r"^(?:editorial board|front matter|back matter|contents|corrigendum|erratum)\b", title, re.I):
            continue
        parts = (row.get("published-online") or row.get("published", {})).get("date-parts", [[]])[0]
        if len(parts) < 2:
            continue
        published = dt.date(*parts) if len(parts) == 3 else dt.date(*parts, 1)
        if published > today or published < today - dt.timedelta(days=90):
            continue
        authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in row.get("author", [])]
        doi = row["DOI"]
        item = paper(source, doi, title, public_url(f"https://doi.org/{doi}"), published,
                     "出版日期" if len(parts) == 3 else "出版月份", [name for name in authors if name][:6],
                     "期刊紀錄")
        results.append(item)
    return results, len(entries), []


READERS = {"ntu_econ": ntu_econ, "creta": creta, "sinica_econ": sinica_econ, "sinica_ling": sinica_ling,
           "sinica_calendar": sinica_calendar, "nep": nep, "journal": journal}
