#!/usr/bin/env python3
"""Build a dated launch plan from an owner's answers.

Usage:
  python3 build_plan.py --profile profile.json [--today YYYY-MM-DD] [--prev plan.json]
                        [--data DIR_OR_URL] [--out plan.json] [--summary]

--data defaults to ../data next to this script. It can also be the raw GitHub base
https://raw.githubusercontent.com/Play-Omega-Games/indie-launch-coach/main/data
No third-party packages needed.
"""
import argparse, datetime as dt, json, os, sys, urllib.request

D = dt.date
ONE = dt.timedelta(days=1)

# ---------- data loading ----------
def load_json(base, name):
    if base.startswith('http'):
        with urllib.request.urlopen(base.rstrip('/') + '/' + name, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    with open(os.path.join(base, name), encoding='utf-8') as f:
        return json.load(f)

def load_data(base):
    return {k: load_json(base, k + '.json') for k in
            ('tasks', 'gates', 'phases', 'platforms', 'events_snapshot', 'sources')}

def pd(s):
    return D.fromisoformat(s) if s else None

# ---------- business days (Mon to Fri, US federal holidays skipped) ----------
def nth_weekday(y, m, wd, n):
    d = D(y, m, 1)
    while d.weekday() != wd:
        d += ONE
    return d + dt.timedelta(weeks=n - 1)

def last_weekday(y, m, wd):
    d = D(y, m + 1, 1) - ONE if m < 12 else D(y, 12, 31)
    while d.weekday() != wd:
        d -= ONE
    return d

def observed(d):
    if d.weekday() == 5:
        return d - ONE
    if d.weekday() == 6:
        return d + ONE
    return d

_HOL = {}
def holidays(y):
    if y not in _HOL:
        h = {observed(D(y, 1, 1)), nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3),
             last_weekday(y, 5, 0), observed(D(y, 6, 19)), observed(D(y, 7, 4)),
             nth_weekday(y, 9, 0, 1), nth_weekday(y, 10, 0, 2), observed(D(y, 11, 11)),
             nth_weekday(y, 11, 3, 4), observed(D(y, 12, 25))}
        # New Year's Day of next year observed on Dec 31 when Jan 1 is a Saturday
        nxt = D(y + 1, 1, 1)
        if nxt.weekday() == 5:
            h.add(D(y, 12, 31))
        _HOL[y] = h
    return _HOL[y]

def is_bday(d):
    return d.weekday() < 5 and d not in holidays(d.year)

def add_bdays(d, n):
    step = ONE if n >= 0 else -ONE
    left = abs(n)
    while left:
        d += step
        if is_bday(d):
            left -= 1
    return d

def next_bday(d):
    while not is_bday(d):
        d += ONE
    return d

def prev_bday(d):
    while not is_bday(d):
        d -= ONE
    return d

def roll_due(due, offset, today):
    """Move a task due date off weekends and US federal holidays.
    Work due before its anchor moves earlier, so it still lands before the anchor;
    work due after its anchor moves later, so it never comes before the event.
    A task on the anchor day itself keeps that day (it is the event)."""
    if due is None or offset == 0 or is_bday(due):
        return due
    if offset < 0:
        back = prev_bday(due)
        # do not pull a not-yet-due task into the past; move it forward instead
        return back if (back >= today or due < today) else next_bday(due)
    return next_bday(due)

def next_weekday(d):
    while d.weekday() >= 5:
        d += ONE
    return d

# ---------- helpers ----------
CONSOLES = {'switch', 'playstation', 'xbox'}
MOBILE = {'ios', 'android'}

def store_tokens(stores):
    s = set(stores)
    tok = set(s) | {'all'}
    if s & CONSOLES:
        tok.add('console')
    if s & MOBILE:
        tok.add('mobile')
    return tok

