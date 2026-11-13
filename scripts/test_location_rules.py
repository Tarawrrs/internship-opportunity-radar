import unittest

from location_rules import classify_location


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
            ("Taiwan, Taipei / Singapore", "", "remote", "eligible", "remote"),
            ("Taiwan, Taipei", "The role requires travel abroad twice per year.", "remote", "excluded", "outside"),
            ("Remote worldwide (Canada)", "", "remote", "excluded", "outside"),
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

if __name__ == '__main__':
    unittest.main()
