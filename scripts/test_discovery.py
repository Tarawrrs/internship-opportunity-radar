from datetime import date, datetime, timedelta
from dataclasses import replace
from html import escape
import unittest
from unittest.mock import patch

from job_sources import SOURCES, Posting, deadline_in, parse_taiwanjobs, read_rss, sinica_fields
from refresh_jobs import make_job, reconcile, refresh_source
from winter_rules import winter_details

TODAY = date(2026, 11, 13)
NTU = next(s for s in SOURCES if s.board == "ntu-econ")
APP = next(s for s in SOURCES if s.board == "appier")
REMOTE = next(s for s in SOURCES if s.kind == "himalayas")
PORTCAST = next(s for s in SOURCES if s.board == "portcast")


class DiscoveryTest(unittest.TestCase):
    def test_next_scan_discovers_a_previously_unknown_post(self):
        old = Posting("old", "Data Analyst Intern", "Appier", APP.url, "Taipei", "SQL for product analytics")
        new = replace(old, id="new", title="Product Analytics Intern", posted=TODAY)
        first = make_job(old, APP, TODAY - timedelta(days=1))
        active, review, archive, new_ids, _, _ = reconcile(
            [first], [], [(APP, {"status": "ok"}, [make_job(old, APP, TODAY), make_job(new, APP, TODAY)], set())], TODAY)
        self.assertEqual(new_ids, ["new"])
        self.assertEqual({j["id"] for j in active}, {"new", "old"})
        self.assertEqual(next(j for j in active if j["id"] == "old")["firstSeen"], "2026-11-12")
        self.assertFalse(review or archive)

    def test_stale_manual_and_unreachable_jobs_do_not_count_as_current(self):
        previous = make_job(Posting("app", "Data Analyst Intern", "Appier", APP.url, "Taipei", "SQL"), APP, TODAY - timedelta(days=2))
        manual = {**previous, "id": "nanshan-data-intern", "sourceKey": "manual", "checked": "2026-09-17"}
        active, review, archive, *_ = reconcile([previous, manual], [], [(APP, {"status": "error"}, [], set())], TODAY)
        self.assertEqual(active, [])
        self.assertEqual([job["id"] for job in review], ["app"])
        self.assertEqual(review[0]["checked"], "2026-11-11")
        self.assertEqual(archive[0]["id"], "nanshan-data-intern")
        self.assertEqual(archive[0]["lastSeen"], "2026-09-17")

    def test_rolling_feed_missing_post_is_not_marked_closed(self):
        post = Posting("ntu-old", "兼任研究助理", "台大經濟系", NTU.url, "台北", "實證研究資料分析",
                       posted=TODAY - timedelta(days=3), deadline=TODAY + timedelta(days=2))
        old = make_job(post, NTU, TODAY - timedelta(days=1))
        active, review, archive, *_ = reconcile([old], [], [(NTU, {"status": "ok"}, [], set())], TODAY)
        self.assertEqual((len(active), len(review), len(archive)), (0, 1, 0))
        active, review, archive, *_ = reconcile(review, [], [(NTU, {"status": "ok"}, [], set())], TODAY + timedelta(days=3))
        self.assertEqual((len(active), len(review), len(archive)), (0, 0, 1))
        self.assertIn("截止日", archive[0]["archiveReason"])

    def test_employer_location_overrules_remote_aggregator(self):
        lead = Posting("lead", "Data Analyst Intern", "Portcast", REMOTE.url, "Remote — Taiwan",
                       "Python and SQL", workplace="remote", third_party=True)
        job = make_job(lead, REMOTE, TODAY)
        self.assertEqual(job["verificationStatus"], "pending")
        with patch("job_sources.fetch_json", return_value=[{
            "id": "new-id", "text": "Data Analyst Intern", "hostedUrl": PORTCAST.url + "/new-id",
            "categories": {"commitment": "Intern", "location": "Singapore", "allLocations": ["Singapore", "Bangkok"]},
            "workplaceType": "remote", "descriptionPlain": "Python and SQL",
        }]):
            official = refresh_source(PORTCAST, TODAY)
        self.assertEqual(official[2], [])
        active, review, *_ = reconcile([], [], [official, (REMOTE, {"status": "ok"}, [job], set())], TODAY)
        self.assertEqual((active, review), ([], []))

    def test_rss_uses_actual_work_location_and_filters_past_deadline(self):
        post = "<p>工作地點：臺大社會科學院，或遠距工作</p><p>資料清理與經濟實證；隨到隨審。</p>"
        xml = f"""<rss><channel><title>Test</title><item><title>兼任研究助理</title>
          <link>https://econ.ntu.edu.tw/archives/9876</link><pubDate>Thu, 12 Nov 2026 03:00:00 GMT</pubDate>
          <description>{escape(post)}</description></item></channel></rss>"""
        with patch("job_sources.fetch_text", return_value=xml):
            batch = read_rss(NTU, TODAY)
        self.assertEqual(batch.examined, 1)
        self.assertEqual(make_job(batch.postings[0], NTU, TODAY)["locationKey"], "taipei")
        expired = replace(batch.postings[0], deadline=TODAY - timedelta(days=1))
        self.assertIsNone(make_job(expired, NTU, TODAY))
        self.assertEqual(deadline_in("Application deadline: 31 October; rolling basis", TODAY), date(2026, 10, 31))

    def test_documented_source_fields(self):
        xml = """<DataList><Data><OCCU_DESC（職務名稱）><![CDATA[資料實習]]></OCCU_DESC（職務名稱）>
          <CITYNAME（工作地點）>台北市信義區</CITYNAME（工作地點）><URL_QUERY（職缺資料URL）>https://job.taiwanjobs.gov.tw/</URL_QUERY（職缺資料URL）>
          <COMPNAME（公司名稱）>Example</COMPNAME（公司名稱）></Data></DataList>"""
        self.assertEqual(parse_taiwanjobs(xml)[0]["CITYNAME"], "台北市信義區")
        self.assertEqual(sinica_fields("<span>&#x5DE5;&#x4F5C;&#x5730;&#x9EDE;</span> <p>台北市南港區</p>"), {"工作地點": "台北市南港區"})

    def test_winter_uses_work_dates_instead_of_application_dates(self):
        title = "2027 銀行實習"
        self.assertEqual(winter_details(title, "申請截止：2027/1/1\nStart Date: June 2027", TODAY)[0], "other")
        self.assertEqual(winter_details(title, "實習期間：2026/12/28–2027/2/19", TODAY)[0], "winter-only")
        self.assertEqual(winter_details(title, "實習期間：2027/1/4–2027/2/25", TODAY)[0], "extends")
        self.assertEqual(winter_details(title, "Working Period: 2027/01-2027/06", TODAY)[0], "extends")
        self.assertEqual(winter_details(title, "Working Period: 2027/03-2028/02", TODAY)[0], "other")
        self.assertEqual(winter_details(title, "申請截止：2027/1/1", TODAY)[0], "unknown")

    def test_business_internship_needs_no_research_keywords_and_honors_cutoff(self):
        deadline = date(2026, 11, 23)
        post = Posting("bank-intern", "企業金融實習生", "Test Bank", APP.url, "台北",
                       "實習期間：2027/1/4–2027/6/21", deadline=deadline, deadline_time="12:00")
        before = datetime(2026, 11, 23, 11, 59)
        job = make_job(post, APP, deadline, before)
        self.assertEqual((job["track"], job["winterStatus"]), ("finance", "extends"))
        self.assertIsNone(make_job(post, APP, deadline, before + timedelta(minutes=1)))


if __name__ == "__main__":
    unittest.main()
