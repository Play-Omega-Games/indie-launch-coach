"""Checks for scripts/build_plan.py. Run: python3 -m unittest discover -s tests -v"""
import copy, datetime as dt, json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_plan as bp  # noqa: E402

DATA = bp.load_data(os.path.join(ROOT, 'data'))
TODAY = dt.date(2026, 10, 26)

def persona(name):
    with open(os.path.join(HERE, 'personas', name + '.json'), encoding='utf-8') as f:
        return json.load(f)['profile']

def plan_for(name, today=TODAY, prev=None, **override):
    p = copy.deepcopy(persona(name))
    p.update(override)
    return bp.build(p, today, DATA, prev)

def gate(plan, gid):
    m = [g for g in plan['gates'] if g['id'] == gid]
    return m[0] if m else None

def task(plan, tid):
    m = [t for t in plan['tasks'] if t['id'] == tid]
    return m[0] if m else None

class BusinessDays(unittest.TestCase):
    def test_holidays(self):
        h = bp.holidays(2026)
        self.assertIn(dt.date(2026, 11, 11), h)   # Veterans Day, Wednesday
        self.assertIn(dt.date(2026, 11, 26), h)   # Thanksgiving
        self.assertIn(dt.date(2027, 6, 18), bp.holidays(2027))  # Juneteenth observed (Sat Jun 19)
    def test_add(self):
        self.assertEqual(bp.add_bdays(dt.date(2026, 11, 9), 7), dt.date(2026, 11, 19))
        self.assertEqual(bp.add_bdays(dt.date(2027, 6, 29), -7), dt.date(2027, 6, 17))

