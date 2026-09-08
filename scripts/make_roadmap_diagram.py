"""Generate the ROAD TO PRODUCTION diagram SVG (delivery view).

The capability diagram answers *what is built*. It is deliberately coarse — one
tile per capability — and that coarseness misleads in one specific way: it draws
seventeen built capabilities beside six unbuilt ones and so reads as a product
two-thirds finished. `DASHBOARD` is one tile and is done; `SPEECH TO TEXT` is one
tile and is five separate pieces of work with a vendor-selection gate in the
middle. **Tile count is not effort.** This diagram is where that is spelled out.

Four workstream columns of full cards. Order runs top to bottom inside a column;
the columns run in parallel. Two earlier attempts are worth recording, because
the shape here is a reaction to both:

*A four-stage grid of cards* showed the pieces and nothing about the road — four
stages given equal visual weight when they are nothing like equal, and no sense
of what overlaps.

*A lane timeline on a relative axis* fixed the overlap and broke everything else.
Bars carry a label and no explanation, so it said less than the grid it replaced;
thin bars read as a screenshot of a planning tool beside the card-based diagrams
13 and 14; and two lanes finished early, leaving half the canvas empty. A Gantt
with no dates does not earn its axis.

Card columns keep what each attempt got right: a card holds its explanation, the
columns are visibly concurrent, order is unambiguous inside a column, and no axis
implies a precision that does not exist. Sizing stays as S/M/L classes — there
are no weeks anywhere on the page, because an architect's estimate on a diagram
gets quoted as a commitment.

Gates are drawn tinted and outlined rather than as plain cards. Four items are
decisions or measurements, not components: they stop everything below them and no
amount of code routes around them. Two are contractual, and the legend says they
start alongside the first build work rather than after it.

Speaker separation is drawn conditional on purpose. It is real work only for mono
archive recordings; a native dual-channel telephony stream delivers agent and
member on separate channels as a property of the integration. Drawing
"diarisation" as an unconditional component would commit the project to building
something it should be procuring.

Run from the repo root:  python scripts/make_roadmap_diagram.py
Text fit is asserted horizontally and vertically, so a label that outgrows its
box fails loudly.
"""
import pathlib
import xml.etree.ElementTree as ET

W, H = 1880, 850
out = []

C = {
    "page": "#ffffff",
    "ink": "#16212e", "body": "#33414f", "muted": "#61707e", "hair": "#dfe5ec",
    "navy": "#143a6b", "navy_bg": "#f3f6fa", "navy_bd": "#c9d7e8",
    "orange": "#e8791a", "orange_bg": "#fdf7f0", "orange_bd": "#f3d0aa",
    "green": "#1c7a4b", "green_bg": "#f0f8f3", "green_bd": "#bcdcca",
    "red": "#d92b2b", "red_bg": "#fdf3f3", "red_bd": "#f0c6c6",
    "grey": "#9aa8b6", "grey_bg": "#f7f9fb", "grey_bd": "#dde4ec",
}
FONT = "'Segoe UI','Inter',-apple-system,'Helvetica Neue',Arial,sans-serif"
warn = []


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(s, fs, bold=False):
    base = 0.575 if bold else 0.525
    caps = sum(1 for ch in s if ch.isupper())
    return (len(s) * base + caps * 0.11) * fs


def fit(s, fs, avail, tag, bold=False):
    if tw(s, fs, bold) > avail:
        warn.append(f"{tag}: {s!r} {tw(s, fs, bold):.0f} > {avail:.0f}")


def vfit(bottom, limit, tag, pad=10):
    if bottom > limit - pad:
        warn.append(f"{tag}: content reaches {bottom:.0f}, floor {limit:.0f}")


def text(x, y, s, fs=13, fill="body", bold=False, anchor="start", ls=None):
    a = f' letter-spacing="{ls}"' if ls else ""
    out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{fs}" '
               f'fill="{C.get(fill, fill)}" font-weight="{"600" if bold else "400"}" '
               f'text-anchor="{anchor}"{a}>{esc(s)}</text>')


