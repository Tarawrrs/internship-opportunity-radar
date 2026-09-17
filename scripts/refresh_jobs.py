#!/usr/bin/env python3
"""Refresh the internship radar from a small set of official recruiting feeds."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "dist" / "data"
JOBS_PATH = DATA_DIR / "jobs.json"
ARCHIVE_PATH = DATA_DIR / "archive.json"
META_PATH = DATA_DIR / "scan-meta.json"
UTC = dt.timezone.utc

SOURCES = [
    ("greenhouse", "appier", "Appier", "https://boards-api.greenhouse.io/v1/boards/appier/jobs?content=true"),
    ("greenhouse", "point72", "Point72", "https://boards-api.greenhouse.io/v1/boards/point72/jobs?content=true"),
    ("greenhouse", "worldquant", "WorldQuant", "https://boards-api.greenhouse.io/v1/boards/worldquant/jobs?content=true"),
    ("greenhouse", "agoda", "Agoda", "https://boards-api.greenhouse.io/v1/boards/agoda/jobs?content=true"),
    ("greenhouse", "anthropic", "Anthropic", "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true"),
    ("greenhouse", "mercari", "Mercari", "https://boards-api.greenhouse.io/v1/boards/mercari/jobs?content=true"),
    ("lever", "shopback-2", "ShopBack", "https://api.lever.co/v0/postings/shopback-2?mode=json"),
    ("lever", "ninjavan", "Ninja Van", "https://api.lever.co/v0/postings/ninjavan?mode=json"),
]

MANUAL_JOBS = [
    {
        "id": "simular-data-analyst-intern",
        "title": "Data Analyst Intern",
        "company": "Simular",
        "location": "新加坡",
        "locationKey": "sg",
        "track": "industry",
        "score": 93,
        "priority": "先查資格",
        "priorityType": "watch",
        "timing": "目前開放；on-site",
        "eligibility": "統計、CS、經濟等學士／碩士在學；SQL、Python 或 R；職缺未在頁面明示工作授權",
        "fit": "直接做 activation、retention、task success、實驗設計與 agent reliability，工作內容和 experimentation／product analytics 高度重合。",
        "risk": "工作授權、實習長度與是否能配合碩士課程皆需先確認。",
        "source": "https://jobs.ashbyhq.com/simular/7147a575-c7da-44d3-a6d6-2cdd4d24b94a",
        "skills": ["SQL", "Python/R", "實驗設計", "產品指標"],
    },
    {
        "id": "jpal-general-data-ra-2027",
        "title": "General Data Research Associate",
        "company": "J-PAL／合作研究機構",
        "location": "多地，依計畫配置",
        "locationKey": "global",
        "track": "research",
        "score": 91,
        "priority": "準備申請",
        "priorityType": "priority",
        "timing": "早鳥申請 2026-09-08 至 2026-10-09；預計 2027 夏季起",
        "eligibility": "經濟／社科／公共政策／數理相關學士或碩士；micro、econometrics、statistics；Stata 或同類工具與大型資料經驗",
        "fit": "資料清理分析、研究報告、IRB 與 field-data quality；對 applied micro、因果推論、推薦信和 PhD option value 很強。",
        "risk": "這是畢業前後的 RA／predoc 型機會，不是一般學期間實習；各地工作授權與到職時間需逐一確認。",
        "source": "https://www.povertyactionlab.org/careers/general-data-research-associate-job-105606",
        "skills": ["Stata/R", "因果推論", "研究設計", "Applied micro"],
        "expires": "2027-01-13",
    },
    {
        "id": "jpal-general-field-ra-2027",
        "title": "General Field Research Associate",
        "company": "J-PAL／合作研究機構",
        "location": "多地，依計畫配置",
        "locationKey": "global",
        "track": "research",
        "score": 84,
        "priority": "值得查",
        "priorityType": "priority",
        "timing": "完整招募期預計 2026-11-25 開放，2027-01-13 截止；預計 2027 夏季起",
        "eligibility": "經濟／社科／公共政策等學士或碩士；micro、econometrics、statistics；Stata 與 field research 經驗加分",
        "fit": "可累積 RCT、survey、field operations 與資料品質管理經驗，適合用來測試 research／predoc 路線。",
        "risk": "相較 Data Research Associate，現場管理與協調比重更高；各地工作授權與長期派駐需逐案確認。",
        "source": "https://www.povertyactionlab.org/careers/general-field-research-associate-job-105607",
        "skills": ["Stata", "RCT", "Survey", "Field research"],
        "expires": "2027-01-13",
    },
    {
        "id": "watsons-ai-data-science-intern",
        "title": "AI & Data Science Intern",
        "company": "台灣屈臣氏",
        "location": "臺北，臺灣",
        "locationKey": "tw",
        "track": "industry",
        "score": 86,
        "priority": "值得投",
        "priorityType": "priority",
        "timing": "2026-09 查核時仍刊登；每週 2–3 天（約 16–24 小時）",
        "eligibility": "職缺頁面主打銷售預測、商品分群與誤差分析；詳細資格需進入招募頁確認",
        "fit": "有完整問題定義、模型、誤差診斷到落地流程，能留下可描述的商業分析成果。",
        "risk": "偏 forecasting／data science，需確認實際 mentor、SQL／Python 使用比例與是否能形成可公開作品。",
        "source": "https://www.104.com.tw/jobs/search/?keyword=%E5%8F%B0%E7%81%A3%E5%B1%88%E8%87%A3%E6%B0%8F%20AI%20Data%20Science%20Intern",
        "skills": ["預測", "商品分群", "模型診斷", "零售資料"],
        "expires": "2026-10-31",
    },
    {
        "id": "nanshan-data-intern",
        "title": "數據分析實習",
        "company": "南山人壽",
        "location": "臺北，臺灣",
        "locationKey": "tw",
        "track": "finance",
        "score": 82,
        "priority": "列入組合",
        "priorityType": "watch",
        "timing": "下半年通常 10–12 月；總公司學期實習每週至少 2 日",
        "eligibility": "大專院校在學生，大三以上或碩士生尤佳；官方 FAQ 列出碩士學期實習時薪 NT$240",
        "fit": "數據洞察、使用者研究與數位專案，可測試金融資料／風控次線，同時維持分析主軸。",
        "risk": "官方頁是實習計畫總覽，不是單一職缺；投遞前需查當期部門、內容與截止日。",
        "source": "https://www.nanshanlife.com.tw/nanshanlife/nsintern-1/",
        "skills": ["金融資料", "數據洞察", "數位專案"],
    },
]

ALLOWED_LOCATION = re.compile(
    r"taipei|taiwan|singapore|japan|tokyo|asia|remote|multiple|beijing|shanghai|hanoi|ho chi minh|jakarta|kuala lumpur|bangkok|hong kong|london|ontario|united states",
    re.I,
)
ROLE_KEYWORDS = re.compile(
    r"data|product|business|strategy|research|econom|decision|experiment|insight|analytics|risk|credit|quant|pricing|market access|rwe|heor|fellow",
    re.I,
)


def fetch_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Tarawrrs-internship-radar/1.0 (+GitHub Actions)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:90] or "job"


def location_info(raw: str) -> tuple[str, str]:
    if re.search(r"taipei|taiwan", raw, re.I):
        return "臺北／臺灣", "tw"
    if re.search(r"singapore", raw, re.I):
        return "新加坡", "sg"
    if re.search(r"japan|tokyo", raw, re.I):
        return "日本／東京", "jp"
    if re.search(r"beijing|shanghai", raw, re.I):
        return "北京／上海", "asia"
    if re.search(r"hanoi|ho chi minh", raw, re.I):
        return "越南", "asia"
    if re.search(r"jakarta|indonesia", raw, re.I):
        return "印尼", "asia"
    if re.search(r"kuala lumpur|malaysia", raw, re.I):
        return "馬來西亞", "asia"
    if re.search(r"bangkok|thailand", raw, re.I):
        return "泰國", "asia"
    if re.search(r"hong kong", raw, re.I):
        return "香港", "asia"
    return raw or "地點待確認", "global"


def title_relevant(title: str, commitment: str = "") -> bool:
    if re.search(r"research (assistant|associate)", title, re.I):
        return True
    if re.search(r"fellow", title, re.I) and ROLE_KEYWORDS.search(title):
        return True
    is_intern = re.search(r"\bintern(?:ship)?\b", f"{title} {commitment}", re.I)
    return bool(is_intern and ROLE_KEYWORDS.search(title))


def score_job(title: str, description: str, company: str, location: str) -> int:
    text = f"{title} {description}"
    score = 54
    rules = [
        (r"data analyst|product analy", 22),
        (r"data science|business.*strategy|strategy.*business", 12),
        (r"research assistant|research associate|economist|economic", 16),
        (r"product management|product builder", 8),
        (r"experiment|a/b|causal", 8),
        (r"sql", 6),
        (r"python|stata|\br\b", 5),
        (r"dashboard|metric|insight", 4),
        (r"intern", 5),
        (r"sales development|account executive|cold call", -28),
        (r"trader|trading|quantitative alpha", -12),
        (r"software engineer|developer", -10),
    ]
    for pattern, points in rules:
        if re.search(pattern, text, re.I):
            score += points
    if company == "Appier" and re.search(r"data analyst", title, re.I):
        score += 5
    if re.search(r"taipei|taiwan", location, re.I):
        score += 4
    elif re.search(r"singapore|japan|tokyo", location, re.I):
        score += 2
    return max(35, min(96, score))


def skills_for(text: str) -> list[str]:
    candidates = [
        (r"sql", "SQL"), (r"python", "Python"), (r"stata", "Stata"),
        (r"\br\b", "R"), (r"experiment|a/b", "實驗設計"),
        (r"dashboard|visuali", "Dashboard"), (r"research", "研究"),
        (r"metric|product", "產品指標"),
    ]
    result = [label for pattern, label in candidates if re.search(pattern, text, re.I)]
    return result[:4] or ["待人工判讀"]


def priority_for(score: int) -> tuple[str, str]:
    if score >= 90:
        return "優先查核", "priority"
    if score >= 84:
        return "值得查", "priority"
    if score >= 76:
        return "先查資格", "watch"
    if score >= 65:
        return "觀察", "risk"
    return "低契合備選", "risk"


def track_for(text: str) -> str:
    if re.search(r"research|economist|economic|predoc", text, re.I):
        return "research"
    if re.search(r"risk|credit|finance", text, re.I):
        return "finance"
    return "industry"


def make_job(*, source_id: str, source_key: str, title: str, company: str, location_raw: str, description: str, source: str, checked: str) -> dict:
    score = score_job(title, description, company, location_raw)
    priority, priority_type = priority_for(score)
    location, location_key = location_info(location_raw)
    text = f"{title} {description}"
    track = track_for(text)
    if track == "research":
        fit = "符合 applied micro／研究分析關鍵字，可能累積方法、研究產出與 PhD option value。"
    else:
        fit = "符合資料、產品或實驗分析關鍵字，可進一步判斷是否能累積 SQL／Python 與決策成果。"
    if location_key == "tw":
        risk = "投遞前確認每週天數、實習長度、mentor 與實際分析工作比例。"
    else:
        risk = "投遞前先確認工作授權、是否需在地就讀／居住，以及全職時程是否可行。"
    job = {
        "id": source_id,
        "sourceKey": source_key,
        "title": title,
        "company": company,
        "location": location,
        "locationKey": location_key,
        "track": track,
        "score": score,
        "priority": priority,
        "priorityType": priority_type,
        "timing": "官方招募頁在本次掃描時仍列出；精確起訖與截止日請開啟來源確認",
        "eligibility": "由官方招募系統擷取；投遞前請核對完整資格",
        "fit": fit,
        "risk": risk,
        "source": source,
        "checked": checked,
        "skills": skills_for(text),
    }
    if company == "Appier" and title.lower() == "data analyst intern":
        job.update({
            "score": 95,
            "priority": "優先投",
            "priorityType": "priority",
            "timing": "官方頁目前列出；每週 2–3 天、至少 6 個月，申請欄另提及 12 個月安排",
            "eligibility": "大四或研究生；SQL、統計、Excel、Python automation；英文溝通",
            "fit": "與產品 R&D 合作，做資料分析、監控與流程自動化；能直接推進 SQL／Python 與商業轉譯。",
            "risk": "先確認學期能否穩定排出每週 2–3 天，以及 6 個月與 12 個月敘述的實際承諾。",
            "skills": ["SQL", "Python", "產品分析", "統計"],
        })
    if company == "ShopBack" and title.lower().startswith("data analyst"):
        job.update({
            "score": 80,
            "priority": "觀察",
            "priorityType": "risk",
            "timing": "2027 上半年；至少 6 個月 full-time、on-site",
            "eligibility": "SQL 必備，Python 加分；官方頁目前只考慮人在新加坡的候選人",
            "fit": "metrics、data model、dashboard、AI data tools 與 stakeholder decision support 很貼近目標定位。",
            "risk": "六個月全職與目前碩士主線可能衝突；且地點限制明確，不應在未解決資格前投入大量申請時間。",
            "skills": ["SQL", "Python", "Dashboard", "數據模型"],
        })
    return job


def greenhouse_jobs(board: str, company: str, url: str, checked: str) -> list[dict]:
    data = fetch_json(url)
    result = []
    for raw in data.get("jobs", []):
        title = raw.get("title", "")
        location = (raw.get("location") or {}).get("name", "")
        if not title_relevant(title) or not ALLOWED_LOCATION.search(location):
            continue
        description = clean_html(raw.get("content", ""))
        job = make_job(
            source_id=f"gh-{board}-{raw.get('id', slug(title))}",
            source_key=f"greenhouse:{board}",
            title=title,
            company=company,
            location_raw=location,
            description=description,
            source=raw.get("absolute_url", ""),
            checked=checked,
        )
        if job["score"] >= 58:
            result.append(job)
    return result


def lever_jobs(board: str, company: str, url: str, checked: str) -> list[dict]:
    data = fetch_json(url)
    result = []
    for raw in data:
        title = raw.get("text", "")
        categories = raw.get("categories") or {}
        location = categories.get("location", "")
        commitment = categories.get("commitment", "")
        if not title_relevant(title, commitment) or not ALLOWED_LOCATION.search(location):
            continue
        description = " ".join([raw.get("descriptionPlain", ""), raw.get("additionalPlain", "")])
        job = make_job(
            source_id=f"lever-{board}-{raw.get('id', slug(title))}",
            source_key=f"lever:{board}",
            title=title,
            company=company,
            location_raw=location,
            description=description,
            source=raw.get("hostedUrl", ""),
            checked=checked,
        )
        if job["score"] >= 58:
            result.append(job)
    return result


def load_meta() -> dict:
    if not META_PATH.exists():
        return {}
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def load_list(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (ValueError, OSError):
        return []


def source_key_for(job: dict) -> str:
    if job.get("sourceKey"):
        return job["sourceKey"]
    identifier = job.get("id", "")
    company = job.get("company", "").lower()
    if identifier.startswith("gh-"):
        parts = identifier.split("-", 2)
        return f"greenhouse:{parts[1]}" if len(parts) > 2 else "unknown"
    if identifier.startswith("lever-"):
        if "shopback" in identifier or "shopback" in company:
            return "lever:shopback-2"
        if "ninja" in identifier or "ninja van" in company:
            return "lever:ninjavan"
    return "manual"


def due(days: int, now: dt.datetime) -> bool:
    value = load_meta().get("last_successful_scan")
    if not value:
        return True
    try:
        previous = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    return now - previous.astimezone(UTC) >= dt.timedelta(days=days)


def active_manual_jobs(today: dt.date, checked: str) -> list[dict]:
    result = []
    for raw in MANUAL_JOBS:
        expiry = raw.get("expires")
        if expiry and today > dt.date.fromisoformat(expiry):
            continue
        job = {key: value for key, value in raw.items() if key != "expires"}
        job["sourceKey"] = "manual"
        job["checked"] = checked
        result.append(job)
    return result


def dedupe(jobs: list[dict]) -> list[dict]:
    chosen: dict[tuple[str, str, str], dict] = {}
    for job in sorted(jobs, key=lambda value: value["score"], reverse=True):
        key = (job["company"].lower(), job["title"].lower(), job["locationKey"])
        chosen.setdefault(key, job)
    return sorted(chosen.values(), key=lambda value: (-value["score"], value["company"], value["title"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-due", type=int, default=0, metavar="DAYS")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    now = dt.datetime.now(UTC)
    if args.if_due and not args.force and not due(args.if_due, now):
        print(f"Not due: the last successful scan is less than {args.if_due} days old.")
        return 0

    checked = now.date().isoformat()
    previous_jobs = load_list(JOBS_PATH)
    previous_archive = load_list(ARCHIVE_PATH)
    jobs = active_manual_jobs(now.date(), checked)
    source_status = []
    successful_sources = {"manual"}
    failed_sources = set()
    failures = 0
    for kind, board, company, url in SOURCES:
        source_key = f"{kind}:{board}"
        try:
            if kind == "greenhouse":
                fetched = greenhouse_jobs(board, company, url, checked)
            else:
                fetched = lever_jobs(board, company, url, checked)
            jobs.extend(fetched)
            successful_sources.add(source_key)
            source_status.append({"source": company, "sourceKey": source_key, "status": "ok", "matches": len(fetched)})
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
            failures += 1
            failed_sources.add(source_key)
            source_status.append({"source": company, "sourceKey": source_key, "status": "error", "message": type(error).__name__})

    if failures == len(SOURCES):
        print("All live sources failed; preserving the previous published data.", file=sys.stderr)
        return 1

    previous_by_id = {job["id"]: job for job in previous_jobs if job.get("id")}
    archive_by_id = {job["id"]: job for job in previous_archive if job.get("id")}

    current_ids = {job["id"] for job in jobs}
    for old_job in previous_jobs:
        key = source_key_for(old_job)
        if old_job.get("id") not in current_ids and key in failed_sources:
            preserved = dict(old_job)
            preserved["sourceKey"] = key
            jobs.append(preserved)

    jobs = dedupe(jobs)
    current_ids = {job["id"] for job in jobs}
    for job in jobs:
        old = previous_by_id.get(job["id"]) or archive_by_id.get(job["id"], {})
        job["sourceKey"] = source_key_for(job)
        job["firstSeen"] = old.get("firstSeen") or old.get("checked") or checked
        job["lastSeen"] = checked if job["sourceKey"] in successful_sources else old.get("lastSeen", checked)
        job["status"] = "active"
        archive_by_id.pop(job["id"], None)

    for old_job in previous_jobs:
        identifier = old_job.get("id")
        key = source_key_for(old_job)
        if not identifier or identifier in current_ids or key not in successful_sources:
            continue
        if key != "manual" and not title_relevant(old_job.get("title", "")):
            continue
        archived = dict(old_job)
        archived.update({
            "sourceKey": key,
            "status": "archived",
            "archived": True,
            "firstSeen": old_job.get("firstSeen") or old_job.get("checked") or checked,
            "lastSeen": old_job.get("lastSeen") or old_job.get("checked") or checked,
            "archivedAt": checked,
            "archiveReason": "人工追蹤日期已過或已移出清單" if key == "manual" else "本次成功掃描後未再出現在官方來源；可能已截止或下架",
        })
        archive_by_id[identifier] = archived

    archive = sorted(
        archive_by_id.values(),
        key=lambda value: (value.get("archivedAt", ""), value.get("lastSeen", ""), value.get("score", 0)),
        reverse=True,
    )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_PATH.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta = {
        "last_successful_scan": now.isoformat().replace("+00:00", "Z"),
        "interval_days": args.if_due or 5,
        "job_count": len(jobs),
        "archive_count": len(archive),
        "sources": source_status,
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(jobs)} matching opportunities; {failures} source(s) failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
