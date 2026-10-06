#!/usr/bin/env python3
"""Run the badge's table parser against the live fractal-securities.com page.

    python3 tools/check_portfolio.py            # or: make check-portfolio

Uses exactly the code the badge runs (drive/apps/fractal_securities/
fractal_table.py), so if the table prints correctly here, the app will read it.
"""
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "drive", "apps", "fractal_securities"))
import fractal_table  # noqa: E402

URL = "https://fractal-securities.com/"

req = urllib.request.Request(URL, headers={"User-Agent": "tufty-badge-check"})
with urllib.request.urlopen(req, timeout=20) as r:
    html = r.read().decode("utf-8", "replace")

data = fractal_table.parse(html)
print(f"{URL}  ({len(html):,} bytes)")
print(f"as of: {data['as_of']!r}")
if not data["rows"]:
    sys.exit("no table with Portfolio and S&P 500 / VOO columns found - the badge would show 'table not found'")
print(f"\n{'Period':<12}{'Portfolio':>12}{'S&P 500':>12}")
for period, port, voo in data["rows"]:
    print(f"{period:<12}{port:>12}{voo:>12}")
odd = {ch for row in data["rows"] for cell in row for ch in cell if ord(ch) > 126}
if odd:
    print("\nwarning: non-ASCII characters the badge font may not have:", " ".join(f"U+{ord(c):04X}" for c in sorted(odd)))
print(f"\nok: {len(data['rows'])} rows")
