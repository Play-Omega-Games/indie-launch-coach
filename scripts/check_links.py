#!/usr/bin/env python3
"""Check every link in the repo: status 200 and, where known, the page title.

Steamworks answers missing pages with a 200 "Documentation Home Page", so a bare
status check is not enough. Exit code 0 when everything passes.
Usage: python3 scripts/check_links.py [--quiet]
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _http import fetch, title  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', 'tests'}
URL_RE = re.compile(r'https?://[^\s)\]"\'<>`|,]+')
# URLs that are patterns or not pages
IGNORE_PREFIX = ('https://raw.githubusercontent.com/Play-Omega-Games/indie-launch-coach/',
                 'https://github.com/Play-Omega-Games/indie-launch-coach')

def collect():
    urls = {}
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if not f.endswith(('.md', '.json', '.py')):
                continue
            path = os.path.join(d, f)
            for u in URL_RE.findall(open(path, encoding='utf-8').read()):
                u = u.rstrip('.;:')
                if u.startswith(IGNORE_PREFIX) or '<' in u or '{' in u:
                    continue
                urls.setdefault(u, set()).add(os.path.relpath(path, ROOT))
    return urls

def expected_titles():
    src = json.load(open(os.path.join(ROOT, 'data', 'sources.json'), encoding='utf-8'))['sources']
    return {v['url']: v.get('title_contains') for v in src.values()}

def main():
    quiet = '--quiet' in sys.argv
    urls, exp = collect(), expected_titles()
    fails = 0
    for u in sorted(urls):
        want = exp.get(u)
        try:
            status, body = fetch(u)
            t = title(body)
            ok = status == 200
            if ok and 'partner.steamgames.com/doc' in u and t.startswith('Documentation Home Page'):
                ok, why = False, 'Steamworks soft 404'
            elif ok and want and want.lower() not in t.lower():
                ok, why = False, 'title "%s" lacks "%s"' % (t[:60], want)
            else:
                why = t[:70]
        except Exception as e:  # network or HTTP error
            ok, why = False, str(e)[:80]
        if not ok:
            fails += 1
        if not ok or not quiet:
            print('%s  %s  %s' % ('OK  ' if ok else 'FAIL', u, why))
        time.sleep(0.3)
    print('%d links checked, %d failed' % (len(urls), fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
