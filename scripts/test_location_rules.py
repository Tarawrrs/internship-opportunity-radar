import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from location_rules import classify_location
import refresh_jobs as refresh


class LocationRulesTest(unittest.TestCase):
    def test_work_location_gate(self):
        cases = [
            ("Taipei, Taiwan", "", "hybrid", "eligible", "taipei"),
            ("台北市松山區", "", "onsite", "eligible", "taipei"),
            ("Taiwan", "Our company has an office in Taipei.", "", "excluded", "outside"),
            ("New Taipei City, Taiwan", "", "", "excluded", "outside"),
            ("Greater Taipei", "", "", "excluded", "outside"),
            ("新北市", "", "", "excluded", "outside"),
            ("Singapore", "We collaborate with remote teams worldwide.", "", "excluded", "outside"),
            ("Taiwan", "", "remote", "eligible", "remote"),
            ("Remote - Worldwide", "", "", "eligible", "remote"),
            ("Home based - Worldwide", "", "", "eligible", "remote"),
            ("Remote", "Work from anywhere.", "", "eligible", "remote"),
            ("Remote", "We have customers worldwide.", "", "review", "remote-review"),
            ("Remote - APAC", "", "", "review", "remote-review"),
            ("Remote - US", "", "", "excluded", "outside"),
            ("Remote - US / Canada", "", "", "excluded", "outside"),
            ("Remote - EMEA", "", "", "excluded", "outside"),
            ("Singapore", "", "remote", "excluded", "outside"),
            ("Remote - Worldwide", "Must be based in the United States.", "", "excluded", "outside"),
            ("Remote - Worldwide", "You must be authorized to work in Canada.", "", "excluded", "outside"),
            ("Remote - Worldwide", "US only.", "", "excluded", "outside"),
            ("Remote - Worldwide", "Not available in Taiwan.", "", "excluded", "outside"),
            ("Remote - Worldwide", "Travel internationally twice per year is required.", "", "excluded", "outside"),
            ("Remote - Worldwide", "Required to attend in-person meetings abroad.", "", "excluded", "outside"),
            ("Taiwan", "", "hybrid", "excluded", "outside"),
            ("Remote - Worldwide", "This role is not remote.", "", "excluded", "outside"),
        ]
        for location, description, workplace, disposition, key in cases:
            with self.subTest(location=location, description=description):
                decision = classify_location(location, description, workplace)
                self.assertEqual((decision['locationDisposition'], decision['locationKey']), (disposition, key))

    def test_archive_migration_and_source_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            foreign = {'id': 'gh-old-1', 'sourceKey': 'greenhouse:old', 'title': 'Data Analyst Intern',
                       'company': 'Old', 'location': 'Singapore', 'locationKey': 'sg', 'score': 95,
                       'checked': '2026-09-17', 'firstSeen': '2026-09-17'}
            taipei = dict(foreign, id='gh-old-2', location='Taipei', locationKey='tw')
            with patch.multiple(refresh, DATA_DIR=root, JOBS_PATH=root/'jobs.json',
                                REVIEW_PATH=root/'review.json', ARCHIVE_PATH=root/'archive.json',
                                META_PATH=root/'meta.json', MANUAL_JOBS=[],
                                SOURCES=[('greenhouse', 'old', 'Old', 'unused'),
                                         ('greenhouse', 'new', 'New', 'unused')]):
                (root/'jobs.json').write_text(json.dumps([foreign, taipei]))
                remote = dict(foreign, id='gh-new-3', sourceKey='greenhouse:new', company='New', location='Remote')
                remote.update(classify_location('Remote'))
                with patch.object(refresh, 'greenhouse_jobs', side_effect=[TimeoutError(), [remote]]), \
                     patch('sys.argv', ['refresh_jobs.py', '--force']), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(refresh.main(), 0)
                active = json.loads((root/'jobs.json').read_text())
                archive = json.loads((root/'archive.json').read_text())
                review = json.loads((root/'review.json').read_text())
                self.assertEqual([j['id'] for j in active], ['gh-old-2'])
                self.assertEqual([j['id'] for j in review], ['gh-new-3'])
                self.assertEqual([j['id'] for j in archive], ['gh-old-1'])
                self.assertIn('不表示職缺已下架', archive[0]['archiveReason'])
                self.assertEqual(archive[0]['firstSeen'], '2026-09-17')
                self.assertEqual(active[0]['lastSeen'], '2026-09-17')

    def test_manual_dates_are_not_falsely_refreshed(self):
        jobs = refresh.active_manual_jobs(dt.date(2026, 9, 19), '2026-09-19')
        self.assertTrue(jobs)
        self.assertTrue(all(j['checked'] == '2026-09-17' for j in jobs))
        self.assertTrue(all(j['locationKey'] == 'taipei' for j in jobs))


if __name__ == '__main__':
    unittest.main()
