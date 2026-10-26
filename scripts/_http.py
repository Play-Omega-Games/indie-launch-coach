"""Small HTTP helper shared by the checkers. Standard library only."""
import re, urllib.request, html

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'ignore')

def title(body):
    m = re.search(r'<title[^>]*>(.*?)</title>', body, re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', m.group(1)).strip()) if m else ''

def text(body):
    body = re.sub(r'(?is)<(script|style).*?</\1>', ' ', body)
    body = re.sub(r'(?s)<[^>]+>', ' ', body)
    return re.sub(r'\s+', ' ', html.unescape(body))