def rect(x, y, w, h, r=10, fill="#ffffff", stroke=None, sw=1.4, dash=None, filt=None):
    a = f' stroke="{C.get(stroke, stroke)}" stroke-width="{sw}"' if stroke else ""
    a += f' stroke-dasharray="{dash}"' if dash else ""
    a += f' filter="url(#{filt})"' if filt else ""
    out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
               f'rx="{r}" fill="{C.get(fill, fill)}"{a}/>')


def path(d, stroke=None, fill="none", sw=1.4, dash=None):
    a = f' stroke="{C.get(stroke, stroke)}" stroke-width="{sw}"' if stroke else ""
    a += f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<path d="{d}" fill="{C.get(fill, fill)}"{a} '
               f'stroke-linejoin="round" stroke-linecap="round"/>')


GLYPH = {
    "shield": '<path d="M12 2.5 20.5 6v6.5c0 5-3.7 8.8-8.5 10-4.8-1.2-8.5-5-8.5-10V6z" '
              'fill="none" stroke-width="2"/>'
              '<rect x="9" y="10.5" width="6" height="5" rx="1" fill="currentColor" '
              'stroke="none"/><path d="M10.2 10.5V9a1.8 1.8 0 0 1 3.6 0v1.5" '
              'fill="none" stroke-width="1.6"/>',
    "wave": '<g stroke-linecap="round" stroke-width="2">'
            '<path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/></g>',
    "assist": '<rect x="4.5" y="9.5" width="15" height="10.5" rx="2" fill="none" '
              'stroke-width="2"/><path d="M8 9.5V7a4 4 0 0 1 8 0v2.5" fill="none" '
              'stroke-width="2"/><path d="M12 12.8v3.6M10.2 14.6h3.6" stroke-width="1.9"/>',
    "stack": '<path d="M12 3 21 8l-9 5-9-5z" fill="none" stroke-width="2" '
             'stroke-linejoin="round"/><path d="m3 12.5 9 5 9-5" fill="none" '
             'stroke-width="1.8" stroke-linejoin="round"/>'
             '<path d="m3 16.8 9 5 9-5" fill="none" stroke-width="1.8" '
             'stroke-linejoin="round"/>',
}


def icon(x, y, size, bg, glyph, r=8):
    rect(x, y, size, size, r, bg, filt="ic")
    s = (size - 10) / 24
    out.append(f'<g transform="translate({x + 5:.1f},{y + 5:.1f}) scale({s:.3f})" '
               f'fill="#ffffff" stroke="#ffffff" stroke-linejoin="round" '
               f'stroke-linecap="round" color="{C.get(bg, bg)}">{GLYPH[glyph]}</g>')


def chip(x, y, label, fill, fs=9.5):
    cw = tw(label, fs, True) + 18
    rect(x, y, cw, 16, 8, fill)
    text(x + cw / 2, y + 11.5, label, fs, "#ffffff", bold=True, anchor="middle",
         ls="0.06em")
    return cw


COL_W, CARD_H, CARD_GAP = 443, 96, 12
GUTTER = 40                      # the step-number column inside each card


def card(x, y, step, title, lines, size, accent, bg):
    """One piece of work, or one gate.

    A gate is tinted and outlined in the workstream colour. It is not a component
    and must not read as one: it is a decision or a measurement that stops
    everything below it, and code cannot route around it.
    """
    gate = size == "GATE"
    rect(x, y, COL_W, CARD_H, 10, bg if gate else "#ffffff",
         accent if gate else "hair", 1.6 if gate else 1.2,
         "6 5" if size == "COND" else None, filt=None if gate else "sh")
    text(x + 20, y + 30, str(step), 15, accent if gate else "grey", bold=True)
    cw = chip(x + COL_W - 16 - (tw(size, 9.5, True) + 18), y + 16,
              size, accent if gate else "grey")
    fit(title, 12.5, COL_W - GUTTER - 30 - cw, f"card {title}", True)
    text(x + GUTTER, y + 30, title, 12.5, accent, bold=True, ls="0.02em")
    ly = y + 56
    for ln in lines:
        fit(ln, 11, COL_W - GUTTER - 20, f"cardline {title}")
        text(x + GUTTER, ly, ln, 11, "body")
        ly += 17
    vfit(ly - 17, y + CARD_H, f"card {title}", pad=8)


