"""
Parses a BananaPatterns "fresh breakouts" PDF export into a list of stock dicts.

NOTE: This is a best-effort text/regex parser built from one sample export.
BananaPatterns can change their layout, and PDF text extraction from a
multi-column card layout is inherently a bit fragile. If a field comes back
as None, it just won't count toward that stock's score (see scoring.py),
so a partial parse still produces a usable (if slightly less accurate) score.

If you find it's misreading fields after your first real run, share the raw
extracted text (printed via `python parse_pdf.py yourfile.pdf --debug`) and
the regexes below can be tightened.
"""
import re
import sys
import pdfplumber


PRICE_LINE = re.compile(
    r"([A-Za-z0-9&'.\-\s]+?)\s*₹([\d,]+\.?\d*)\s*\(([+-]?\d+\.?\d*)%\)"
)

FIELD_PATTERNS = {
    "ticker": re.compile(r"\n([A-Z]{2,15})\n"),
    "breakout_date": re.compile(r"Breakout date.*?(\d{1,2} [A-Za-z]{3} \d{4})"),
    "vs_pivot_pct": re.compile(r"Now vs pivot \(%\).*?([+-]?\d+\.?\d*)%"),
    # Note: source PDF text sometimes has an unclosed "(" after "vs normal…",
    # so this stops at the first DIGIT rather than the first ")" — otherwise
    # it over-matches into the next field's value.
    "breakout_volume": re.compile(r"Breakout volume \(vs normal[^\d]*?([\d.]+)"),
    "cir": re.compile(r"Breakout close-in-range \(0.1\).*?([\d.]+)"),
    "rs_rating": re.compile(r"RS rating.*?(\d{1,3})"),
    "base_age_wk": re.compile(r"Base age.*?([\d.]+)\s*wk"),
    "rs_avg_in_base": re.compile(r"RS, average in base \(1.99\).*?(\d{1,3})"),
    "overhead_supply_pct": re.compile(r"Overhead supply \(%\).*?([+-]?\d+\.?\d*)%"),
    "base_count": re.compile(r"(\d{1,2})(?:st|nd|rd|th) base this year"),
    "held_pct": re.compile(r"first broke out[^,]*,\s*\+?([\d.]+)%\s*held"),
    "status": re.compile(r"(Powering up|Cooling off)"),
    "pivot_price": re.compile(r"pivot\s*₹?([\d,]+\.?\d*)"),
}


def extract_text(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            full_text += t + "\n"
    return full_text


def _clean_value(field, val):
    if field in (
        "vs_pivot_pct", "breakout_volume", "cir", "rs_rating",
        "base_age_wk", "rs_avg_in_base", "overhead_supply_pct",
        "base_count", "held_pct", "pivot_price",
    ):
        try:
            return float(val.replace(",", ""))
        except ValueError:
            return val
    return val


def _find_name_matches(full_text):
    matches = []
    for m in PRICE_LINE.finditer(full_text):
        name = m.group(1).strip().strip("-").strip()
        if len(name) < 3 or name.lower() in ("tech chart", "share"):
            continue
        matches.append({"name": name, "price": m.group(2), "pct": m.group(3), "pos": m.start()})
    return matches


def split_into_stock_blocks(full_text):
    """
    BananaPatterns renders cards two-per-row. In the extracted text this
    means: [NameA priceA] [NameB priceB] appear together, THEN both
    stocks' metric blocks (DataA, DataB) appear together afterward. A
    naive "next name = end of this stock's chunk" split therefore grabs
    DataA's numbers for NameB's card.

    Fix: process stock name-matches two at a time (one screen "row").
    The combined text span from NameA through (but not including) the
    NEXT row's first name contains both DataA and DataB, in that order
    (left column's metrics before right column's metrics). For each
    metric label, the 1st occurrence in that span belongs to A, the 2nd
    to B.
    """
    name_matches = _find_name_matches(full_text)
    blocks = []

    i = 0
    while i < len(name_matches):
        pair = name_matches[i:i + 2]
        span_start = pair[0]["pos"]
        span_end = (
            name_matches[i + 2]["pos"] if i + 2 < len(name_matches) else len(full_text)
        )
        span_text = full_text[span_start:span_end]

        for col_idx, stock_meta in enumerate(pair):
            stock = {
                "name": stock_meta["name"],
                "price": float(stock_meta["price"].replace(",", "")),
                "pct_change": float(stock_meta["pct"]),
            }
            for field, pattern in FIELD_PATTERNS.items():
                occurrences = list(pattern.finditer(span_text))
                if col_idx < len(occurrences):
                    stock[field] = _clean_value(field, occurrences[col_idx].group(1))
                else:
                    stock[field] = None
            blocks.append(stock)
        i += 2

    return blocks


def parse_pdf(pdf_path, debug=False):
    full_text = extract_text(pdf_path)
    if debug:
        print("----- RAW EXTRACTED TEXT -----")
        print(full_text)
        print("----- END RAW TEXT -----")
    stocks = split_into_stock_blocks(full_text)
    # De-duplicate by name (the same stock shouldn't appear twice on one screen)
    seen = {}
    for s in stocks:
        seen[s["name"]] = s
    return list(seen.values())


if __name__ == "__main__":
    path = sys.argv[1]
    debug = "--debug" in sys.argv
    result = parse_pdf(path, debug=debug)
    import json
    print(json.dumps(result, indent=2))