class Personas(unittest.TestCase):
    def test_all_build_and_sorted(self):
        for f in sorted(os.listdir(os.path.join(HERE, 'personas'))):
            plan = plan_for(f[:-5])
            self.assertTrue(plan['tasks'], f)
            self.assertTrue(plan['this_week'], f)
            dates = [g['date'] for g in plan['gates'] if g['date']]
            self.assertEqual(dates, sorted(dates), f)

    def test_a_exact_8_months_no_page(self):
        p = plan_for('a_steam_8_months_no_page')
        self.assertEqual(p['launch_date'], '2027-06-29')
        self.assertEqual(gate(p, 'steam_store_submit')['date'], '2026-11-09')
        self.assertEqual(gate(p, 'steam_coming_soon')['date'], '2026-11-19')
        self.assertEqual(gate(p, 'steam_coming_soon')['latest'], '2027-06-15')
        self.assertEqual(gate(p, 'steam_date_lock')['date'], '2027-06-15')
        self.assertEqual(gate(p, 'steam_build_submit')['date'], '2027-06-17')
        self.assertEqual(gate(p, 'steam_build_submit')['recommended'], '2027-06-08')
        self.assertEqual(gate(p, 'steam_keys_wait')['date'], '2027-05-11')
        self.assertEqual(gate(p, 'steam_demo_notice')['date'], '2027-05-18')
        self.assertEqual(gate(p, 'steam_discount_cooldown')['date'], '2027-07-29')
        self.assertIsNone(gate(p, 'steam_first_seasonal_sale')['date'])  # Autumn 2027 not announced
        self.assertEqual([f['id'] for f in p['festival_options']], ['nextfest_feb_2027', 'nextfest_jun_2027'])
        self.assertEqual(p['phase'], 'grow')
        self.assertFalse(p['warnings'])

    def test_b_month_page_live_festival(self):
        p = plan_for('b_month_known_page_live_demo')
        self.assertEqual(p['launch_date'], '2027-05-17')  # 15th is a Saturday
        self.assertEqual(p['launch_display'], 'around May 2027')
        self.assertEqual(gate(p, 'steam_coming_soon')['status'], 'done')
        self.assertEqual(gate(p, 'steam_build_submit')['date'], '2027-05-06')
        self.assertEqual(gate(p, 'nextfest_registration_deadline')['date'], '2027-01-10')
        self.assertEqual(gate(p, 'nextfest_all_items_due')['date'], '2027-02-01')
        # demo date: the business day before the festival (Sun Feb 21 rolls back to Fri Feb 19)
        self.assertEqual(p['demo_date'], '2027-02-19')
        self.assertEqual(gate(p, 'steam_demo_notice')['date'], '2027-03-05')
        self.assertEqual(task(p, 'sc_register')['due'], '2026-12-31')  # Sun Jan 3 rolls back past New Year's Day
        self.assertIn('Summer Sale 2027', gate(p, 'steam_first_seasonal_sale')['title'])
        self.assertIsNone(gate(p, 'steam_keys_wait'))
        self.assertIsNotNone(task(p, 'gr_paid_test'))

    def test_c_unknown_date(self):
        p = plan_for('c_date_unknown_prototype')
        self.assertIsNone(p['launch_date'])
        self.assertEqual(p['phase'], 'groundwork')
        self.assertIsNone(gate(p, 'steam_coming_soon')['date'])
        self.assertTrue(all(t['due'] is None for t in p['tasks'] if t['phase'] in ('final_approach', 'launch_window')))
        self.assertIsNotNone(task(p, 'gw_settle_look'))
        self.assertIsNotNone(task(p, 'gw_itch_account'))

    def test_d_launched(self):
        p = plan_for('d_launched_10_days_ago')
        self.assertEqual(p['phase'], 'first_month')
        self.assertEqual(gate(p, 'steam_discount_cooldown')['date'], '2026-11-15')
        self.assertIn('Winter Sale 2026', gate(p, 'steam_first_seasonal_sale')['title'])
        self.assertFalse([t for t in p['tasks'] if t['phase'] in ('groundwork', 'reveal', 'grow', 'showcase', 'final_approach')])
        self.assertFalse([t for t in p['tasks'] if t['status'] == 'catch_up'])
        self.assertEqual(p['festival_options'], [])

    def test_e_short_runway(self):
        p = plan_for('e_five_weeks_no_page')
        self.assertTrue(p['sprint'])
        self.assertEqual([w['id'] for w in p['warnings']], ['steam_runway_too_short'])
        self.assertEqual(p['festival_options'], [])
        self.assertTrue(p['notes'])
        self.assertEqual(task(p, 'gr_playtest')['status'], 'skipped_by_plan')
        # same date with art ready becomes feasible
        q = plan_for('e_five_weeks_no_page', assets=['capsule', 'screenshots'])
        self.assertFalse(q['warnings'])
        self.assertEqual(gate(q, 'steam_coming_soon')['date'], '2026-11-04')

    def test_f_multi_platform(self):
        p = plan_for('f_multi_platform_staggered')
        self.assertEqual(gate(p, 'ios_preorder_window')['date'], '2027-03-18')
        self.assertEqual(gate(p, 'console_switch')['status'], 'waiting on platform')
        self.assertEqual(p['festival'], 'nextfest_jun_2027')
        self.assertEqual(task(p, 'rv_short_desc')['status'], 'done')   # page built
        self.assertEqual(task(p, 'rv_submit_cs')['status'], 'open')  # first build: nothing overdue on day one
        self.assertIsNotNone(task(p, 'gw_console_apply'))
        self.assertIsNone(gate(p, 'steam_keys_wait'))

    def test_g_essentials(self):
        p = plan_for('g_solo_3h_no_budget')
        self.assertTrue(p['essentials_track'])
        self.assertEqual(len(p['this_week']), 3)
        hours = sum(t['effort_hours'] for t in p['tasks'] if t['id'] in p['this_week'])
        self.assertLessEqual(hours, 3.6)  # 3 hour budget, topped up by at most a fifth to reach 3 tasks
        self.assertIsNone(task(p, 'gr_paid_test'))
        self.assertIsNone(task(p, 'gr_devlog'))

    def test_h_early_access(self):
        p = plan_for('h_early_access')
        self.assertIsNotNone(task(p, 'gr_ea_questionnaire'))
        self.assertEqual(task(p, 'lt_ea_graduation')['due'], '2027-10-06')
        self.assertEqual(p['festival'], 'nextfest_feb_2027')
        self.assertEqual(gate(p, 'steam_date_lock')['date'], '2027-02-24')

    def test_i_free(self):
        p = plan_for('i_free_to_play')
        self.assertIsNone(gate(p, 'steam_launch_discount'))
        self.assertIsNone(gate(p, 'steam_discount_cooldown'))
        self.assertIsNone(task(p, 'fa_price'))
        self.assertEqual(gate(p, 'android_prereg_window')['date'], '2027-05-05')
        self.assertIsNotNone(task(p, 'gr_android_testing'))

    def test_j_publisher(self):
        p = plan_for('j_publisher_multi')
        self.assertEqual(p['launch_date'], '2027-11-15')
        self.assertEqual(p['launch_display'], 'around Q4 2027')
        self.assertEqual(task(p, 'fa_build_submit')['owner'], 'confirm with publisher')
        self.assertEqual(gate(p, 'console_playstation')['date'], '2027-11-16')
        self.assertEqual(gate(p, 'console_xbox')['status'], 'waiting on platform')
        self.assertEqual(gate(p, 'epic_onboarding')['date'], '2027-09-01')

