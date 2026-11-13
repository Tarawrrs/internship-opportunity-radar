#!/usr/bin/env python3
"""Discover fresh Taipei internships and research roles, with a durable history."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys

from job_sources import SOURCES, SOURCE_ERRORS, TAIPEI, Posting, Source, deadline_in, read_source
from location_rules import POLICY_VERSION, classify_location
from winter_rules import winter_details, winter_year

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "dist" / "data"
INTERVAL_DAYS = 1
NOTICE_WINDOW_DAYS = 35
PENDING_GRACE_DAYS = 10
RECENT_DISCOVERY_DAYS = 7

INTERNSHIP = re.compile(r"\bintern(?:ship)?\b|實習|寒假.{0,12}工讀|研究工讀|學習型獎助生", re.I)
RESEARCH_ROLE = re.compile(r"\bresearch (?:assistant|associate)\b|\bpre[- ]?doc(?:toral)?\b|研究助理|研究工讀", re.I)
PROJECT_ASSISTANT = re.compile(r"(?:專任|兼任|專案|計[畫劃]).{0,9}(?:助理|助理專員)|research intern", re.I)
TARGET_TITLE = re.compile(
    r"\b(?:data|analytic[ss]?|analyst|product|economics?|econometric\w*|statistics?|strategy|"
    r"risk|pricing|quantitative|market research|user research|experimentation|business intelligence)\b|"
    r"數據|數位分析|資料分析|資料科學|統計|產品|風[險控]|經濟|策略|廣告平台營運|商業分析|使用者研究", re.I)
METHOD = re.compile(
    r"data (?:analy\w*|scien\w*|clean\w*|model\w*|processing|visuali\w*|engineering|quality)|"
    r"statistical (?:analy\w*|method\w*|inference|model\w*)|applied micro|econometric\w*|"
    r"causal inference|a/b test|experiment(?:al design|ation|s)\b|forecast\w*|survey data|"
    r"product metric|dashboard|business intelligence|quantitative (?:analysis|research)|"
    r"risk model|recommendation|machine learning|evaluation metrics|user behavio[u]?r|"
    r"(?:資料|數據).{0,5}(?:清理|分析|處理|視覺化|挖掘|治理)|(?:分析|整理).{0,7}(?:資料|數據)|"
    r"統計(?:分析|方法|模型|推論|歸因)|實證|因果推論|計量|實驗設計|神經經濟|賽局理論|"
    r"機器學習|問卷調查|調查資料|使用者行為|成效報表|人口社經|資料科學|[Ss]tata|[Ss][Qq][Ll]", re.I)
RESEARCH_DOMAIN = re.compile(
    r"經濟|社會科學|社會學|心理學|行為科學|社會調查|公共政策|政治學|人口|教育政策|統計|資料科學|語言學|"
    r"economic|social science|sociology|psychology|public policy|political science|behavioral|demograph|statistics|linguistics", re.I)
UNRELATED_TITLE = re.compile(
    r"助理教授|副教授|專任師資|院長|所長|系主任|行政助理|行政工讀|純行政|餐飲|護理|"
    r"儲備店長|才藝|幼兒|人才招募實習|人資實習|樣本前處理|觀測採樣|網站與資訊系統開發|"
    r"\b(?:professor|faculty|talent acquisition|sales development|account executive)\b", re.I)
LAB_ONLY = re.compile(r"細胞培養|分子生物|細胞與個體生物|基因轉殖|育苗|種子處理|動物實驗|wet lab|cell culture|molecular biology", re.I)


def role_kind(post: Posting) -> str | None:
    title = post.title.strip()
    if UNRELATED_TITLE.search(title):
        return None
    body = post.description
    # Ignore internships mentioned only in boilerplate or an ordinary employee's qualifications.
    internship = INTERNSHIP.search(f"{title} {post.commitment}")
    ra = RESEARCH_ROLE.search(title)
    if internship and not ra:
        if LAB_ONLY.search(title) or re.search(r"(?:實習|internship).{0,12}(?:說明會|講座)$", title, re.I):
            return None
        if re.search(r"研究實習|\bresearch intern\b", title, re.I) and RESEARCH_DOMAIN.search(f"{title}\n{body}"):
            return "research-intern"
        return "intern"
    if not (ra or PROJECT_ASSISTANT.search(title)):
        return None
    substantive = bool(METHOD.search(f"{title}\n{body}"))
    domain = bool(RESEARCH_DOMAIN.search(f"{title}\n{body}"))
    if LAB_ONLY.search(f"{post.company}\n{title}\n{body}") and not domain:
        return None
    if not (substantive or (ra and domain)):
        return None
    if re.search(r"兼[)）]?任|兼職|part[- ]time", f"{title} {post.commitment}", re.I):
        return "part-time-ra"
    if re.search(r"\bpre[- ]?doc(?:toral)?\b", title, re.I):
        return "predoc"
    if re.search(r"專任|全職|full[- ]time", f"{title} {post.commitment}", re.I):
        return "full-time-ra"
    return "research"


def fit_score(post: Posting, kind: str) -> tuple[int, list[str]]:
    text = post.title + "\n" + post.description
    score = {"intern": 59, "research-intern": 62, "part-time-ra": 65, "predoc": 64,
             "full-time-ra": 52, "research": 55}[kind]
    skills = []
    for pattern, points, label in [
        (r"econometric|applied micro|causal inference|empirical economics|因果|計量|實證|經濟史", 15, "實證／因果"),
        (r"data analy|數據分析|資料分析|統計分析|statistical analy|data science|資料科學|(?:資料|數據).{0,5}(?:清理|處理|分析)", 12, "資料分析"),
        (r"experiment(?:al design|ation|s)\b|a/b test|實驗設計|統計推論|evaluation metrics", 9, "實驗／評估"),
        (r"product analy|product management|產品分析|產品企劃|使用者行為", 7, "產品分析"),
        (r"\bsql\b", 5, "SQL"),
        (r"\bpython\b", 5, "Python"),
        (r"\bstata\b", 5, "Stata"),
        (r"\bR\b(?!\s*&\s*D)", 3, "R"),
        (r"問卷|調查資料|survey data", 6, "調查資料"),
        (r"dashboard|視覺化|成效報表", 4, "報表／視覺化"),
        (r"gis|地理資訊|空間分析", 4, "GIS"),
    ]:
        if re.search(pattern, text, re.I if label != "R" else 0):
            skills.append(label)
            score += points
    if kind == "intern" and TARGET_TITLE.search(post.title):
        score += 8
    if re.search(r"限.{0,8}資工|computer science or related|工程開發|backend|後端|軟體開發", post.title + "\n" + post.description, re.I):
        score -= 6
    if re.search(r"行銷|廣告平台營運", post.title):
        score -= 7
    return max(35, min(96, score)), skills[:5]


def safe_id(value: str) -> str:
    # Preserve existing ids where possible so device-local bookmarks still work.
    if re.fullmatch(r"[a-zA-Z0-9_-]{1,120}", value):
        return value
    return value.split("-", 1)[0] + "-" + hashlib.sha256(value.encode()).hexdigest()[:20]


def iso(value: dt.date | None) -> str | None:
    return value.isoformat() if value else None


def make_job(post: Posting, source: Source, today: dt.date, now: dt.datetime | None = None) -> dict | None:
    kind = role_kind(post)
    if not kind or (post.posted and post.posted > today):
        return None
    deadline = deadline_in(post.description, post.posted or post.updated)
    if post.deadline:
        deadline = min(deadline, post.deadline) if deadline else post.deadline
    cutoff = post.deadline_time if deadline and deadline == post.deadline else ""
    if deadline and (deadline < today or
                     (deadline == today and cutoff and now and now.strftime("%H:%M") >= cutoff)):
        return None
    if source.kind == "rss" and not deadline and (
        not post.posted or (today - post.posted).days > NOTICE_WINDOW_DAYS
    ):
        return None
    if re.search(r"^(?:[【\[]?(?:已額滿|已截止|停止收件|已結束招募)|position (?:closed|filled))", post.title, re.I):
        return None

    location = classify_location(post.location, post.description, post.workplace)
    if location["locationDisposition"] == "excluded":
        return None
    # Publish the job-location and work-mode fields, not prose or contact details from the source.
    location["locationEvidence"] = location["locationEvidence"][:1 + bool(post.workplace)]
    score, skills = fit_score(post, kind)
    if kind not in {"intern", "research-intern"} and score < 58 and not re.search(
        r"經濟研究所|經濟系|economics|語言學|linguistics", f"{post.company} {post.title}", re.I
    ):
        return None
    job_type = {"intern": "工讀" if "工讀" in post.title else "實習", "research-intern": "研究實習",
                "part-time-ra": "兼任研究助理", "full-time-ra": "全職研究助理",
                "predoc": "Predoc", "research": "研究職缺"}[kind]
    status = "confirmed"
    reason = ""
    if post.verification_note:
        status = "pending"
        reason = post.verification_note
    elif post.third_party:
        status = "pending"
        reason = "遠端平台標記接受台灣、UTC+8；原雇主刊登與地區限制仍需確認。"
    elif location["locationDisposition"] == "review":
        status = "pending"
        reason = location["locationReason"]
    elif post.location_needs_check:
        status = "pending"
        reason = "公告同時列出外縣市，請在投遞前核對所選職缺的實際辦公地點。"
    elif source.kind in {"rss", "campus"} and not (deadline or post.rolling_open):
        status = "pending"
        reason = "近期求才公告未列明截止日或隨到隨審，請確認是否仍收件。"

    if post.third_party:
        timing = f"平台刊登到期：{iso(post.deadline)}；雇主可能已先下架。" if post.deadline else "平台未列到期日；以雇主招募頁為準。"
    elif deadline:
        timing = f"公告截止：{iso(deadline)}。如提前額滿，以原公告為準。"
    elif post.rolling_open:
        timing = "公告採隨到隨審或額滿為止，投遞前確認尚有名額。"
    else:
        timing = "本輪仍列於招募清單，來源未提供明確截止日。"

    eligibility = post.eligibility or "請在原公告核對學籍、所需技能與每週工時。"
    if not post.eligibility and re.search(r"臺大在學學生|台大在學學生|currently enrolled NTU student", post.description, re.I):
        eligibility = "限台大在學學生（大學部或研究所）；其他條件見原公告。"
    elif kind == "full-time-ra":
        eligibility = "全職職缺，需核對到職日、學位要求與能否配合目前課業。"

    winter_status, period = winter_details(post.title, post.description, today)
    if kind in {"full-time-ra", "predoc"}:
        winter_status = "other"
    return {
        "id": safe_id(post.id), "sourceKey": source.key, "sourceName": source.name,
        "source": post.url, "title": post.title.strip(), "company": post.company.strip(),
        "location": post.location, **location, "jobType": job_type,
        "track": ("research" if kind != "intern" else
                  "finance" if re.search(r"risk|credit|compliance|bank|finance|風控|風險|金融|證券|銀行",
                                          f"{post.company} {post.title}", re.I) else "industry"),
        "winterStatus": post.winter_status or winter_status, "winterYear": winter_year(today),
        "period": post.period or period, "note": post.note, "applicationUrl": post.application_url,
        "score": score,
        "priority": "待查核" if status == "pending" else "優先查核" if score >= 88 else "值得看看" if score >= 72 else "備選",
        "priorityType": "watch" if status == "pending" else "priority" if score >= 88 else "watch",
        "fit": f"{job_type} · " + ("、".join(skills) if skills else "相關領域，工作內容請見原公告"),
        "skills": skills, "timing": timing, "eligibility": eligibility,
        "risk": ("從台灣全程線上仍須符合雇主的聘僱、工時與時區要求。"
                 if location["locationKey"] != "taipei" else "請核對每週工時、到班要求和實際分析／研究工作比重。"),
        "checked": iso(today), "postedAt": iso(post.posted), "sourceUpdatedAt": iso(post.updated),
        "deadline": iso(deadline), "deadlineTime": cutoff, "verificationStatus": status, "verificationNote": reason,
    }


def load_records(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(j, dict) or not j.get("id") for j in value):
        raise ValueError(f"Malformed history file: {path.name}")
    return value


def date_field(job: dict, key: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(job[key]) if job.get(key) else None
    except ValueError:
        return None


def duplicate_key(job: dict) -> tuple[str, str]:
    def normalize(value):
        return re.sub(r"[\W_]+", "", value.casefold())
    return normalize(job["company"]), normalize(job["title"])


def campus_identity(job: dict):
    title = job["title"]
    if "勤業眾信" in title and "ESG" in title:
        unit = re.search(r"諮詢組|確信組", title)
        if unit:
            return ("Deloitte ESG", unit[0], job.get("deadline"))
    link = job.get("applicationUrl", "")
    if link and "/company/" not in link:
        return link.rstrip("/")
    return duplicate_key(job)


def refresh_source(source: Source, today: dt.date, now: dt.datetime | None = None):
    try:
        result = read_source(source, today)
        candidates = [job for post in result.postings if (job := make_job(post, source, today, now))]
        status = "partial" if result.issues else "ok"
        summary = {"source": source.name, "sourceKey": source.key, "url": source.url, "status": status,
                   "examined": result.examined, "matches": len(candidates), "issues": result.issues[:12]}
        if source.kind == "manual-leads":
            summary["manual"] = True
            for job in candidates:
                job["checked"] = job["sourceUpdatedAt"]
        # Use employer listings to block duplicate/disagreeing third-party cards.
        identities = {duplicate_key({"company": p.company, "title": p.title}) for p in result.postings}
        return source, summary, candidates, identities
    except SOURCE_ERRORS as error:
        return source, {"source": source.name, "sourceKey": source.key, "url": source.url,
                        "status": "error", "examined": 0, "matches": 0,
                        "issues": [type(error).__name__]}, [], set()


def reconcile(previous: list[dict], history: list[dict], scans: list, today: dt.date, now: dt.datetime | None = None):
    """Keep only current confirmations active; carry old uncertain posts to review, then history."""
    previous_by_id = {job["id"]: job for job in previous}
    archived = {job["id"]: job for job in history}
    known = set(previous_by_id) | set(archived)
    current = {}
    summaries = {}
    source_lookup = {}
    campus_keys = set()
    official = set().union(*(identities for src, _, _, identities in scans if src.kind != "himalayas"))
    for src, summary, candidates, _ in scans:
        summaries[src.key] = summary
        source_lookup[src.key] = src
        for job in candidates:
            if src.kind == "himalayas" and duplicate_key(job) in official:
                continue
            if src.kind == "campus":
                key = campus_identity(job)
                if key in campus_keys:
                    continue
                campus_keys.add(key)
            old = previous_by_id.get(job["id"]) or archived.get(job["id"], {})
            job["firstSeen"] = old.get("firstSeen") or old.get("checked") or iso(today)
            job["lastSeen"] = job["checked"] if src.kind == "manual-leads" else iso(today)
            job["status"] = "active" if job["verificationStatus"] == "confirmed" else "review"
            current[job["id"]] = job
            archived.pop(job["id"], None)

    for old in previous:
        identifier = old["id"]
        if identifier in current:
            continue
        key = old.get("sourceKey", "manual")
        summary = summaries.get(key, {})
        source = source_lookup.get(key)
        expiry = date_field(old, "deadline")
        checked = date_field(old, "lastSeen") or date_field(old, "checked")
        recently_seen = checked and (today - checked).days <= PENDING_GRACE_DAYS

        cutoff = old.get("deadlineTime")
        if expiry and (expiry < today or
                       (expiry == today and cutoff and now and now.strftime("%H:%M") >= cutoff)):
            reason = "公告截止日已過。"
        elif key == "manual" or old.get("verificationMode") == "manual":
            reason = "原為人工追蹤；尚無近期可驗證的單一招募公告，已移出目前職缺。"
        elif source and source.kind == "himalayas" and duplicate_key(old) in official:
            reason = "已找到雇主的對應公告；是否接受台灣，以雇主公告為準。"
        elif source and source.kind == "campus" and campus_identity(old) in campus_keys:
            reason = "已找到同一招募公告，保留一筆於目前清單。"
        elif source and (summary["status"] != "ok" or source.rolling) and recently_seen:
            note = ("本輪來源未能完整讀取，保留前次結果供確認。"
                    if summary["status"] != "ok" else "已不在本輪近期公告範圍內，是否仍收件請見原公告。")
            current[identifier] = dict(old, status="review", verificationStatus="pending",
                                       verificationNote=note, priority="待查核", priorityType="watch")
            continue
        elif source and (summary["status"] != "ok" or source.rolling):
            reason = "近期未能重新確認；不表示雇主已停止招募。"
        else:
            reason = "本輪未再出現在符合條件的招募清單；可能已下架或條件變更。"
        archived[identifier] = dict(old, status="archived", archived=True,
                                    archivedAt=iso(today), archiveReason=reason,
                                    firstSeen=old.get("firstSeen") or old.get("checked") or iso(today),
                                    lastSeen=old.get("lastSeen") or old.get("checked") or iso(today))

    active = [j for j in current.values() if j["status"] == "active"]
    review = [j for j in current.values() if j["status"] == "review"]
    for jobs in (active, review):
        jobs.sort(key=lambda j: (-j["score"], j["company"], j["title"]))
    archive = sorted(archived.values(), key=lambda j: (j.get("archivedAt", ""), j.get("lastSeen", ""), j.get("score", 0)), reverse=True)
    new_ids = [j["id"] for j in active if j["id"] not in known]
    new_review_count = sum(j["id"] not in known for j in review)
    for key, summary in summaries.items():
        summary["active"] = sum(job.get("sourceKey") == key for job in active)
        summary["review"] = sum(job.get("sourceKey") == key for job in review)
    return active, review, archive, new_ids, new_review_count, list(summaries.values())


def write_json(path: pathlib.Path, value) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=pathlib.Path, default=DATA_DIR, help="Read prior history and write scan data in this directory")
    args = parser.parse_args()
    output = args.output_dir
    paths = {name: output / f"{name}.json" for name in ("jobs", "review", "archive", "scan-meta")}
    previous = load_records(paths["jobs"]) + load_records(paths["review"])
    archive = load_records(paths["archive"])
    prior_meta = json.loads(paths["scan-meta"].read_text(encoding="utf-8")) if paths["scan-meta"].exists() else {}
    now = dt.datetime.now(TAIPEI)
    today = now.date()

    with ThreadPoolExecutor(max_workers=5) as workers:
        scans = list(workers.map(lambda source: refresh_source(source, today, now), SOURCES))
    jobs, review, archive, new_ids, new_review_count, sources = reconcile(previous, archive, scans, today, now)
    recent_ids = [job["id"] for job in jobs if (seen := date_field(job, "firstSeen")) and
                  0 <= (today - seen).days < RECENT_DISCOVERY_DAYS]
    finished = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    automatic = [source for source in sources if not source.get("manual")]
    ok = sum(source["status"] == "ok" for source in automatic)
    errors = sum(source["status"] == "error" for source in automatic)
    examined = sum(source["examined"] for source in automatic)
    scan_status = "error" if errors == len(automatic) else "ok" if ok == len(automatic) else "partial"
    run = {"id": os.environ.get("GITHUB_RUN_ID", ""), "event": os.environ.get("GITHUB_EVENT_NAME", "local"),
           "finished": finished, "scan_date": iso(today), "examined": examined,
           "new": len(new_ids), "status": scan_status}
    history = [run, *(entry for entry in prior_meta.get("history", [])
                      if not run["id"] or entry.get("id") != run["id"])][:12]
    meta = {
        "last_scan_attempt": finished,
        "last_successful_scan": finished if scan_status != "error" else prior_meta.get("last_successful_scan"),
        "interval_days": INTERVAL_DAYS, "scan_status": scan_status,
        "job_count": len(jobs), "review_count": len(review), "archive_count": len(archive),
        "records_examined": examined, "new_count": len(new_ids), "new_ids": new_ids,
        "recent_ids": recent_ids,
        "new_review_count": new_review_count, "location_policy": POLICY_VERSION, "sources": sources,
        "winter_year": winter_year(today),
        "history": history, "run": run,
        "last_schedule": run if run["event"] == "schedule" else prior_meta.get("last_schedule"),
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("jobs", jobs), ("review", review), ("archive", archive), ("scan-meta", meta)):
        write_json(paths[name], value)
    summary = (f"Scanned {examined} postings across {len(automatic)} sources ({ok} complete, {errors} failed). "
               f"Current: {len(jobs)} ({len(new_ids)} first discovered); review: {len(review)}; archive: {len(archive)}.")
    print(summary)
    for source in sources:
        print(f"{source['source']}: {source['status']}; examined {source['examined']}; active {source['active']}; review {source['review']}"
              + (f"; {', '.join(source['issues'])}" if source["issues"] else ""))
    if log := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(log, "a", encoding="utf-8") as stream:
            stream.write(summary + "\n")
    if scan_status != "ok":
        print("::warning::Some recruiting sources could not be checked completely; see the public scan status.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
