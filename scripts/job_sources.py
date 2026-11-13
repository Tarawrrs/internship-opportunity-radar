"""Read current public recruiting listings. Adapters never publish full job descriptions."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
from email.utils import parsedate_to_datetime
import html
import json
import re
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
SOURCE_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError)


@dataclass(frozen=True)
class Source:
    kind: str
    board: str
    name: str
    url: str
    endpoint: str
    rolling: bool = False

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.board}"


@dataclass
class Posting:
    id: str
    title: str
    company: str
    url: str
    location: str
    description: str = ""
    commitment: str = ""
    workplace: str = ""
    posted: dt.date | None = None
    updated: dt.date | None = None
    deadline: dt.date | None = None
    rolling_open: bool = False
    third_party: bool = False
    winter_status: str = ""
    period: str = ""
    eligibility: str = ""
    note: str = ""
    application_url: str = ""
    deadline_time: str = ""
    location_needs_check: bool = False
    verification_note: str = ""


@dataclass
class Batch:
    postings: list[Posting] = field(default_factory=list)
    examined: int = 0
    issues: list[str] = field(default_factory=list)


def greenhouse(board: str, name: str) -> Source:
    return Source("greenhouse", board, name, f"https://job-boards.greenhouse.io/{board}",
                  f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")


def lever(board: str, name: str) -> Source:
    return Source("lever", board, name, f"https://jobs.lever.co/{board}",
                  f"https://api.lever.co/v0/postings/{board}?mode=json")


def workday(tenant: str, board: str, host: str, name: str) -> Source:
    base = f"https://{tenant}.{host}.myworkdayjobs.com"
    return Source("workday", tenant, name, f"{base}/{board}", f"{base}/wday/cxs/{tenant}/{board}")


SINICA_LIST = "https://www.sinica.edu.tw/recruitment/53?Datas_Query.workType=3"
NTU_CAREERS = "https://econ.ntu.edu.tw/archives/category/" + quote("實習與就業")
NTU_BOARD = "https://career.ntu.edu.tw/board/index/tab/2"
NCU_BOARD = "https://careercenter.ncu.edu.tw/internship"
NYCU_BOARD = "https://openhouse.osa.nycu.edu.tw/recruit_news/"
NCCU_BOARD = "https://cd.nccu.edu.tw/domestic_internship/job"
SC_BOARD = "https://jobs.standardchartered.com/"
SOURCES = (
    Source("taiwanjobs", "taipei", "台灣就業通（台北 12 區）", "https://data.gov.tw/dataset/44062",
           "https://free.taiwanjobs.gov.tw/webservice_taipei/Webservice.ashx"),
    Source("line", "taiwan", "LINE Careers", "https://careers.linecorp.com/jobs?ca=All&cp=LINE+Taiwan",
           "https://careers.linecorp.com/page-data/jobs/page-data.json"),
    greenhouse("dcard", "Dcard"),
    Source("sinica", "research", "中央研究院人才招募", SINICA_LIST, SINICA_LIST),
    Source("rss", "ntu-econ", "台大經濟系實習與就業公告", NTU_CAREERS, NTU_CAREERS + "/feed", True),
    Source("rss", "nstc", "國科會求才公告", "https://www.nstc.gov.tw/folksonomy/list/ba3d22f3-96fd-4adf-a078-91a05b8f0166?l=ch",
           "https://www.nstc.gov.tw/nstc/rss/hr", True),
    Source("campus", "ntu-career", "台大職涯中心｜實習公告", NTU_BOARD, NTU_BOARD, True),
    Source("campus", "ncu-career", "中央大學職涯中心｜實習公告", NCU_BOARD, NCU_BOARD, True),
    Source("campus", "nycu-career", "陽明交大職涯中心｜求才公告", NYCU_BOARD, NYCU_BOARD, True),
    Source("campus", "nccu-career", "政大職涯平台｜國內實習職缺", NCCU_BOARD, NCCU_BOARD, True),
    Source("bank", "standard-chartered", "渣打銀行｜官方職缺", SC_BOARD,
           SC_BOARD + "services/rss/job/?locale=en_GB&keywords=Taiwan", True),
    workday("dbs", "DBS_Careers", "wd3", "星展銀行"),
    workday("pwc", "Global_Campus_Careers", "wd3", "資誠 PwC"),
    workday("mastercard", "CorporateCareers", "wd1", "Mastercard"),
    Source("reviewed", "capital-winter-2027", "群益金鼎證券｜已核對簡章",
           "https://career.ntu.edu.tw/board/detail/sn/4775", "https://career.ntu.edu.tw/board/download/sn/1784"),
    Source("manual-leads", "richemont-winter-2027", "歷峯集團｜人工查核線索",
           "https://www.104.com.tw/company/12wz0014", ""),
    Source("himalayas", "tw", "Himalayas 遠端職缺", "https://himalayas.app/",
           "https://himalayas.app/jobs/api/search", True),
    greenhouse("appier", "Appier"), greenhouse("point72", "Point72"),
    greenhouse("worldquant", "WorldQuant"), greenhouse("agoda", "Agoda"),
    greenhouse("anthropic", "Anthropic"), greenhouse("mercari", "Mercari"),
    lever("shopback-2", "ShopBack"), lever("ninjavan", "Ninja Van"), lever("portcast", "Portcast"),
)


def fetch_payload(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": "InternshipRadar/2.0 (+https://github.com/Tarawrrs/internship-opportunity-radar)"})
    for attempt in range(2):
        try:
            with urlopen(request, timeout=20) as response:
                limit = 24_000_000
                payload = response.read(limit + 1)
                if len(payload) > limit:
                    raise ValueError("Source response exceeds the size limit")
                return payload, response.headers.get_content_charset() or "utf-8-sig"
        except HTTPError as error:
            if attempt or error.code not in {408, 500, 502, 503, 504}:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt:
                raise
        sleep(1)


def fetch_text(url: str) -> str:
    payload, encoding = fetch_payload(url)
    return payload.decode(encoding)


def fetch_json(url: str):
    return json.loads(fetch_text(url))


def clean_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", value, flags=re.I | re.S)
    value = re.sub(r"<\s*(?:br\b[^>]*|/?(?:p|div|li|h[1-6]|tr|td|th)\b[^>]*)>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return "\n".join(line for part in value.splitlines() if (line := " ".join(part.split())))


def public_url(value: str, host: str | None = None, keep_query: bool = False) -> str:
    parts = urlsplit(value or "")
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Expected a public HTTPS posting URL")
    if host and parts.hostname != host:
        raise ValueError("Unexpected posting host")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query if keep_query else "", ""))


def date_value(value) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, (float, int)):
        try:
            return dt.datetime.fromtimestamp(value / 1000 if value > 10**11 else value, TAIPEI).date()
        except (OverflowError, OSError, ValueError):
            return None
    value = str(value).strip()
    compact = re.fullmatch(r"(20\d\d)(\d\d)(\d\d)", value)
    numeric = compact or re.search(r"(?<!\d)(20\d\d|1\d\d)\s*(?:[-/.]|年)\s*(\d{1,2})\s*(?:[-/.]|月)\s*(\d{1,2})(?!\d)", value)
    if numeric:
        year, month, day = map(int, numeric.groups())
        try:
            return dt.date(year + 1911 if year < 200 else year, month, day)
        except ValueError:
            return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(TAIPEI).date() if parsed.tzinfo else parsed.date()
    except (TypeError, ValueError):
        return None


def deadline_in(text: str, published: dt.date | None) -> dt.date | None:
    """Read dates near application/deadline language, not dates like the start of work."""
    date = r"(?:20\d\d|1\d\d)\s*[-/.年]\s*\d{1,2}\s*[-/.月]\s*\d{1,2}(?:日)?"
    for pattern in (
        rf"(?:投遞|報名|申請|收件)(?:日期|期間|時間)\s*[:：｜|]?\s*(?:即日|即刻|現在)起\s*(?:至|到|[–~～])?\s*({date})",
        rf"(?:截止|收件(?:至|到)|報名(?:至|到)|deadline)\s*(?:日期|時間|日)?\s*[:：｜|為至\s]*({date})",
        rf"({date})\s*(?:\d{{1,2}}[:：]\d{{2}}\s*)?(?:\([^)]{{1,6}}\)|（[^）]{{1,6}}）)?\s*(?:前\s*(?:寄|送|繳|將|完成|投遞|來信|報名)|截止)",
    ):
        if found := re.search(pattern, text, re.I):
            return date_value(found[1])
    english = re.search(r"\b(?:deadline|apply by)\s*[:：]?\s*(\d{1,2}\s+[A-Za-z]{3,9}|[A-Za-z]{3,9}\s+\d{1,2})(?:,?\s+(20\d\d))?\b", text, re.I)
    if english and (english[2] or published):
        for fmt in ("%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y"):
            try:
                return dt.datetime.strptime(f"{english[1]} {english[2] or published.year}", fmt).date()
            except ValueError:
                continue
    return None


def campus_location(value: str) -> str:
    # Map named campuses only from the notice's work-location field, never its footer or organizer.
    if re.search(r"新北|南部院區|台南|臺南|桃園|綠島|屏東|嘉義|新竹|台中|臺中|高雄|基隆|宜蘭", value):
        return value
    if re.search(r"(?:臺大|台大|臺灣大學|台灣大學)社會科學院|College of Social Sciences,\s*NTU|"
                 r"(?:中央研究院|中研院)(?:人文社會科學研究中心|經濟研究所|社會學研究所|政治學研究所|統計科學研究所|歐美研究所|環境變遷研究中心)", value, re.I):
        return f"台北｜{value}"
    return value


def notice_location(text: str) -> str:
    labels = re.findall(r"(?:工作地點|工作地址|工作地區|工作場所|上班地點|實習地點|實習地址|工作模式|work location|work mode)[ \t]*[】\]〗）)]?[ \t]*[:：｜| \t\n]+([^\n]{2,220})", text, re.I)
    if labels:
        return campus_location(" / ".join(dict.fromkeys(labels))[:220])
    return ""


def parse_xml(raw: str) -> ET.Element:
    if re.search(r"<!DOCTYPE|<!ENTITY", raw, re.I):
        raise ValueError("Unexpected DTD in feed")
    return ET.fromstring(raw)


def read_greenhouse(source: Source, today: dt.date) -> Batch:
    rows = fetch_json(source.endpoint)["jobs"]
    if not isinstance(rows, list):
        raise ValueError("Invalid Greenhouse job list")
    jobs = []
    for row in rows:
        location = (row.get("location") or {}).get("name", "")
        offices = [office.get("location") for office in row.get("offices", []) if office.get("location")]
        # A name such as “Dcard” is not a city. Use the posted office city when the label is generic.
        if offices and (not location or location.casefold() == source.name.casefold()):
            location = " / ".join(dict.fromkeys(offices))
        jobs.append(Posting(f"gh-{source.board}-{row['id']}", row["title"], source.name,
                            public_url(row["absolute_url"]), location, clean_html(row.get("content", "")),
                            posted=date_value(row.get("first_published")), updated=date_value(row.get("updated_at")),
                            deadline=date_value(row.get("application_deadline"))))
    return Batch(jobs, len(rows))


def read_lever(source: Source, today: dt.date) -> Batch:
    rows = fetch_json(source.endpoint)
    if not isinstance(rows, list):
        raise ValueError("Invalid Lever job list")
    jobs = []
    for row in rows:
        categories = row.get("categories") or {}
        locations = categories.get("allLocations") or [categories.get("location", "")]
        text = "\n".join([row.get("descriptionPlain", ""), row.get("additionalPlain", "")] +
                         [clean_html(item.get("content", "")) for item in row.get("lists", [])])
        jobs.append(Posting(f"lever-{source.board}-{row['id']}", row["text"], source.name,
                            public_url(row["hostedUrl"]), " / ".join(locations), text,
                            categories.get("commitment", ""), row.get("workplaceType", ""),
                            posted=date_value(row.get("createdAt"))))
    return Batch(jobs, len(rows))


def parse_taiwanjobs(raw: str) -> list[dict]:
    # This XML service uses full-width parentheses in its documented field names.
    # Normalize tag names only; never alter the employer's CDATA text.
    parts = re.split(r"(<!\[CDATA\[.*?\]\]>)", raw, flags=re.S)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(r"(<\/?[A-Z][A-Z0-9_]+)（[^<>]+?）>", r"\1>", parts[index])
    root = parse_xml("".join(parts))
    if root.tag != "DataList":
        raise ValueError("Unexpected TaiwanJobs response")
    rows = [{field.tag: (field.text or "").strip() for field in row} for row in root.findall("./Data")]
    if any(not {"OCCU_DESC", "CITYNAME", "URL_QUERY", "COMPNAME"}.issubset(row) for row in rows):
        raise ValueError("Unexpected TaiwanJobs fields")
    return rows


def read_taiwanjobs(source: Source, today: dt.date) -> Batch:
    result = Batch()
    for postal in (100, 103, 104, 105, 106, 108, 110, 111, 112, 114, 115, 116):
        try:
            rows = parse_taiwanjobs(fetch_text(source.endpoint + "?" + urlencode({"zipno": postal, "count": 1000})))
            if len(rows) >= 1000:
                result.issues.append(f"{postal} 區已達單次查詢上限")
            result.examined += len(rows)
            for row in rows:
                # Most results are regular full-time jobs; only take actual intern/RA postings.
                if not re.search(r"實習|研究助理|研究工讀|\bintern(?:ship)?\b|research assistant", row["OCCU_DESC"], re.I):
                    continue
                url = public_url(row["URL_QUERY"], "job.taiwanjobs.gov.tw", keep_query=True)
                identifier = parse_qs(urlsplit(url).query)["HIRE_ID"][0]
                result.postings.append(Posting(f"taiwanjobs-{identifier}", row["OCCU_DESC"], row["COMPNAME"], url,
                                               row["CITYNAME"], row.get("JOB_DETAIL", ""), row.get("WK_TYPE", ""),
                                               updated=date_value(row.get("TRANDATE")), deadline=date_value(row.get("STOP_DATE"))))
        except SOURCE_ERRORS as error:
            result.issues.append(f"{postal} 區：{type(error).__name__}")
    if len(result.issues) == 12 and not result.examined:
        raise ValueError("All Taipei district requests failed")
    return result


def read_line(source: Source, today: dt.date) -> Batch:
    rows = fetch_json(source.endpoint)["result"]["data"]["allStrapiJobs"]["edges"]
    if not rows:
        raise ValueError("LINE recruiting list is empty or changed format")
    result = Batch()
    for entry in rows:
        row = entry["node"]
        if not row["publish"] or not row.get("is_public"):
            continue
        location = " / ".join(city["name"] for city in row["cities"])
        if not re.search(r"\btaipei\b", location, re.I):
            continue
        posted = date_value(row.get("start_date"))
        end = None if row.get("until_filled") else date_value(row.get("end_date"))
        if (posted and posted > today) or (end and end < today):
            continue
        result.examined += 1
        commitment = " / ".join(item["name"] for item in row["employment_type"])
        if not re.search(r"\bintern\b", commitment, re.I):
            continue
        identifier = int(row["strapiId"])
        url = f"https://careers.linecorp.com/jobs/{identifier}/"
        try:
            detail = fetch_json(f"https://careers.linecorp.com/page-data/jobs/{identifier}/page-data.json")["result"]["data"]["strapiJobs"]
            if not detail["publish"]:
                continue
            result.postings.append(Posting(f"line-{identifier}", row.get("title_en") or row["title"],
                                           " / ".join(item["name"] for item in row["companies"]), url,
                                           location, clean_html(detail["content"]), commitment, posted=posted, deadline=end,
                                           rolling_open=bool(row.get("until_filled"))))
        except SOURCE_ERRORS as error:
            result.issues.append(f"職缺 {identifier}：{type(error).__name__}")
    return result


def read_rss(source: Source, today: dt.date) -> Batch:
    root = parse_xml(fetch_text(source.endpoint))
    if root.find("channel") is None:
        raise ValueError("Expected an RSS channel")
    items = root.findall("./channel/item")
    postings = []
    for item in items:
        title = item.findtext("title") or ""
        if source.board == "nstc":
            title = re.sub(r"\s+1\d{2}年\d{1,2}月\d{1,2}日\s*$", "", title)
        text = clean_html(item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or item.findtext("description") or "")
        posted = date_value(item.findtext("pubDate"))
        link = public_url(item.findtext("link"), urlsplit(source.url).hostname, keep_query=source.board == "nstc")
        identifier = urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1]
        # Feed publishers may advertise jobs at other schools. Trust only the work-location field.
        location = notice_location(text)
        if not location:
            continue
        organization_match = re.match(r"^(?:\[徵才\]\s*)?([^，。｜_、\s]{2,32}?(?:大學|研究院|研究所|學院))", title)
        organization = ("台大經濟系／公告單位" if source.board == "ntu-econ" else
                        organization_match[1] if organization_match else "國科會求才／公告單位")
        postings.append(Posting(f"{source.board}-{identifier}", title, organization, link, location, text,
                                posted=posted, deadline=deadline_in(text, posted),
                                rolling_open=bool(re.search(r"隨到隨審|額滿為止|until (?:the positions are )?filled|rolling basis", text, re.I))))
    return Batch(postings, len(items))


def sinica_fields(page: str) -> dict[str, str]:
    labels = {"單位", "職務名稱", "工作內容", "應徵資格", "工作地點", "截止日期", "刊登日期", "刊登時間"}
    fields = re.findall(r"<span>\s*([^<]{1,160})\s*</span>\s*<p\b[^>]*>(.*?)</p>", page, re.S)
    return {label: clean_html(value) for name, value in fields if (label := clean_html(name)) in labels}


def read_sinica(source: Source, today: dt.date) -> Batch:
    result = Batch()
    max_pages = 4
    for page in range(1, max_pages + 1):
        body = fetch_text(f"{source.endpoint}&pagenumber={page}&pagesize=36")
        sections = re.split(r'<div\s+class="recruiting"\s*>', body)[1:]
        if not sections:
            raise ValueError("Unexpected Sinica recruiting-list format")
        result.examined += len(sections)
        for section in sections:
            match = re.search(r"href=['\"](/recruitment_content/53/(\d+))['\"]>\s*([^<]+)", section)
            if not match:
                result.issues.append("有公告無法解析")
                continue
            path, identifier, title = match.groups()
            title = clean_html(title)
            summary = clean_html(section.split('<div class="recruiting_bot">', 1)[0])
            if not re.search(r"研究助理|專[（(、兼]*任助理|計畫.*助理|實習|research assistant", title, re.I):
                continue
            # Pre-filter so we do not request the details of every wet-lab or engineering post.
            if not re.search(r"人文及社會|統計科學|環境變遷|經濟|社會科學|資料分析|資料科學|數據分析|實證|實驗設計|[Cc]ausal", summary):
                continue
            url = urljoin(source.url, path)
            try:
                detail = fetch_text(url)
                fields = sinica_fields(detail)
                if not {"職務名稱", "工作內容", "工作地點", "截止日期"}.issubset(fields):
                    raise ValueError("Unexpected Sinica posting fields")
                result.postings.append(Posting(f"sinica-{identifier}", title, "中研院｜" + fields.get("單位", "研究單位"),
                                               url, campus_location(fields["工作地點"]),
                                               fields["工作內容"] + "\n" + fields.get("應徵資格", ""),
                                               posted=date_value(fields.get("刊登日期") or fields.get("刊登時間")),
                                               deadline=date_value(fields["截止日期"])))
            except SOURCE_ERRORS as error:
                result.issues.append(f"公告 {identifier}：{type(error).__name__}")
        if not re.search(rf"/recruitment/53\?pagenumber={page + 1}\b", body):
            break
    return result


def read_himalayas(source: Source, today: dt.date) -> Batch:
    result = Batch()
    for filters in ({"employment_type": "Intern"}, {"q": "research assistant"}):
        for page in range(1, 4):
            params = {"country": "TW", "sort": "recent", "page": page, **filters}
            try:
                data = fetch_json(source.endpoint + "?" + urlencode(params))
                rows = data["jobs"]
                if not isinstance(rows, list):
                    raise ValueError("Invalid Himalayas job list")
                result.examined += len(rows)
                for row in rows:
                    countries, offsets = row["locationRestrictions"], row["timezoneRestrictions"]
                    if not isinstance(countries, list) or not isinstance(offsets, list):
                        raise ValueError("Missing structured remote eligibility")
                    if countries and not any(re.search(r"\btaiwan\b|臺灣|台灣", name, re.I) for name in countries):
                        continue
                    if offsets and 8 not in offsets:
                        continue
                    url = public_url(row["guid"], "himalayas.app")
                    result.postings.append(Posting(f"himalayas-{urlsplit(url).path}", row["title"], row["companyName"], url,
                                                   "Remote — Taiwan" if countries else "Remote — Worldwide",
                                                   clean_html(row.get("description", "")), row.get("employmentType", ""), "remote",
                                                   updated=date_value(row.get("pubDate")), deadline=date_value(row.get("expiryDate")),
                                                   third_party=True))
                if data["offset"] + data["limit"] >= data["totalCount"]:
                    break
            except SOURCE_ERRORS as error:
                result.issues.append(f"遠端搜尋第 {page} 頁：{type(error).__name__}")
                break
    if result.issues and not result.examined:
        raise ValueError("No remote search request could be read")
    return result


READERS = {"greenhouse": read_greenhouse, "lever": read_lever, "taiwanjobs": read_taiwanjobs,
           "line": read_line, "rss": read_rss, "sinica": read_sinica, "himalayas": read_himalayas}


def read_source(source: Source, today: dt.date) -> Batch:
    if source.kind in {"campus", "bank", "reviewed", "manual-leads", "workday"}:
        from recruiting_notices import NOTICE_READERS
        return NOTICE_READERS[source.kind](source, today)
    return READERS[source.kind](source, today)