out.append(f'''<defs>
  <filter id="sh" x="-6%" y="-12%" width="112%" height="126%">
    <feDropShadow dx="0" dy="1.4" stdDeviation="2.2" flood-color="#0d2242"
                  flood-opacity="0.10"/></filter>
  <filter id="ic" x="-24%" y="-24%" width="148%" height="148%">
    <feDropShadow dx="0" dy="1.4" stdDeviation="1.8" flood-color="#0d2242"
                  flood-opacity="0.22"/></filter>
</defs>''')
out.append(f'<rect width="100%" height="100%" fill="{C["page"]}"/>')

text(24, 46, "NanoVox — Road to Production", 22, "ink", bold=True)
text(24, 70, "What the unbuilt capabilities actually contain. Order runs down a "
             "column; the four columns run in parallel", 13, "muted")

COLUMNS = [
    ("COMPLIANCE & ACCESS", "before any real call", "red", "red_bg", "shield", [
        ("PHI REDACTION ADAPTER", "M",
         ["Presidio or Azure AI Language behind the existing port.",
          "Reversible tokens so screens re-hydrate; fails closed"]),
        ("BAA IN PLACE", "GATE",
         ["Signed with the provider, or routed via a cloud that",
          "already holds one. Lead time, no engineering content"]),
        ("CONSENT & NOTICE", "GATE",
         ["Jurisdiction map, recording notice, decline flag.",
          "Two-party-consent states differ"]),
        ("FAIL-CLOSED PROVIDER GATE", "S",
         ["If the redactor is inactive, only local providers",
          "are selectable"]),
        ("AUTHENTICATION & RBAC", "L",
         ["Entra SSO and six defined roles; today the seam",
          "sits unused at the API boundary"]),
     ]),
    ("VOICE INGESTION", "before it can hear a call", "navy", "navy_bg", "wave", [
        ("TELEPHONY INTEGRATION", "M",
         ["Native dual-channel media stream — agent and member",
          "arrive on separate channels"]),
        ("STREAMING ASR + VOCABULARY", "L",
         ["Plan names, drugs, CARC codes and provider names as",
          "phrase lists from day one"]),
        ("WER MEASURED ON REAL CALLS", "GATE",
         ["100 labelled calls before committing to a vendor. A",
          "studio-audio demo is not evidence at 8 kHz"]),
        ("NORMALISATION", "S",
         ["Numbers, dates and plan codes into a single form",
          "before analysis"]),
        ("SPEAKER SEPARATION", "COND",
         ["Only for mono archive recordings. Dual-channel live",
          "audio removes the need — procure, do not build"]),
     ]),
    ("REAL-TIME LANE", "on top of a working transcript", "orange", "orange_bg",
     "assist", [
        ("KNOWLEDGE BASE & RETRIEVAL", "L",
         ["Ingest, chunk, embed, index. Every answer cited to",
          "an approved document"]),
        ("CONTENT COVERAGE PER INTENT", "GATE",
         ["A gap in approved content is a gap in capability,",
          "not a degraded answer"]),
        ("ASSIST RULES ENGINE", "M",
         ["Seeded from the assist layer's own should-have-fired",
          "findings — the rule set already exists"]),
        ("AGENT ASSIST PANEL", "M",
         ["The card on the agent's desktop, with citations and",
          "dismissal memory"]),
        ("ESCALATION & ALERTING", "M",
         ["Supervisor notified when risk crosses a set line —",
          "listen in, or step in"]),
     ]),
    ("PLATFORM & OPERATIONS", "runs alongside; blocked by nothing", "green",
     "green_bg", "stack", [
        ("DATABASE MIGRATION", "M",
         ["SQLite to Postgres; the repository interfaces",
          "already isolate this"]),
        ("RETENTION JOBS", "M",
         ["Per data class, on a schedule. Audio is the shortest",
          "window and the highest risk"]),
        ("FULL AUDIT SCOPE", "L",
         ["Hash-chained and append-only; every data access with",
          "its purpose, not model calls alone"]),
        ("EGRESS, DLP & INJECTION DEFENCE", "L",
         ["Allow-listed destinations, output scanning, content",
          "treated as data and never as instruction"]),
        ("TENANT ISOLATION", "S",
         ["Row-level security bound to the token claim; the",
          "column is already on every row"]),
     ]),
]

