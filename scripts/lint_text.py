#!/usr/bin/env python3
"""Lint user-facing text.

Checks: no em or en dashes; no @handles; no credit phrases; links only to allowed
official domains; no stat-like numbers (percentages or counts of wishlists, sales,
followers and so on) unless the line is about a platform rule; optional blocklist of
names (one per line) passed with --blocklist FILE.

Usage: python3 scripts/lint_text.py [--blocklist FILE] [extra files or folders...]
Exit 0 when clean.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = ['README.md', 'playbook', 'templates', 'data']
JSON_KEYS = {'title', 'why', 'text', 'focus', 'window', 'note', 'notes', 'name', 'label', 'what', 'themes',
             'setup', 'sprint_rule', 'owner_events', 'themed_note', 'prompt', 'prompts', 'idea', 'hook'}
ALLOWED = ('partner.steamgames.com', 'store.steampowered.com', 'itch.io', 'dev.epicgames.com', 'developer.nintendo.com',
           'partners.playstation.net', 'www.xbox.com', 'developer.apple.com', 'support.google.com', 'www.ecfr.gov',
           'github.com/Play-Omega-Games', 'raw.githubusercontent.com/Play-Omega-Games', 'playomega.games')
DASH = re.compile('[\u2014\u2013]')
HANDLE = re.compile(r'(?<![\w.])@[A-Za-z0-9_]{2,}')
CREDIT = re.compile(r'\b(courtesy of|credit(?:ed|s)? to|according to|inspired by|thanks to|adapted from|as seen in|distilled from|crowdsourced)\b', re.I)
URL = re.compile(r'https?://([^\s)\]"\'<>`]+)')
STAT = re.compile(r'(\d[\d,.]*\s?%|\b\d[\d,.]*\s?[kKmM]?\s+(?:wishlists?|sales|followers|views|installs|conversions|subscribers|downloads|players)\b)')
RULE_WORDS = re.compile(r'(Steam|Steamworks|Epic|Apple|App Store|Google Play|Play Console|itch\.io|Xbox|Nintendo|PlayStation|you entered|\{)', re.I)

def lines_of(path):
    if path.endswith('.json'):
        data = json.load(open(path, encoding='utf-8'))
        out = []
        def walk(o, key=None):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, k)
            elif isinstance(o, list):
                for v in o:
                    walk(v, key)
            elif isinstance(o, str) and key in JSON_KEYS:
                out.append(o)
        walk(data)
        return out
    return open(path, encoding='utf-8').read().splitlines()

def files(targets):
    for t in targets:
        t = t if os.path.isabs(t) else os.path.join(ROOT, t)
        if os.path.isdir(t):
            for d, dirs, fs in os.walk(t):
                for f in sorted(fs):
                    if f.endswith(('.md', '.json')):
                        yield os.path.join(d, f)
        elif os.path.exists(t):
            yield t

def main():
    args = sys.argv[1:]
    block = []
    if '--blocklist' in args:
        i = args.index('--blocklist')
        block = [b.strip() for b in open(args[i + 1], encoding='utf-8') if b.strip() and not b.startswith('#')]
        del args[i:i + 2]
    targets = DEFAULT + args
    problems, n = [], 0
    for path in files(targets):
        n += 1
        rel = os.path.relpath(path, ROOT)
        for i, line in enumerate(lines_of(path), 1):
            def bad(why):
                problems.append('%s:%d: %s: %s' % (rel, i, why, line.strip()[:110]))
            if DASH.search(line):
                bad('em or en dash')
            for h in HANDLE.findall(line):
                if not re.search(r'[\w.+-]' + re.escape(h), line):
                    bad('handle ' + h)
            if CREDIT.search(line):
                bad('credit phrase')
            for u in URL.findall(line):
                if not u.startswith(ALLOWED):
                    bad('link outside allowed official domains: ' + u[:60])
            if STAT.search(line) and not RULE_WORDS.search(line):
                bad('number that reads like a stat, not tied to a platform rule')
            for b in block:
                if re.search(r'(?<![A-Za-z])' + re.escape(b) + r'(?![A-Za-z])', line, re.I):
                    bad('blocked name ' + b)
    for p in problems:
        print(p)
    print('%d files checked, %d problems' % (n, len(problems)))
    return 1 if problems else 0

if __name__ == '__main__':
    sys.exit(main())