class NextFestChoice(unittest.TestCase):
    def ids(self, launch):
        p = plan_for('b_month_known_page_live_demo', date_precision='exact', launch_date=launch, festival='ask')
        return [f['id'] for f in p['festival_options']]
    def test_choices(self):
        self.assertEqual(self.ids('2027-02-10'), [])
        self.assertEqual(self.ids('2027-04-15'), ['nextfest_feb_2027'])
        self.assertEqual(self.ids('2027-08-01'), ['nextfest_feb_2027', 'nextfest_jun_2027'])
    def test_after_deadline(self):
        p = plan_for('b_month_known_page_live_demo', today=dt.date(2027, 1, 11), festival='ask')
        self.assertEqual(p['festival_options'], [])

class DateMoves(unittest.TestCase):
    def test_move_plus_minus_six_weeks(self):
        base = plan_for('a_steam_8_months_no_page')
        for t in base['tasks']:
            if t['id'] in ('gw_hook', 'gw_player'):
                t['status'] = 'done'
        for weeks in (6, -6):
            new = (dt.date(2027, 6, 29) + dt.timedelta(weeks=weeks)).isoformat()
            p = plan_for('a_steam_8_months_no_page', prev=base, launch_date=new)
            self.assertEqual(task(p, 'gw_hook')['status'], 'done')
            self.assertEqual(task(p, 'gw_player')['status'], 'done')
            self.assertEqual(p['changes'][-1], {'on': '2026-10-26', 'from': '2027-06-29', 'to': new})
            lock = dt.date.fromisoformat(new) - dt.timedelta(days=14)
            self.assertEqual(gate(p, 'steam_date_lock')['date'], lock.isoformat())
        # -6 weeks drops the June festival option
        p = plan_for('a_steam_8_months_no_page', prev=base, launch_date='2027-05-18', festival='nextfest_jun_2027')
        self.assertIn('festival_no_longer_fits', [w['id'] for w in p['warnings']])

    def test_steam_lock(self):
        today = dt.date(2027, 6, 20)
        base = plan_for('a_steam_8_months_no_page', today=today)
        p = plan_for('a_steam_8_months_no_page', today=today, prev=base, launch_date='2027-07-20')
        self.assertIn('steam_date_locked', [w['id'] for w in p['warnings']])


class Regressions(unittest.TestCase):
    def test_coming_soon_target_does_not_slide(self):
        p0 = plan_for('a_steam_8_months_no_page')
        p1 = plan_for('a_steam_8_months_no_page', today=TODAY + dt.timedelta(days=7), prev=p0)
        self.assertEqual(gate(p1, 'steam_coming_soon')['date'], gate(p0, 'steam_coming_soon')['date'])
        self.assertEqual(task(p1, 'gw_hook')['due'], task(p0, 'gw_hook')['due'])
    def test_registered_festival_kept_after_registration_closes(self):
        p0 = plan_for('b_month_known_page_live_demo')
        for t in p0['tasks']:
            if t['id'] == 'sc_register':
                t['status'] = 'done'
        p1 = plan_for('b_month_known_page_live_demo', today=dt.date(2027, 1, 20), prev=p0)
        self.assertEqual(p1['festival'], 'nextfest_feb_2027')
        self.assertFalse([w for w in p1['warnings'] if w['id'] == 'festival_no_longer_fits'])
    def test_setup_answers_close_tasks(self):
        p = plan_for('b_month_known_page_live_demo')
        self.assertEqual(task(p, 'gw_home_base')['status'], 'done')
        self.assertEqual(task(p, 'gw_channels')['status'], 'done')

K = 'k_page_public_demo_planned_festival'
SETUP = dt.date(2026, 10, 30)  # a Friday

def mark_done(plan, ids):
    for t in plan['tasks']:
        if t['id'] in ids:
            t['status'] = 'done'
    return plan

