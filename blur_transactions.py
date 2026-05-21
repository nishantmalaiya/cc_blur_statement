"""
blur_transactions.py
--------------------
Dynamically detects the Account Summary table in any credit card PDF
and blurs all transaction rows EXCEPT the ones in VISIBLE_TRANSACTIONS.

Works on any PDF regardless of page size or layout — no hardcoded coordinates.

Usage:
    python blur_transactions.py

Requirements:
    pip install pymupdf
"""

import re
import fitz  # PyMuPDF

# ── Configuration ─────────────────────────────────────────────────────────────

INPUT_PDF  = r"D:\python\cc_blur_statement\Credit_Card.pdf"
OUTPUT_PDF = r"D:\python\cc_blur_statement\Credit_Card_Redacted.pdf"

# Transactions to keep VISIBLE — add as many as needed (partial match, case-insensitive)
VISIBLE_TRANSACTIONS = [
    "GOOGLE PLAY CONTENT PU",
]

# Blur box styling
BLUR_FILL_COLOR   = (0.82, 0.84, 0.90)   # light blue-grey
BLUR_STRIPE_COLOR = (0.78, 0.80, 0.87)
BLUR_OPACITY      = 1.0
ROW_PADDING       = 1.5                   # pts above/below each row

# ── Date pattern ──────────────────────────────────────────────────────────────

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


# ── Core logic ────────────────────────────────────────────────────────────────

def find_table_bounds(words):
    """
    Auto-detect the Y range of the Account Summary table by finding:
      - Start: the line containing 'Account Summary' header
      - End:   the line containing 'End of Statement'
    Returns (y_start, y_end) in PDF points.
    """
    y_start = None
    y_end   = None

    for w in words:
        text = w[4].strip().lower()
        y0, y1 = w[1], w[3]

        if "account" in text or "summary" in text:
            # Start table a bit after the "Account Summary" heading
            if y_start is None or y0 > y_start:
                y_start = y1 + 2   # just below the heading

        if "end" in text and y_start and y0 > y_start:
            y_end = y0
            break   # first "End" after table start = "End of Statement"

    return y_start, y_end


def get_page_width(page):
    return page.rect.width


def group_words_into_rows(words, y_start, y_end):
    """
    Group words that fall within [y_start, y_end] by their Y midpoint.
    Returns list of (y0, y1, full_text) sorted top-to-bottom.
    """
    in_table = [w for w in words if y_start <= w[1] <= y_end]

    lines = {}
    for w in in_table:
        mid_y = round((w[1] + w[3]) / 2, 0)
        lines.setdefault(mid_y, []).append(w)

    rows = []
    for mid_y in sorted(lines):
        line_words = sorted(lines[mid_y], key=lambda w: w[0])
        text = " ".join(w[4] for w in line_words)
        y0 = min(w[1] for w in line_words)
        y1 = max(w[3] for w in line_words)
        rows.append((y0, y1, text))

    return rows


def is_transaction_row(text):
    """
    True if the row starts with a DD/MM/YYYY date -> it's a real transaction row.
    """
    first_token = text.strip().split()[0] if text.strip() else ""
    return bool(DATE_RE.match(first_token))


def is_visible(text):
    """True if this transaction should remain unblurred."""
    text_lower = text.lower()
    return any(v.lower() in text_lower for v in VISIBLE_TRANSACTIONS)


def draw_blur(page, y0, y1, page_width):
    """Cover a row with an opaque striped rectangle."""
    margin = 5
    rect = fitz.Rect(margin, y0 - ROW_PADDING, page_width - margin, y1 + ROW_PADDING)

    # Solid fill
    page.draw_rect(rect, color=BLUR_FILL_COLOR, fill=BLUR_FILL_COLOR,
                   fill_opacity=BLUR_OPACITY, overlay=True)

    # Vertical stripe texture
    x = int(margin)
    while x < int(page_width - margin):
        page.draw_line(
            fitz.Point(x, y0 - ROW_PADDING),
            fitz.Point(x, y1 + ROW_PADDING),
            color=BLUR_STRIPE_COLOR,
            width=2,
        )
        x += 6

    # "REDACTED" label
    mid_y = (y0 + y1) / 2
    page.insert_text(
        fitz.Point(page_width - 80, mid_y + 3),
        "REDACTED",
        fontsize=6,
        color=(0.50, 0.53, 0.65),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def process_page(page):
    words = page.get_text("words")
    page_width = get_page_width(page)

    # Step 1: auto-detect table bounds
    y_start, y_end = find_table_bounds(words)
    if y_start is None or y_end is None:
        print("  Could not find Account Summary table on this page -- skipping.")
        return 0

    print(f"  Table detected: y={y_start:.1f} to y={y_end:.1f}")

    # Step 2: group words into rows
    rows = group_words_into_rows(words, y_start, y_end)

    # Step 3: blur non-visible transaction rows
    blurred = 0
    for y0, y1, text in rows:
        if not is_transaction_row(text):
            continue   # skip headers, sub-headers, "End of Statement" etc.

        if is_visible(text):
            print(f"  [VISIBLE]  {text[:80]}")
        else:
            draw_blur(page, y0, y1, page_width)
            blurred += 1
            print(f"  [BLURRED]  {text[:80]}")

    return blurred


def main():
    doc = fitz.open(INPUT_PDF)
    total_blurred = 0

    for i, page in enumerate(doc):
        print(f"\n-- Page {i + 1} --")
        total_blurred += process_page(page)

    doc.save(OUTPUT_PDF, garbage=4, deflate=True)
    doc.close()

    print(f"\nDone -- {total_blurred} row(s) blurred across all pages.")
    print(f"Saved to: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()