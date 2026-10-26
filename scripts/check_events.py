#!/usr/bin/env python3
"""Re-read the official Steam event pages and compare with data/events_snapshot.json.

Exit 0: pages read and the snapshot matches.
Exit 2: pages read but something changed (printed). Use --write to refresh the snapshot dates
        you have checked by hand, then commit.
Exit 1: a page could not be read or parsed.
Usage: python3 scripts/check_events.py [--write]
"""
import datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _http import fetch, text  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, 'data', 'events_snapshot.json')
SRC = os.path.join(ROOT, 'data', 'event_sources.json')
MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'], 1)}
MON3 = {k[:3]: v for k, v in MONTHS.items()}

def iso(y, mon, d):
    return dt.date(int(y), MONTHS.get(mon.lower(), MON3.get(mon.lower()[:3])), int(d)).isoformat()

def parse_upcoming(t):
    out = {'nextfest': [], 'seasonal': {}, 'themed': {}}
    for m in re.finditer(r'Next Fest \| (\w+) (\d+) - (?:(\w+) )?(\d+), (\d{4})', t):
        mon1, d1, mon2, d2, y = m.groups()
        out['nextfest'].append((iso(y, mon1, d1), iso(y, mon2 or mon1, d2)))
    for m in re.finditer(r'(Winter|Spring|Summer|Autumn) Sale (\d{4}) \| (?:(\w+) (\d+), (\d{4}) - (\w+) (\d+), (\d{4})|TBD)', t):
        g = m.groups()
        name = '%s Sale %s' % (g[0], g[1])
        out['seasonal'][name] = (iso(g[4], g[2], g[3]), iso(g[7], g[5], g[6])) if g[2] else (None, None)
    for year in ('2026', '2027'):
        sec = re.search(year + r' Fests Event Dates Theme Registration Eligibility & Notes (.*?)(?:\d{4} Fests|Next Fest Running)', t)
        if not sec:
            continue
        for m in re.finditer(r'(\w{3}) (\d+) (\w{3}) (\d+) (.+?) Registration details', sec.group(1)):
            mon1, d1, mon2, d2, name = m.groups()
            y2 = int(year) + (1 if MON3[mon2.lower()] < MON3[mon1.lower()] else 0)
            out['themed'][name.strip()] = (iso(year, mon1, d1), iso(y2, mon2, d2))
    return out

def parse_edition(t):
    reg = None
    mm = re.search(r'(\w+) (\d+), 11:59 ?pm P[SD]T - Registration Deadline', t)
    if mm:
        reg = (mm.group(1), int(mm.group(2)))
    return reg

def main():
    write = '--write' in sys.argv
    snap = json.load(open(SNAP, encoding='utf-8'))
    srcs = {p['id']: p for p in json.load(open(SRC, encoding='utf-8'))['pages']}
    diffs = []
    try:
        st, body = fetch(srcs['steam_upcoming_events']['url'])
        live = parse_upcoming(text(body))
    except Exception as e:
        print('FAIL reading Steam upcoming events:', e)
        return 1
    if not live['nextfest'] or not live['seasonal']:
        print('FAIL parsing Steam upcoming events page (layout may have changed)')
        return 1
    snap_nf = {(e['start'], e['end']) for e in snap['nextfest']}
    for se in live['nextfest']:
        if se not in snap_nf:
            diffs.append('New or changed Next Fest dates on the live page: %s to %s' % se)
    live_nf = set(live['nextfest'])
    for e in snap['nextfest']:
        if e['end'] >= dt.date.today().isoformat() and (e['start'], e['end']) not in live_nf:
            diffs.append('Snapshot Next Fest %s no longer matches the live page' % e['name'])
    for s in snap['seasonal_sales']:
        lv = live['seasonal'].get(s['name'])
        if lv is None:
            if s.get('start') and s['end'] >= dt.date.today().isoformat():
                diffs.append('Seasonal sale missing on live page: %s' % s['name'])
        elif lv != (s.get('start'), s.get('end')):
            diffs.append('Seasonal sale changed: %s snapshot %s to %s, live %s to %s' % (s['name'], s.get('start'), s.get('end'), lv[0], lv[1]))
    for name, lv in live['seasonal'].items():
        if name not in {s['name'] for s in snap['seasonal_sales']}:
            diffs.append('New seasonal sale on live page: %s %s to %s' % (name, lv[0], lv[1]))
    snap_th = {f['name']: (f['start'], f['end']) for f in snap['themed_fests']}
    for name, lv in live['themed'].items():
        if name not in snap_th:
            diffs.append('New themed fest: %s %s to %s' % (name, lv[0], lv[1]))
        elif snap_th[name] != lv:
            diffs.append('Themed fest changed: %s snapshot %s, live %s' % (name, snap_th[name], lv))
    for e in snap['nextfest']:
        if not e.get('registration_deadline'):
            continue
        try:
            st, body = fetch(srcs[e['id']]['url'])
        except Exception as ex:
            print('FAIL reading', e['id'], ex)
            return 1
        reg = parse_edition(text(body))
        want = dt.date.fromisoformat(e['registration_deadline'])
        if not reg:
            print('FAIL parsing registration deadline on', e['id'])
            return 1
        if (MONTHS[reg[0].lower()], reg[1]) != (want.month, want.day):
            diffs.append('%s registration deadline changed: snapshot %s, live %s %s' % (e['name'], want, reg[0], reg[1]))
    print('Read live: %d Next Fest editions, %d seasonal sales, %d themed fests' % (len(live['nextfest']), len(live['seasonal']), len(live['themed'])))
    if diffs:
        for d in diffs:
            print('CHANGED:', d)
        if write:
            snap['verified_on'] = dt.date.today().isoformat()
            json.dump(snap, open(SNAP, 'w', encoding='utf-8'), indent=2)
            print('verified_on updated; edit the changed entries by hand before committing.')
        return 2
    print('Snapshot matches the official pages (snapshot verified_on %s)' % snap['verified_on'])
    return 0

if __name__ == '__main__':
    sys.exit(main())