CX0, CGAP, CARD_TOP = 24, 20, 186
for ci, (name, sub, accent, bg, glyph, cards) in enumerate(COLUMNS):
    cx = CX0 + ci * (COL_W + CGAP)
    icon(cx, 112, 34, accent, glyph)
    fit(name, 13.5, COL_W - 48, f"col {name}", True)
    text(cx + 46, 128, name, 13.5, accent, bold=True, ls="0.05em")
    fit(sub, 11, COL_W - 48, f"colsub {name}")
    text(cx + 46, 146, sub, 11, "muted")
    for si, (title, size, lines) in enumerate(cards):
        card(cx, CARD_TOP + si * (CARD_H + CARD_GAP), si + 1, title, lines, size,
             accent, bg)

STACK_BOTTOM = CARD_TOP + len(COLUMNS[0][5]) * (CARD_H + CARD_GAP) - CARD_GAP

# ------------------------------------------------------------------ legend ---
LY, LH = STACK_BOTTOM + 24, 108
rect(CX0, LY, 4 * COL_W + 3 * CGAP, LH, 12, "grey_bg", "grey_bd", 1.4)
_lx = CX0 + 24
for label, fill, meaning in [
        ("S", "grey", "days"),
        ("M", "grey", "weeks"),
        ("L", "grey", "a month or more"),
        ("COND", "grey", "conditional — only if the archive is mono"),
        ("GATE", "red", "a decision or a measurement; it stops everything below it")]:
    cw = chip(_lx, LY + 22, label, fill)
    fit(meaning, 10.5, 400, f"key {label}")
    text(_lx + cw + 10, LY + 34, meaning, 10.5, "body")
    _lx += cw + 10 + tw(meaning, 10.5) + 28

for i, ln in enumerate([
        "Twenty items across four workstreams — sixteen pieces of work and four "
        "gates. Sizes are relative classes, not "
        "estimates — there are no weeks on this page, because sizing in weeks belongs "
        "to whoever owns delivery.",
        "Two of the four gates are contractual: they consume elapsed time without "
        "consuming engineering, so they start alongside the first build work rather "
        "than after it."]):
    fit(ln, 11.5, 4 * COL_W + 3 * CGAP - 48, f"legendline {i}")
    text(CX0 + 24, LY + 66 + i * 20, ln, 11.5, "body" if i == 0 else "ink")
vfit(LY + 66 + 20, LY + LH, "legend")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
       f'height="{H}" role="img" aria-label="Road to production: four parallel '
       f'workstreams as columns of cards, ordered top to bottom, with gates drawn '
       f'distinctly from components">\n' + "\n".join(out) + "\n</svg>\n")
dest = pathlib.Path("Gen Documents/15-road-to-production-diagram.svg")
dest.write_text(svg, encoding="utf-8")
ET.fromstring(svg)
print(f"wrote {dest} ({len(svg)} bytes) — XML OK")
print("\n".join(["FIT WARNINGS:"] + ["  - " + w for w in warn]) if warn
      else "no text-fit warnings")
