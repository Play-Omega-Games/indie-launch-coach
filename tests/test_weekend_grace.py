"""Regression: a weekend setup must not leave weekend-rolled tasks to fall into catch up on the first rebuild.
Run from the repo root: python3 -m unittest tests/test_weekend_grace.py (copy into tests/)."""
import copy, datetime as dt, json, os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_plan as bp
DATA = bp.load_data(os.path.join(ROOT, 'data'))
def persona(n):
    return json.load(open(os.path.join(HERE, 'personas', n + '.json')))['profile']
class WeekendSetup(unittest.TestCase):
    def test_saturday_setup_no_catch_up_monday(self):
        p = persona('k_page_public_demo_planned_festival')
        day0 = bp.build(copy.deepcopy(p), dt.date(2026, 10, 31), DATA, None)
        mon = bp.build(copy.deepcopy(p), dt.date(2026, 11, 2), DATA, day0)
        self.assertEqual([t['id'] for t in mon['tasks'] if t['status'] == 'catch_up'], [])
if __name__ == '__main__':
    unittest.main()