class LiveTestRegressions(unittest.TestCase):
    """Bugs from the Oct 30, 2026 live self-test."""
    def test_due_dates_are_business_days(self):
        offsets = {t['id']: t['offset_days'] for t in DATA['tasks']['tasks']}
        names = [f[:-5] for f in sorted(os.listdir(os.path.join(HERE, 'personas')))]
        for name in names:
            for today in (TODAY, SETUP, dt.date(2026, 11, 7)):
                p = plan_for(name, today=today)
                for t in p['tasks']:
                    if t['due'] and offsets[t['id']] != 0:
                        self.assertTrue(bp.is_bday(dt.date.fromisoformat(t['due'])), (name, today, t['id'], t['due']))
    def test_rolled_dates_stay_before_their_deadline(self):
        p = plan_for(K, today=SETUP)
        self.assertLess(task(p, 'sc_register')['due'], gate(p, 'nextfest_registration_deadline')['date'])
        self.assertLess(task(p, 'sc_demo_live')['due'], gate(p, 'nextfest_start')['date'])
        self.assertEqual(task(p, 'rv_utm')['due'], '2026-11-02')  # Sat Oct 31 moves on to Monday
    def test_day_one_grace_survives_first_rebuild(self):
        p0 = plan_for(K, today=SETUP)
        self.assertFalse([t for t in p0['tasks'] if t['status'] == 'catch_up'])
        graced = [t['id'] for t in p0['tasks'] if t.get('day_one_grace')]
        self.assertIn('gr_playtest', graced)
        p1 = plan_for(K, today=dt.date(2026, 11, 2), prev=p0)
        self.assertFalse([t for t in p1['tasks'] if t['status'] == 'catch_up'])
        for tid in graced:
            self.assertEqual(task(p1, tid)['due'], task(p0, tid)['due'], tid)
        # the grace is one-off: still not done a week later means catch up
        p2 = plan_for(K, today=dt.date(2026, 11, 9), prev=p1)
        self.assertEqual(task(p2, 'gr_playtest')['status'], 'catch_up')
    def test_public_page_tasks_do_not_slide(self):
        p0 = plan_for(K, today=SETUP)
        p1 = plan_for(K, today=dt.date(2026, 11, 9), prev=p0)
        self.assertEqual(p1['page_public_on'], '2026-10-30')
        self.assertEqual(task(p1, 'gr_rhythm')['due'], task(p0, 'gr_rhythm')['due'])
        # a page that goes public later is dated from the check-in that reported it
        a0 = plan_for('a_steam_8_months_no_page')
        a1 = plan_for('a_steam_8_months_no_page', today=dt.date(2026, 12, 7), prev=a0, store_page='public')
        self.assertEqual(a1['page_public_on'], '2026-12-07')
        self.assertEqual(task(a1, 'gr_rhythm')['due'], '2026-12-14')
    def test_this_week_has_at_least_three(self):
        p0 = plan_for(K, today=SETUP)
        # everything due this year is done except one 4 hour task, now in catch up
        p0 = mark_done(p0, [t['id'] for t in p0['tasks'] if t['id'] != 'gr_playtest' and t['due'] and t['due'] <= '2026-12-31'])
        p1 = plan_for(K, today=dt.date(2026, 11, 9), prev=p0)
        self.assertIn('gr_playtest', p1['this_week'])
        self.assertGreaterEqual(len(p1['this_week']), 3)
        hours = sum(t['effort_hours'] for t in p1['tasks'] if t['id'] in p1['this_week'])
        self.assertLessEqual(hours, p1['hours_budget'] + 1)
        for name in [f[:-5] for f in sorted(os.listdir(os.path.join(HERE, 'personas')))]:
            p = plan_for(name)
            open_n = len([t for t in p['tasks'] if t['status'] in ('open', 'catch_up')])
            self.assertGreaterEqual(len(p['this_week']), min(3, open_n), name)
    def test_public_page_needs_evidence_for_trailer_and_reveal(self):
        p = plan_for(K, today=SETUP)
        self.assertEqual(task(p, 'rv_trailer1')['status'], 'open')    # no trailer in assets
        self.assertEqual(task(p, 'rv_announce')['status'], 'open')
        self.assertEqual(task(p, 'rv_profiles')['status'], 'open')
        self.assertEqual(task(p, 'rv_capsules')['status'], 'done')    # Steam needs it for a public page
        self.assertEqual(task(p, 'rv_submit_cs')['status'], 'done')
        q = plan_for(K, today=SETUP, assets=['capsule', 'screenshots', 'trailer'])
        self.assertEqual(task(q, 'rv_trailer1')['status'], 'done')
    def test_budget_answer_closes_budget_task(self):
        self.assertEqual(task(plan_for(K, today=SETUP), 'gw_budget')['status'], 'done')
        self.assertEqual(task(plan_for(K, today=SETUP, budget='private'), 'gw_budget')['status'], 'open')
    def test_creator_demo_invites_after_demo_is_public(self):
        p = plan_for(K, today=SETUP)
        t = task(p, 'sc_creator_demo')
        self.assertGreaterEqual(t['due'], p['demo_date'])
        self.assertGreaterEqual(t['due'], task(p, 'dm_demo_release')['due'])
        self.assertIn('no keys are needed', t['why'])
        # a festival with no demo date yet still dates it before the festival
        q = plan_for(K, today=SETUP, demo='none')
        self.assertEqual(task(q, 'sc_creator_demo')['due'], '2027-02-19')

if __name__ == '__main__':
    unittest.main()
