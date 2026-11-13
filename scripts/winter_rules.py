"""Read work dates independently from application dates and announcement dates."""

import datetime as dt
import re

from job_sources import date_value

DATE = r"(?:20\d\d|1\d\d)\s*[-/.年]\s*\d{1,2}\s*[-/.月]\s*\d{1,2}(?!\d)\s*(?:日)?"
MONTH = r"(?:20\d\d|1\d\d)(?:\s*年\s*\d{1,2}\s*月|\s*[-/.]\s*\d{1,2}(?!\d))"
WORK_PERIOD = r"(?:(?:實習|工讀)(?:期間|時程|期程|時間|日期|起迄|起訖)|起始日期|到職日(?:期)?|起聘日(?:期)?|工作期間|start date|(?:internship|working) (?:dates|period|duration))"
WINTER = re.compile(r"寒假|冬季實習|\bwinter (?:internship|intern|program(?:me)?|break)\b", re.I)
# NTU academic calendar for 115–2. For unpublished calendars use January–February.
NTU_WINTERS = {2027: (dt.date(2026, 12, 28), dt.date(2027, 2, 19))}


def winter_year(today: dt.date) -> int:
    return today.year if today.month <= 2 else today.year + 1


def period_date(value: str) -> dt.date | None:
    value = value.strip()
    if re.fullmatch(MONTH, value):
        return date_value(value + ("1日" if value.endswith("月") else "/01"))
    return date_value(value)


def winter_details(title: str, description: str, today: dt.date) -> tuple[str, str]:
    year = winter_year(today)
    first, last = NTU_WINTERS.get(year, (dt.date(year, 1, 1), dt.date(year, 3, 1) - dt.timedelta(days=1)))
    # Select a work-period field. A December application deadline and a January interview
    # do not establish a January start. Stop at the end of the field.
    for field in re.findall(rf"{WORK_PERIOD}[ \t]*[：:｜|為 \t]*(?:\n[ \t]*)?([^\n]{{1,160}})", description, re.I):
        field = re.split(r"截止|申請期間|招募期間|投遞期間|application deadline", field, maxsplit=1, flags=re.I)[0]
        field = re.split(r"【(?:工作|實習)地點|\s[📍💼]", field, maxsplit=1)[0].strip()
        tokens = re.findall(rf"{DATE}|{MONTH}", field)
        dates = [d for part in tokens if (d := period_date(part))]
        if not dates:
            month = re.match(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d\d)", field, re.I)
            if month:
                dates = [dt.datetime.strptime(month[0], "%B %Y").date()]
        if not dates:
            continue
        start, end = dates[0], dates[-1]
        if not first <= start <= last:
            return "other", field.strip()
        if tokens and re.fullmatch(MONTH, tokens[0].strip()) and start.month == last.month and last.day < 28:
            return "flexible", field.strip()
        if end > start:
            status = "extends" if end > last or (end.month == last.month and re.search(MONTH + r"\s*$", field)) else "winter-only"
            return status, field.strip()
        return "flexible", field.strip()

    if re.search(r"暑期實習|暑假實習|summer (?:internship|intern|analyst|associate)", title, re.I):
        return "other", ""
    if WINTER.search(title):
        # Campus circulars often combine a winter program with semester-length roles.
        return "flexible", ""
    return "unknown", ""
