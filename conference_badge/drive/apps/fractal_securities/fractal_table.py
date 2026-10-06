# Pull the performance table out of the fractal-securities.com page.
#
# Plain Python that runs on the badge (MicroPython) and on a computer
# (tools/check_portfolio.py). The table is found by its header row, a
# "Portfolio" column and an "S&P 500" / "VOO" column, so it doesn't depend on
# exact markup or class names. No regex: just str.find, which both have.

ENTITIES = {
    "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " ",
    "minus": "-", "ndash": "-", "mdash": "-", "plus": "+", "thinsp": "",
    "middot": ".",
}
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
SPACE = (" ", "\t", "\n", "\r", ">", "/")


def _unescape(t):
    if "&" not in t:
        return t
    out = []
    i = 0
    while True:
        a = t.find("&", i)
        if a < 0:
            out.append(t[i:])
            break
        b = t.find(";", a)
        if b < 0 or b - a > 10:
            out.append(t[i:a + 1])
            i = a + 1
            continue
        name = t[a + 1:b]
        rep = ENTITIES.get(name)
        if rep is None and name.startswith("#"):
            try:
                rep = chr(int(name[2:], 16) if name[1:2] in ("x", "X") else int(name[1:]))
            except ValueError:
                rep = None
        out.append(t[i:a])
        out.append(t[a:b + 1] if rep is None else rep)
        i = b + 1
    return "".join(out)


def _clean(t):
    t = _unescape(t)
    for bad, good in (("−", "-"), ("–", "-"), ("—", "-"), (" ", " "),
                      (" ", ""), (" ", ""), ("​", "")):
        if bad in t:
            t = t.replace(bad, good)
    return " ".join(t.split())


def _texts(html, low, a, b):
    """Text runs between tags in html[a:b], skipping <script> and <style> bodies."""
    out = []
    i = a
    while i < b:
        lt = html.find("<", i, b)
        if lt < 0:
            lt = b
        t = _clean(html[i:lt])
        if t:
            out.append(t)
        if lt >= b:
            break
        gt = html.find(">", lt, b)
        if gt < 0:
            break
        for skip in ("script", "style"):
            if low.startswith(skip, lt + 1):
                end = low.find("</" + skip, gt, b)
                gt = b if end < 0 else low.find(">", end, b)
                if gt < 0:
                    gt = b
                break
        i = gt + 1
    return out


def _opens(low, tag, a, b):
    """Positions in [a, b) where <tag opens (so "<th" doesn't match "<thead")."""
    out = []
    key = "<" + tag
    i = a
    while True:
        p = low.find(key, i, b)
        if p < 0:
            return out
        if low[p + len(key):p + len(key) + 1] in SPACE:
            out.append(p)
        i = p + 1


def _rows(html, low, a, b):
    """Table rows in [a, b) as lists of cells, each cell a list of text runs."""
    rows = []
    starts = _opens(low, "tr", a, b) + [b]
    for r in range(len(starts) - 1):
        r0, r1 = starts[r], starts[r + 1]
        cells = sorted(_opens(low, "td", r0, r1) + _opens(low, "th", r0, r1)) + [r1]
        row = []
        for c in range(len(cells) - 1):
            body = html.find(">", cells[c], cells[c + 1])
            row.append(_texts(html, low, body + 1, cells[c + 1]) if body >= 0 else [])
        if row:
            rows.append(row)
    return rows


def _header(rows):
    for i, row in enumerate(rows):
        joined = [" ".join(cell).lower() for cell in row]
        port = voo = None
        for c, text in enumerate(joined):
            if port is None and "portfolio" in text:
                port = c
            if voo is None and ("voo" in text or "s&p" in text):
                voo = c
        if port is not None and voo is not None:
            return i, port, voo
    return None, None, None


def _value(cell):
    for t in cell:
        if "%" in t:
            return t.replace(" ", "")
    return cell[0] if cell else ""


def _is_date(t):
    w = t.replace(",", " ").split()
    return len(w) >= 3 and w[0][:3].lower() in MONTHS and w[1].isdigit() and w[-1].isdigit() and len(w[-1]) == 4


def _as_of(html, low, a, b):
    texts = _texts(html, low, a, b)
    for k, t in enumerate(texts):
        at = t.lower().find("as of")
        if at >= 0:
            rest = t[at + 5:].strip(" :")
            if not rest and k + 1 < len(texts):
                rest = texts[k + 1]
            if rest:
                return rest
    for t in reversed(texts):
        if _is_date(t):
            return t
    return None


def _code_blocks(low):
    """(start, end) of every <script> and <style> block, so text inside them is ignored."""
    spans = []
    for tag in ("script", "style"):
        for a in _opens(low, tag, 0, len(low)):
            b = low.find("</" + tag, a)
            spans.append((a, len(low) if b < 0 else b))
    return spans


def _find(low, key, i, skip):
    """low.find(key, i), ignoring matches inside the skip spans."""
    while True:
        p = low.find(key, i)
        if p < 0:
            return p
        for a, b in skip:
            if a <= p < b:
                i = b
                break
        else:
            return p


def parse(html):
    """-> {"as_of": "Oct 9, 2026" or None, "rows": [[period, portfolio, voo], ...]}

    rows is empty if no table with Portfolio and S&P 500 / VOO columns was found.
    """
    low = html.lower()
    skip = _code_blocks(low)
    pos = 0
    while True:
        t0 = _find(low, "<table", pos, skip)
        if t0 < 0:
            return {"as_of": _as_of(html, low, 0, len(html)), "rows": []}
        t1 = _find(low, "</table", t0, skip)
        if t1 < 0:
            t1 = len(low)
        rows = _rows(html, low, t0, t1)
        head, port, voo = _header(rows)
        if head is not None:
            break
        pos = t1 + 1

    out = []
    for row in rows[head + 1:]:
        if len(row) <= max(port, voo) or not row[0]:
            continue
        out.append([row[0][0], _value(row[port]), _value(row[voo])])
    return {"as_of": _as_of(html, low, 0, t0), "rows": out}
