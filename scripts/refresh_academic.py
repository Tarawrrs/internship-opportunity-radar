#!/usr/bin/env python3
"""Publish upcoming events and recent research with per-source scan outcomes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
import os
import pathlib
from urllib.error import HTTPError

from academic_sources import EVENT_SOURCES, PAPER_SOURCES, READERS, TOPICS
from job_sources import SOURCE_ERRORS, TAIPEI
from refresh_jobs import DATA_DIR, write_json


def scan(source, today):
    status = {
        "sourceKey": source.key, "source": source.name, "url": source.url,
        "group": "events" if source.institution else "papers", "examined": 0, "matches": 0, "issues": [],
    }
    try:
        items, examined, issues = READERS[source.reader](source, today)
        status.update(status="partial" if issues else "ok", examined=examined, matches=len(items), issues=issues[:6])
        return status, items
    except SOURCE_ERRORS as error:
        issue = f"HTTP {error.code}" if isinstance(error, HTTPError) else type(error).__name__
        status.update(status="error", issues=[issue])
        return status, []


def academic_snapshot(scans, previous, today):
    by_kind = {"events": {}, "papers": {}}
    sources = {info["sourceKey"]: info for info, _ in scans}
    for info, items in scans:
        index = by_kind[info["group"]]
        for item in items:
            key = item["id"]
            if key not in index:
                index[key] = item
            elif info["group"] == "papers":
                index[key]["topics"] = list(dict.fromkeys([*index[key]["topics"], *item["topics"]]))
                index[key]["sourceKeys"].extend(item["sourceKeys"])
    for kind, index in by_kind.items():
        for item in previous.get(kind, []):
            if item["id"] in index:
                continue
            day = dt.date.fromisoformat(item.get("endDate", item["date"]))
            if kind == "events":
                retain = day >= today and sources.get(item["sourceKey"], {}).get("status") in ("error", "partial")
            else:
                retain = 0 <= (today - day).days <= 90
            if retain:
                keys = [item["sourceKey"]] if kind == "events" else item["sourceKeys"]
                stale = all(sources.get(key, {}).get("status") in ("error", "partial") for key in keys)
                index[item["id"]] = dict(item, stale=stale)
    events = list(by_kind["events"].values())
    # Prefer the detailed announcement for sessions also listed on a general timetable.
    identities = {(e["date"], e["title"].casefold()) for e in events if e["sourceKey"] != "sinica-calendar"}
    for item in events:
        if item["sourceKey"] == "sinica-calendar" and (item["date"], item["title"].casefold()) in identities:
            item["duplicate"] = True
        if item["sourceKey"] != "ntu-creta":
            continue
        title = item["title"].split(" (", 1)[0].casefold()
        duplicate = next((e for e in events if e["sourceKey"] == "ntu-econ-seminars" and
                          e["date"] == item["date"] and e["title"].casefold() == title), None)
        if duplicate:
            if not item["time"]:
                item.update(time=duplicate["time"], endTime=duplicate["endTime"])
            item["topics"] = list(dict.fromkeys([*item["topics"], *duplicate["topics"]]))
            duplicate["duplicate"] = True
    events = sorted((e for e in events if not e.get("duplicate")),
                    key=lambda row: (row["date"], row["time"] or "99:99", row["title"]))
    papers = sorted(by_kind["papers"].values(), key=lambda row: (row["date"], row["title"]), reverse=True)[:175]
    return events, papers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=pathlib.Path, default=DATA_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "academic.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    today = dt.datetime.now(TAIPEI).date()
    sources = EVENT_SOURCES + PAPER_SOURCES
    crossref = [source for source in sources if source.reader == "journal"]
    with ThreadPoolExecutor(max_workers=5) as workers:
        requests = {source.key: workers.submit(scan, source, today) for source in sources if source not in crossref}
        # Crossref's public pool accepts one concurrent request per client.
        crossref_results = {source.key: scan(source, today) for source in crossref}
        results = [crossref_results[source.key] if source.key in crossref_results else requests[source.key].result()
                   for source in sources]
    events, papers = academic_snapshot(results, previous, today)
    summaries = [info for info, _ in results]
    finished = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    write_json(path, {
        "events": events, "papers": papers, "sources": summaries, "topics": list(TOPICS),
        "last_scan_attempt": finished,
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
    })
    for info in summaries:
        print(f"{info['source']}: {info['status']}; examined {info['examined']}; matches {info['matches']}"
              + (f"; {', '.join(info['issues'])}" if info["issues"] else ""))
    print(f"Published {len(events)} upcoming events and {len(papers)} recent research items.")
    if log := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(log, "a", encoding="utf-8") as stream:
            stream.write(f"\nAcademic scan: {len(events)} upcoming events, {len(papers)} papers.\n")


if __name__ == "__main__":
    main()