def working_date(p):
    prec = p.get('date_precision', 'unknown')
    if p.get('stage') == 'launched':
        return pd(p.get('launched_on')), 'exact'
    if prec == 'exact':
        return pd(p['launch_date']), 'exact'
    if prec == 'month':
        y, m = map(int, p['launch_month'].split('-'))
        return next_weekday(D(y, m, 15)), 'month'
    if prec == 'quarter':
        y, q = p['launch_quarter'].split('-Q')
        return next_weekday(D(int(y), (int(q) - 1) * 3 + 2, 15)), 'quarter'
    return None, 'unknown'

def display_date(L, prec):
    if not L:
        return 'To decide'
    if prec == 'month':
        return 'around ' + L.strftime('%B %Y')
    if prec == 'quarter':
        return 'around Q%d %d' % ((L.month - 1) // 3 + 1, L.year)
    return L.strftime('%a %b %d, %Y').replace(' 0', ' ')

# ---------- main build ----------
def build(profile, today, data, prev=None):
    p = profile
    stores = p.get('stores', [])
    tok = store_tokens(stores)
    steam = 'steam' in stores
    launched = p.get('stage') == 'launched'
    L, prec = working_date(p)
    assets = set(p.get('assets', []))
    free = p.get('release_type') == 'free'
    ea = p.get('release_type') == 'ea'
    budget_paid = p.get('budget') in ('lt500', '500to2500', 'gt2500')
    hours_key = p.get('hours', '3to6')
    ph = data['phases']
    hours_budget = ph['hours_budget'][hours_key]
    max_tasks = ph['max_tasks_per_week'][hours_key]
    essentials = hours_key == 'lt3'
    publisher = p.get('team') == 'publisher'
    snap = data['events_snapshot']
    warnings, gates, notes = [], [], []
    dtl = (L - today).days if L else None
    page_public = p.get('store_page') == 'public' or launched

    # ---- Coming Soon anchor (Steam) ----
    CS = None
    cs_info = {}
    if steam and not page_public:
        ready = {'capsule', 'screenshots'} <= assets
        prep = 0 if ready else 14  # guideline: two weeks to make missing art
        submit_earliest = next_bday(today + dt.timedelta(days=prep))
        cs_earliest = add_bdays(submit_earliest, 7)
        cs_info = {'earliest': cs_earliest, 'prep_days': prep}
        if p.get('stage') == 'idea' and not L:
            CS = None
        elif L:
            cs_latest = L - dt.timedelta(days=14)
            CS = max(cs_earliest, L - dt.timedelta(days=365))
            cs_info['latest'] = cs_latest
            if cs_earliest > cs_latest:
                warnings.append({'id': 'steam_runway_too_short', 'text':
                    'Steam needs your page public as Coming Soon for at least two weeks before release, and asks for 7 business days to review it. '
                    'The earliest your page could be public is %s, but it needs to be public by %s for this date. '
                    'Options: pick a later launch date, or keep the date and run the short plan.' % (display_date(cs_earliest, 'exact'), display_date(cs_latest, 'exact')),
                    'source': 'steam_coming_soon'})
                CS = cs_earliest
        else:
            CS = cs_earliest
        # Keep the Coming Soon target from the last build while it is still reachable,
        # so weekly rebuilds do not quietly slide it forward.
        same_date = prev and prev.get('launch_date') == (L.isoformat() if L else None)
        pcs = pd(prev.get('coming_soon_target')) if prev else None
        if same_date and pcs and CS and pcs < CS:
            if add_bdays(pcs, -7) >= today:
                CS = pcs
            else:
                warnings.append({'id': 'coming_soon_slipped', 'text':
                    'The store page submission date in your plan (%s) has passed. If you already submitted it, tell me and I will mark it done. '
                    'Otherwise the earliest your page can be public is now %s.' % (display_date(add_bdays(pcs, -7), 'exact'), display_date(CS, 'exact')),
                    'source': 'steam_coming_soon'})

    # ---- Festival (Steam Next Fest) ----
    fest_options = []
    if steam and not launched:
        for e in snap['nextfest']:
            reg = pd(e.get('registration_deadline'))
            if not reg:
                continue
            start, end, allitems = pd(e['start']), pd(e['end']), pd(e['all_items_due'])
            if reg < today or allitems < today:
                continue
            if L and not (L > end):
                continue
            cs_ready = page_public or (cs_info.get('earliest') and cs_info['earliest'] <= reg)
            if not cs_ready:
                continue
            fest_options.append({'id': e['id'], 'name': e['name'], 'start': e['start'], 'end': e['end'],
                                 'registration_deadline': e['registration_deadline'],
                                 'press_preview_submit': e.get('press_preview_submit'),
                                 'all_items_due': e['all_items_due'],
                                 'needs_demo_note': p.get('demo') == 'none'})
    chosen = None
    fchoice = p.get('festival', 'ask')
    if fchoice not in ('ask', 'none', None):
        match = [f for f in fest_options if f['id'] == fchoice]
        if match:
            chosen = match[0]
        else:
            # Keep an edition the owner already registered for after its registration closes.
            ed = [x for x in snap['nextfest'] if x['id'] == fchoice]
            registered = bool(prev) and any(t.get('id') == 'sc_register' and t.get('status') == 'done' for t in prev.get('tasks', []))
            if ed and registered and (not L or L > pd(ed[0]['end'])):
                e0 = ed[0]
                chosen = {'id': e0['id'], 'name': e0['name'], 'start': e0['start'], 'end': e0['end'],
                          'registration_deadline': e0.get('registration_deadline'),
                          'press_preview_submit': e0.get('press_preview_submit'),
                          'all_items_due': e0.get('all_items_due'), 'needs_demo_note': p.get('demo') == 'none'}
        if not chosen:
            warnings.append({'id': 'festival_no_longer_fits', 'text':
                'The festival you chose no longer fits this plan (it must end before your launch, its deadlines must still be open, and your page must be public by registration). '
                'Pick another from the options, or skip festivals for now.', 'source': 'steam_nextfest'})
    if steam and L and not launched and not fest_options and not chosen:
        notes.append('No Steam Next Fest edition fits before this launch date. The plan leans on themed events, your demo notice and personal outreach.')
    if chosen and CS and not page_public:
        reg = pd(chosen['registration_deadline'])
        if CS > reg:
            CS = max(cs_info['earliest'], min(CS, reg))
    F = pd(chosen['start']) if chosen else None
    fest_dates = {}
    if chosen:
        e = [x for x in snap['nextfest'] if x['id'] == chosen['id']][0]
        fest_dates = {'F': pd(e['start']), 'F_REG': pd(e['registration_deadline']), 'F_ALL': pd(e['all_items_due']),
                      'F_PRESS': pd(e.get('press_preview_submit'))}

    # ---- Demo anchor ----
    Dm = None
    demo = p.get('demo', 'none')
    if demo == 'planning':
        if pd(p.get('demo_date')):
            Dm = pd(p['demo_date'])
        elif F:
            Dm = prev_bday(F - ONE)
        elif L and not launched:
            Dm = prev_bday(L - dt.timedelta(days=56))
    elif demo == 'have' and pd(p.get('demo_date')) and pd(p['demo_date']) >= today:
        Dm = pd(p['demo_date'])

    L1 = pd(p.get('ea_1_0_date')) if ea else None
    started = pd(prev.get('started_on') or prev.get('built_on')) if prev else today
    # A public page is dated from the first build that saw it public (setup, or the check-in
    # where the owner said it went live), so its follow-up tasks keep their dates on weekly
    # rebuilds instead of sliding with today.
    public_on = None
    if page_public:
        public_on = (pd(prev.get('page_public_on')) if prev else None) or today
    anchors = {'TODAY': started, 'L': L, 'CS': CS if CS else public_on, 'D': Dm, 'L1': L1}
    anchors.update(fest_dates)

    # ---- Gates ----
    def gate(gid, title, date, text, source, latest=None, recommended=None, status=None):
        g = {'id': gid, 'title': title, 'date': date.isoformat() if date else None, 'text': text, 'source': source,
             'source_url': data['sources']['sources'].get(source, {}).get('url') if source else None}
        if latest:
            g['latest'] = latest.isoformat()
        if recommended:
            g['recommended'] = recommended.isoformat()
        if status:
            g['status'] = status
        elif date is None:
            g['status'] = 'undated'
        elif date < today:
            g['status'] = 'late'
        elif (date - today).days <= 14:
            g['status'] = 'due soon'
        else:
            g['status'] = 'on track'
        gates.append(g)

    G = {g['id']: g for g in data['gates']['gates']}
    def req_ok(g):
        r = g.get('requires', [])
        if 'not_free' in r and free:
            return False
        if 'demo' in r and demo == 'none':
            return False
        return True

    if steam:
        if page_public:
            gate('steam_coming_soon', G['steam_coming_soon']['title'], None, G['steam_coming_soon']['text'], 'steam_coming_soon', status='done')
        else:
            sub = add_bdays(CS, -7) if CS else None
            gate('steam_store_submit', G['steam_store_submit']['title'], sub, G['steam_store_submit']['text'], 'steam_coming_soon')
            gate('steam_coming_soon', G['steam_coming_soon']['title'], CS, G['steam_coming_soon']['text'], 'steam_coming_soon',
                 latest=(L - dt.timedelta(days=14)) if L else None)
        if L and not launched:
            gate('steam_date_lock', G['steam_date_lock']['title'], L - dt.timedelta(days=14), G['steam_date_lock']['text'], 'steam_release_dates')
            gate('steam_tags', G['steam_tags']['title'], L - dt.timedelta(days=14), G['steam_tags']['text'], 'steam_tags')
            gate('steam_build_submit', G['steam_build_submit']['title'], add_bdays(L, -7), G['steam_build_submit']['text'], 'steam_release',
                 recommended=L - dt.timedelta(days=21))
            if not free:
                gate('steam_launch_discount', G['steam_launch_discount']['title'], L - ONE, G['steam_launch_discount']['text'], 'steam_discounts')
            if p.get('steam_first_game', True) and not p.get('appid_created') and p.get('store_page', 'none') == 'none':
                need = L - dt.timedelta(days=28)
                create_by = need - dt.timedelta(days=21)
                gate('steam_keys_wait', G['steam_keys_wait']['title'], create_by, G['steam_keys_wait']['text'], 'steam_keys')
            gate('steam_release_button', G['steam_release_button']['title'], L, G['steam_release_button']['text'], 'steam_release')
        if Dm:
            gate('steam_demo_notice', G['steam_demo_notice']['title'], Dm + dt.timedelta(days=14), G['steam_demo_notice']['text'], 'steam_wishlist')
        if L and not free:
            gate('steam_discount_cooldown', G['steam_discount_cooldown']['title'], L + dt.timedelta(days=30), G['steam_discount_cooldown']['text'], 'steam_discounts')
            first = None
            for s in snap['seasonal_sales']:
                st = pd(s.get('start'))
                if st and st >= L + dt.timedelta(days=30) and st >= today:
                    first = s
                    break
            if first:
                gate('steam_first_seasonal_sale', 'First Steam seasonal sale you can join: ' + first['name'], pd(first['start']),
                     G['steam_first_seasonal_sale']['text'], 'steam_events')
            elif L:
                gate('steam_first_seasonal_sale', 'First Steam seasonal sale you can join', None,
                     G['steam_first_seasonal_sale']['text'] + ' The next one is not announced yet in the snapshot.', 'steam_events')
        if chosen:
            e = [x for x in snap['nextfest'] if x['id'] == chosen['id']][0]
            for key, label in (('registration_deadline', 'registration deadline'), ('press_preview_submit', 'submit demo for Press Preview (optional)'),
                               ('all_items_due', 'all demo items submitted for review'), ('start', 'festival starts, demo live')):
                if e.get(key):
                    gate('nextfest_' + key, '%s: %s' % (e['name'], label), pd(e[key]),
                         'From the official edition page, as read on %s. I re-check it every week.' % snap['verified_on'], 'steam_nextfest')
    if L and not launched:
        if 'epic' in stores:
            gate('epic_onboarding', G['epic_onboarding']['title'], L - dt.timedelta(days=75), G['epic_onboarding']['text'], 'epic_onboarding')
        if 'ios' in stores:
            gate('ios_preorder_window', G['ios_preorder_window']['title'], L - dt.timedelta(days=180), G['ios_preorder_window']['text'], 'apple_preorders')
        if 'android' in stores:
            gate('android_prereg_window', G['android_prereg_window']['title'], L - dt.timedelta(days=90), G['android_prereg_window']['text'], 'play_prereg')
    for c in sorted(set(stores) & CONSOLES):
        cd = (p.get('custom_dates') or {}).get(c + '_launch')
        gate('console_' + c, '%s: your submission and release dates' % data['platforms']['platforms'][c]['name'],
             pd(cd), G['console_dates']['text'], data['platforms']['platforms'][c]['sources'][0],
             status=None if cd else 'waiting on platform')

    # ---- Phase ----
    if launched or (L and dtl is not None and dtl < -7):
        since = (today - L).days
        phase = 'launch_window' if since <= 7 else 'first_month' if since <= 30 else 'long_tail'
    elif L is None:
        phase = 'groundwork' if p.get('stage') == 'idea' or p.get('store_page') == 'none' else 'grow'
    elif dtl <= 7:
        phase = 'launch_window'
    elif dtl <= 56:
        phase = 'final_approach'
    elif F and (F - today).days <= ph['showcase_window_days_before_festival'] and today <= pd(chosen['end']):
        phase = 'showcase'
    elif dtl <= 252:
        phase = 'grow'
    else:
        phase = 'reveal' if (page_public or p.get('stage') != 'idea') else 'groundwork'
    sprint = bool(L and not launched and dtl < ph['sprint_if_days_to_launch_below'])

    # ---- Tasks ----
    prev_status, prev_grace = {}, {}
    if prev:
        for t in prev.get('tasks', []):
            if t.get('status') in ('done', 'skipped'):
                prev_status[t['id']] = t['status']
            elif t.get('day_one_grace') and t.get('due'):
                prev_grace[t['id']] = pd(t['due'])
    # Store page work Steam requires before a page can go public. Only these are
    # implied done by a public page; trailer, reveal posts and profiles need the owner's word.
    page_implies = lambda t: t['anchor'] == 'CS' and t['offset_days'] <= 0 and t['platforms'] == ['steam']
    budget_set = p.get('budget') in ('zero', 'lt500', '500to2500', 'gt2500')
    order = {x['id']: x['order'] for x in ph['phases']}
    tasks = []
    for t in data['tasks']['tasks']:
        if not (set(t['platforms']) & tok):
            continue
        r = set(t['requires'])
        if 'paid' in r and not budget_paid: continue
        if 'not_free' in r and free: continue
        if 'ea' in r and not ea: continue
        if 'festival' in r and not chosen: continue
        if 'demo_planned' in r and not (Dm or demo == 'planning'): continue
        if 'stage_idea' in r and p.get('stage') != 'idea': continue
        if essentials and not t['essentials']: continue
        if launched and order[t['phase']] < order['launch_window']: continue
        anchor = anchors.get(t['anchor'])
        if anchor is None and t['anchor'] == 'D' and 'festival' in r and F:
            anchor = prev_bday(F - ONE)  # a festival demo has to be live before the festival starts
        raw_due = anchor + dt.timedelta(days=t['offset_days']) if anchor else None
        due = roll_due(raw_due, t['offset_days'], today)
        status = 'open'
        grace = False
        if t['asset'] and t['asset'] in assets:
            status = 'done'
        elif page_public and page_implies(t):
            status = 'done'
        elif 'page_exists' in t['done_if'] and (page_public or p.get('store_page') == 'built' or p.get('appid_created')):
            status = 'done'
        elif 'page_built' in t['done_if'] and p.get('store_page') == 'built':
            status = 'done'
        elif t['id'] == 'gw_home_base' and p.get('home_base'):
            status = 'done'
        elif t['id'] == 'gw_channels' and p.get('channels'):
            status = 'done'
        elif t['id'] == 'gw_budget' and budget_set:
            status = 'done'
        if t['id'] in prev_status:
            status = prev_status[t['id']]
        if status == 'open' and due and due <= today and not prev and not launched and not sprint:
            due = next_bday(today + ONE)  # first build: nothing is overdue or due on day one
            grace = True
        elif status == 'open' and due and raw_due and due > raw_due and t['offset_days'] < 0 and not prev and not launched and not sprint:
            grace = True  # first build moved weekend work forward past today; keep that date on rebuilds
        if status == 'open' and t['id'] in prev_grace and due and due < prev_grace[t['id']]:
            due = prev_grace[t['id']]  # keep the day-one grace date on later rebuilds
            grace = True
        if status == 'open' and due and due < today:
            if launched:
                status = 'past'
            elif sprint and (t['priority'] > 1 or (order[t['phase']] <= order['grow'] and not t['essentials'])):
                status = 'skipped_by_plan'
            else:
                status = 'catch_up'
        item = {'id': t['id'], 'title': t['title'], 'why': t['why'], 'phase': t['phase'],
                'due': due.isoformat() if due else None, 'status': status, 'effort_hours': t['effort_hours'],
                'priority': t['priority'], 'draft_tool': t['draft_tool'],
                'source_urls': [data['sources']['sources'][s]['url'] for s in t['source_ids']]}
        if grace:
            item['day_one_grace'] = True
        if publisher and t['publisher_owned']:
            item['owner'] = 'confirm with publisher'
        tasks.append(item)
    tasks.sort(key=lambda x: (x['due'] or '9999', order[x['phase']], x['priority']))

    # ---- This week ----
    horizon = (today + dt.timedelta(days=21)).isoformat()
    cand = [t for t in tasks if t['status'] == 'catch_up' or (t['status'] == 'open' and t['due'] and t['due'] <= horizon)]
    if not cand and not L:
        cand = [t for t in tasks if t['status'] == 'open' and order[t['phase']] <= order[phase] + 1]
    cand.sort(key=lambda x: (x['priority'], today.isoformat() if x['status'] == 'catch_up' else (x['due'] or '9999'), order[x['phase']]))
    week, used, cu, cu_hours = [], 0.0, 0, 0.0
    cu_max = (max_tasks + 1) // 2
    has_fresh = any(t['status'] == 'open' for t in cand)
    for t in cand:
        if len(week) >= max_tasks:
            break
        if used + t['effort_hours'] > hours_budget and week:
            continue
        if t['status'] == 'catch_up' and has_fresh and (cu >= cu_max or cu_hours + t['effort_hours'] > hours_budget / 2.0) and cu:
            continue
        week.append(t['id'])
        used += t['effort_hours']
        if t['status'] == 'catch_up':
            cu += 1
            cu_hours += t['effort_hours']
    # The coach promises at least 3 tasks a week (when that many are open). If one big
    # task used up the hours, top up with quick tasks (1 hour or less), nearest due first,
    # going over the budget by at most a fifth of it (1 hour at most).
    min_tasks = min(3, max_tasks)
    slack = min(1.0, round(hours_budget * 0.2, 1))
    if len(week) < min_tasks:
        pool = [t for t in cand if t['id'] not in week]
        pool += sorted([t for t in tasks if t['status'] == 'open' and t['id'] not in week and t not in pool],
                       key=lambda x: (x['due'] or '9999', x['priority']))
        for t in pool:
            if len(week) >= min_tasks:
                break
            if t['effort_hours'] <= 1 and used + t['effort_hours'] <= hours_budget + slack:
                week.append(t['id'])
                used += t['effort_hours']

    # ---- Date change log and recheck ----
    changes = list(prev.get('changes', [])) if prev else []
    if prev and prev.get('launch_date') != (L.isoformat() if L else None):
        changes.append({'on': today.isoformat(), 'from': prev.get('launch_date'), 'to': L.isoformat() if L else None})
        pl = pd(prev.get('launch_date'))
        if steam and pl and (pl - today).days <= 14 and not launched:
            warnings.append({'id': 'steam_date_locked', 'text':
                'Your Steam date was inside the two-week lock, so it cannot be changed in Steamworks. The plan shows the new date, but Steam will keep the old one.',
                'source': 'steam_release_dates'})

    return {
        'built_on': today.isoformat(), 'started_on': started.isoformat(), 'game': p.get('game_name') or 'Your game', 'stores': stores,
        'home_base': p.get('home_base') or (stores[0] if stores else None),
        'launch_date': L.isoformat() if L else None, 'launch_display': display_date(L, prec), 'precision': prec,
        'days_to_launch': dtl, 'phase': phase, 'sprint': sprint, 'essentials_track': essentials,
        'hours_budget': hours_budget, 'coming_soon_target': CS.isoformat() if CS else None,
        'page_public_on': public_on.isoformat() if public_on else None,
        'festival_options': fest_options, 'festival': chosen['id'] if chosen else None,
        'demo_date': Dm.isoformat() if Dm else None, 'ea_1_0_date': L1.isoformat() if L1 else None,
        'gates': sorted(gates, key=lambda g: g['date'] or '9999'), 'tasks': tasks, 'this_week': week,
        'warnings': warnings, 'notes': notes, 'changes': changes,
        'events_snapshot_verified_on': snap['verified_on'],
    }

def summary(plan):
    out = ['%s: %s (%s), phase %s%s' % (plan['game'], plan['launch_display'],
           ('%s days' % plan['days_to_launch']) if plan['days_to_launch'] is not None else 'no date',
           plan['phase'], ', sprint' if plan['sprint'] else '')]
    for w in plan['warnings']:
        out.append('WARNING: ' + w['text'])
    for n in plan['notes']:
        out.append('Note: ' + n)
    out.append('Gates:')
    for g in plan['gates']:
        out.append('  %-11s %-12s %s' % (g['date'] or '-', g['status'], g['title']))
    if plan['festival_options']:
        out.append('Next Fest options: ' + ', '.join(f['name'] for f in plan['festival_options']))
    byid = {t['id']: t for t in plan['tasks']}
    out.append('This week:')
    for i in plan['this_week']:
        t = byid[i]
        out.append('  [%s] %s (%sh, due %s)' % (t['status'], t['title'], t['effort_hours'], t['due'] or 'when ready'))
    return '\n'.join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', required=True)
    ap.add_argument('--today')
    ap.add_argument('--prev')
    ap.add_argument('--data', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data'))
    ap.add_argument('--out')
    ap.add_argument('--summary', action='store_true')
    a = ap.parse_args()
    profile = json.load(open(a.profile, encoding='utf-8'))
    profile = profile.get('profile', profile)
    today = pd(a.today) if a.today else D.today()
    prev = json.load(open(a.prev, encoding='utf-8')) if a.prev else None
    plan = build(profile, today, load_data(a.data), prev)
    if a.out:
        json.dump(plan, open(a.out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    if a.summary or not a.out:
        print(summary(plan))

if __name__ == '__main__':
    main()
