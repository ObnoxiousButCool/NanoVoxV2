"""Generate the PRODUCT ARCHITECTURE diagram SVG (capability / stakeholder view).

Different question from the other two diagrams in this folder. `make_highlevel_
diagram.py` answers *how does a call become a score* and `make_architecture_
diagram.py` answers *what runs where*. This one answers **what the product is
made of, who each part serves, and which parts actually exist today** — the view
a client asks for when deciding what to buy, not how to host it.

Shape of the story: channels on the left, five capability bands stacked so that
the lower a band sits the more of the product rests on it, audiences on the
right. Every capability carries a build status, because a product architecture
that draws designed and delivered capabilities identically is a sales document,
not an architecture.

Run from the repo root:  python scripts/make_product_diagram.py
Text fit is asserted, so a label that outgrows its box fails loudly.
"""
import pathlib
import xml.etree.ElementTree as ET

W, H = 1880, 1120
out = []

C = {
    "page": "#ffffff",
    "ink": "#16212e", "body": "#33414f", "muted": "#61707e", "hair": "#dfe5ec",
    "navy": "#143a6b", "navy_d": "#0d2b52", "navy_bg": "#f3f6fa", "navy_bd": "#c9d7e8",
    "orange": "#e8791a", "orange_d": "#b45c0c", "orange_bg": "#fdf7f0",
    "orange_bd": "#f3d0aa",
    "green": "#1c7a4b", "green_d": "#14603a", "green_bg": "#f0f8f3",
    "green_bd": "#bcdcca",
    "red": "#d92b2b", "red_d": "#a81f1f", "red_bg": "#fdf3f3", "red_bd": "#f0c6c6",
    "grey": "#9aa8b6", "grey_bg": "#f7f9fb", "grey_bd": "#dde4ec",
    "arrow": "#8fa0b3",
}
FONT = "'Segoe UI','Inter',-apple-system,'Helvetica Neue',Arial,sans-serif"
warn = []

# Build status. The whole point of this diagram, so it is a named vocabulary
# rather than three ad-hoc colours: LIVE is running in this build, NEXT has a
# seam in the code and no implementation behind it, LATER is designed only.
STATUS = {"live": "green", "next": "orange", "later": "grey"}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(s, fs, bold=False):
    base = 0.575 if bold else 0.525
    caps = sum(1 for ch in s if ch.isupper())     # capitals run wider
    return (len(s) * base + caps * 0.11) * fs


def fit(s, fs, avail, tag, bold=False):
    if tw(s, fs, bold) > avail:
        warn.append(f"{tag}: {s!r} {tw(s, fs, bold):.0f} > {avail:.0f}")


def vfit(bottom, limit, tag, pad=12):
    """Assert a box's content stops short of its own floor.

    ``fit`` measures width only, which is how a paragraph once ran four pixels
    out through the bottom of the tally box without the build saying a word.
    Any box whose contents grow by a line needs this as well.
    """
    if bottom > limit - pad:
        warn.append(f"{tag}: content reaches {bottom:.0f}, box floor {limit:.0f}")


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


def circle(cx, cy, r, fill):
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
               f'fill="{C.get(fill, fill)}"/>')


# ------------------------------------------------------------------- icons ---
GLYPH = {
    "phone": '<path d="M7 3h4l2 5-2.5 1.5a12 12 0 0 0 4 4L16 11l5 2v4a2 2 0 0 1-2 2'
             'A16 16 0 0 1 5 5a2 2 0 0 1 2-2z"/>',
    "chat": '<path d="M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-5 4v-4H4a1 1 0 0 1-1-1'
            'V6a1 1 0 0 1 1-1z"/>',
    "shield": '<path d="M12 2.5 20.5 6v6.5c0 5-3.7 8.8-8.5 10-4.8-1.2-8.5-5-8.5-10V6z" '
              'fill="none" stroke-width="2"/>'
              '<rect x="9" y="10.5" width="6" height="5" rx="1" fill="currentColor" '
              'stroke="none"/><path d="M10.2 10.5V9a1.8 1.8 0 0 1 3.6 0v1.5" '
              'fill="none" stroke-width="1.6"/>',
    "head": '<path d="M15.5 20.5v-2.2a5.6 5.6 0 0 0 3.4-5.1c0-3.4-2.9-6.2-6.4-6.2'
            'S6 9.8 6 13.2a5.6 5.6 0 0 0 1.9 4.2v3.1" fill="none" stroke-width="2"/>'
            '<path d="M10 12.6c1-.9 2.2-.9 3 0s2 .9 3 0" fill="none" stroke-width="1.8"/>'
            '<path d="M12.5 7V4M9 5 7.6 3M16 5l1.4-2" fill="none" stroke-width="1.8"/>',
    "check": '<circle cx="10.5" cy="10.5" r="6.6" fill="none" stroke-width="2"/>'
             '<path d="m7.8 10.6 2 2 3.4-3.8" fill="none" stroke-width="2"/>'
             '<path d="m15.4 15.4 4.4 4.4" fill="none" stroke-width="2.2"/>',
    "assist": '<rect x="4.5" y="9.5" width="15" height="10.5" rx="2" fill="none" '
              'stroke-width="2"/><path d="M8 9.5V7a4 4 0 0 1 8 0v2.5" fill="none" '
              'stroke-width="2"/><path d="M12 12.8v3.6M10.2 14.6h3.6" stroke-width="1.9"/>',
    "monitor": '<rect x="3" y="4.5" width="18" height="12" rx="2" fill="none" '
               'stroke-width="2"/><path d="M9 20h6M12 16.5V20" stroke-width="1.9"/>',
    "bell": '<path d="M12 3.2a6 6 0 0 0-6 6v3.9l-2 3.1h16l-2-3.1V9.2a6 6 0 0 0-6-6z" '
            'fill="none" stroke-width="2" stroke-linejoin="round"/>'
            '<path d="M9.8 19.2a2.2 2.2 0 0 0 4.4 0" fill="none" stroke-width="2"/>',
    "nodes": '<circle cx="12" cy="12" r="2.6" fill="none" stroke-width="2"/>'
             '<circle cx="4.6" cy="6" r="2.1" fill="none" stroke-width="1.9"/>'
             '<circle cx="19.4" cy="6" r="2.1" fill="none" stroke-width="1.9"/>'
             '<circle cx="4.6" cy="18" r="2.1" fill="none" stroke-width="1.9"/>'
             '<circle cx="19.4" cy="18" r="2.1" fill="none" stroke-width="1.9"/>'
             '<path d="m6.4 7.4 3.4 3.1M17.6 7.4l-3.4 3.1M6.4 16.6l3.4-3.1'
             'M17.6 16.6l-3.4-3.1" stroke-width="1.6"/>',
    "book": '<path d="M12 6.5C10.3 5 7.8 4.4 4 4.6v13.2c3.8-.2 6.3.4 8 1.9 1.7-1.5 '
            '4.2-2.1 8-1.9V4.6c-3.8-.2-6.3.4-8 1.9z" fill="none" stroke-width="2"/>'
            '<path d="M12 6.5v13" stroke-width="1.6"/>',
    "analyse": '<circle cx="10.5" cy="10.5" r="6.6" fill="none" stroke-width="2"/>'
               '<path d="m7.2 11.4 2-2.6 2 3 2.2-3.4" fill="none" stroke-width="1.8"/>'
               '<path d="m15.4 15.4 4.4 4.4" fill="none" stroke-width="2.2"/>',
    "chart": '<rect x="3.5" y="4" width="17" height="16" rx="2" fill="none" '
             'stroke-width="2"/><path d="M7.5 15.5v-3M12 15.5v-6.5M16.5 15.5v-4.5" '
             'stroke-width="2" stroke-linecap="round"/>',
    "stack": '<path d="M12 3 21 8l-9 5-9-5z" fill="none" stroke-width="2" '
             'stroke-linejoin="round"/><path d="m3 12.5 9 5 9-5" fill="none" '
             'stroke-width="1.8" stroke-linejoin="round"/>'
             '<path d="m3 16.8 9 5 9-5" fill="none" stroke-width="1.8" '
             'stroke-linejoin="round"/>',
}


def icon(x, y, size, bg, glyph, r=9):
    """A rounded tile with a white glyph, drawn from a 24x24 grid."""
    rect(x, y, size, size, r, bg, filt="ic")
    s = (size - 10) / 24
    out.append(f'<g transform="translate({x + 5:.1f},{y + 5:.1f}) scale({s:.3f})" '
               f'fill="#ffffff" stroke="#ffffff" stroke-linejoin="round" '
               f'stroke-linecap="round" color="{C.get(bg, bg)}">{GLYPH[glyph]}</g>')


def arrow(pts, color="arrow", sw=2.1):
    d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    out.append(f'<path d="{d}" fill="none" stroke="{C.get(color, color)}" '
               f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
               f'marker-end="url(#aN)"/>')


# -------------------------------------------------------------- components ---
def tile(x, y, w, h, title, lines, accent, status):
    """One capability. A LATER capability is drawn dashed and greyed.

    Status is carried by three signals at once — dot, border and title colour —
    so the diagram survives being printed in monochrome and being read by
    someone who does not consult the legend.
    """
    later = status == "later"
    rect(x, y, w, h, 9, "#ffffff", "grey_bd" if later else "hair", 1.2,
         "5 4" if later else None, filt=None if later else "sh")
    circle(x + w - 15, y + 15, 4.5, STATUS[status])
    fit(title, 12.5, w - 44, f"tile {title}", True)
    text(x + 14, y + 27, title, 12.5, "grey" if later else accent, bold=True,
         ls="0.02em")
    ly = y + 51
    for ln in lines:
        fit(ln, 11, w - 28, f"tileline {title}")
        text(x + 14, ly, ln, 11, "muted" if later else "body")
        ly += 15


def band(x, y, w, h, name, sub, bg, bd, accent, glyph, tiles, note=None):
    """A capability layer, plus the tiles that make it up.

    ``note`` is set on the trust band alone, to say out loud that its tiles are a
    selection rather than the whole control set. Without it the band reads as a
    complete security posture, which would be the most misleading thing on the page.
    """
    rect(x, y, w, h, 14, bg, bd, 1.5)
    icon(x + 20, y + 12, 34, accent, glyph, 8)
    fit(name, 14.5, 320, f"band {name}", True)
    text(x + 64, y + 34, name, 14.5, accent, bold=True, ls="0.07em")
    nw = tw(name, 14.5, True) + len(name) * 14.5 * 0.07
    text(x + 64 + nw + 16, y + 34, "·", 14.5, accent, bold=True)
    text(x + 64 + nw + 32, y + 34, sub, 12.5, accent)
    if note:
        fit(note, 11.5, w / 2, f"bandnote {name}")
        text(x + w - 20, y + 34, note, 11.5, "muted", anchor="end")

    inset, gap = 20, 18
    tw_ = (w - 2 * inset - (len(tiles) - 1) * gap) / len(tiles)
    for i, (title, lines, status) in enumerate(tiles):
        tile(x + inset + i * (tw_ + gap), y + 56, tw_, h - 66, title, lines,
             accent, status)


def channel(x, y, w, h, title, lines, accent, status, glyph):
    later = status == "later"
    rect(x, y, w, h, 12, "#ffffff", "grey_bd" if later else accent, 1.6,
         "7 5" if later else None, filt=None if later else "sh")
    icon(x + 16, y + 16, 38, "grey" if later else accent, glyph, 8)
    circle(x + w - 18, y + 20, 4.5, STATUS[status])
    fit(title, 13, w - 32, f"chan {title}", True)
    text(x + 16, y + 76, title, 13, "grey" if later else accent, bold=True, ls="0.02em")
    ly = y + 98
    for ln in lines:
        fit(ln, 11.5, w - 32, f"chanline {title}")
        text(x + 16, ly, ln, 11.5, "muted" if later else "body")
        ly += 17


def persona(x, y, w, h, title, lines, accent, status, glyph):
    """One audience. Deliberately the same height and pitch as a channel card, so
    the two outer columns read as a matched pair either side of the bands."""
    later = status == "later"
    rect(x, y, w, h, 12, "#ffffff", "grey_bd" if later else "hair", 1.4,
         "6 5" if later else None, filt=None if later else "sh")
    icon(x + w / 2 - 19, y + 14, 38, "grey" if later else accent, glyph, 9)
    circle(x + w - 18, y + 20, 4.5, STATUS[status])
    fit(title, 13.5, w - 24, f"persona {title}", True)
    text(x + w / 2, y + 76, title, 13.5, "grey" if later else accent, bold=True,
         anchor="middle", ls="0.03em")
    ly = y + 98
    for ln in lines:
        fit(ln, 11.5, w - 22, f"personaline {title}")
        text(x + w / 2, ly, ln, 11.5, "muted" if later else "body", anchor="middle")
        ly += 17


out.append(f'''<defs>
  <filter id="sh" x="-14%" y="-24%" width="128%" height="150%">
    <feDropShadow dx="0" dy="1.6" stdDeviation="2.6" flood-color="#0d2242"
                  flood-opacity="0.10"/></filter>
  <filter id="ic" x="-24%" y="-24%" width="148%" height="148%">
    <feDropShadow dx="0" dy="1.4" stdDeviation="1.8" flood-color="#0d2242"
                  flood-opacity="0.22"/></filter>
  <marker id="aN" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.4"
          markerHeight="6.4" orient="auto-start-reverse">
    <path d="M 0 1.6 L 9 5 L 0 8.4 z" fill="{C["arrow"]}"/></marker>
</defs>''')
out.append(f'<rect width="100%" height="100%" fill="{C["page"]}"/>')

# ------------------------------------------------------------------ header ---
text(24, 46, "NanoVox — Product Architecture", 22, "ink", bold=True)
# "Proof of concept" leads the subtitle rather than sitting in a footnote. The
# title is a fair claim — the *architecture* is a product architecture — but the
# green dots are not, unless the reader is told what has actually been built.
text(24, 70, "Proof of concept — what the product is made of, who each part serves, "
             "and what is built so far", 13, "muted")

# No status legend here. The three marks are defined once, in the tally box at the
# foot of the right-hand column — stating them in a header strip as well, and again
# beside the reading notes, made the diagram look like it was explaining itself
# three times instead of saying anything.

# ---------------------------------------------------------------- channels ---
CHX, CHW = 24, 250
text(CHX + CHW / 2, 112, "WHERE IT COMES FROM", 11, "muted", bold=True,
     anchor="middle", ls="0.12em")
CH = [
    ("PASTED TRANSCRIPT", ["One call, analysed on", "demand from the UI"],
     "live", "book"),
    ("RECORDED & LIVE CALLS", ["Needs speech-to-text", "before it can join"],
     "later", "phone"),
    ("EMAIL & CHAT", ["Already text — joins the", "same pipeline at redaction"],
     "later", "chat"),
]
# Card height and pitch are shared with the persona column below, so the two outer
# columns read as a matched pair either side of the bands.
COL_H, COL_PITCH, BOX_Y, BOX_H = 160, 182, 692, 400
for i, (t, ls_, st, g) in enumerate(CH):
    channel(CHX, 132 + i * COL_PITCH, CHW, COL_H, t, ls_, "navy", st, g)

# ------------------------------------------------------- how to read this ----
NX, NY, NW = CHX, BOX_Y, CHW
rect(NX, NY, NW, BOX_H, 12, "navy_bg", "navy_bd", 1.4)
text(NX + 18, NY + 34, "HOW TO READ THIS", 11, "navy", bold=True, ls="0.12em")
_ny = NY + 68
for ln in ["Bands are capability layers.",
           "The lower a band sits, the",
           "more of the product rests",
           "on it.",
           "",
           "Nothing should reach a model",
           "call without passing the",
           "trust layer. Today that layer",
           "is a seam, not a control.",
           "",
           "Email and chat are already",
           "text, so they skip straight",
           "to redaction — a channel, not",
           "a second product."]:
    if ln:
        fit(ln, 11.5, NW - 36, "note")
        text(NX + 18, _ny, ln, 11.5, "body")
    _ny += 18
vfit(_ny - 18, NY + BOX_H, "how-to-read box")

# ------------------------------------------------------------------- bands ---
BX, BW, BH, BGAP = 300, 1290, 176, 20
BANDS = [
    ("EXPERIENCE", "what people touch", "navy_bg", "navy_bd", "navy", "monitor", [
        ("DASHBOARD", ["Where we stand, and the", "detail behind it"], "live"),
        ("INFERENCES", ["What the calls add up to,", "ranked with an owner"], "live"),
        ("CALL EXPLORER", ["Every call, with the quote", "behind each judgement"], "live"),
        ("BROKER SCORECARD", ["Conduct signals members", "named aloud"], "live"),
        ("AGENT ASSIST", ["Guidance card on the", "desktop, mid-call"], "later"),
    ]),
    ("ACTION & OUTCOME", "what changes because of it", "green_bg", "green_bd",
     "green", "check", [
        ("AGENT SCORECARD", ["A score with evidence", "behind every marker"], "live"),
        ("RANKED ACTIONS", ["Findings with an owner,", "not a wall of charts"], "live"),
        ("TREND & ROOT CAUSE", ["Repeat drivers across calls,", "not one at a time"], "live"),
        ("MEMBER AT RISK", ["Churn signals surfaced", "before renewal"], "next"),
        ("ESCALATION", ["Notify when risk crosses", "a set line"], "later"),
    ]),
    ("INTELLIGENCE", "five layers, one model call each", "orange_bg", "orange_bd",
     "orange", "analyse", [
        ("L1 · UNDERSTANDING", ["Call type, caller, tone,", "duration"], "live"),
        ("L2 · CALL INSIGHTS", ["What happened, and whether", "it was resolved"], "live"),
        ("L3 · AGENT QUALITY", ["Evidence markers — the", "rubric does the arithmetic"], "live"),
        ("L4 · OPERATIONAL BI", ["The systemic issue, its", "owner and a recommendation"], "live"),
        ("L5 · REAL-TIME ASSIST", ["What fired — or should have", "fired, and did not"], "live"),
    ]),
    ("FOUNDATION", "what every capability runs on", "navy_bg", "navy_bd",
     "navy_d", "stack", [
        ("LLM GATEWAY", ["One interface — Ollama,", "OpenAI, Anthropic"], "live"),
        ("SCORING RUBRIC", ["Config-driven weights; same", "call, same score"], "live"),
        ("INSIGHT STORE", ["One structured record per", "call — queryable, auditable"], "live"),
        ("KNOWLEDGE BASE · RAG", ["Approved answers, cited to", "a document"], "later"),
        ("SPEECH TO TEXT", ["Speaker-separated, live", "and batch"], "later"),
    ]),
    ("TRUST & GOVERNANCE", "the floor everything stands on", "red_bg", "red_bd",
     "red", "shield", [
        ("PHI REDACTION", ["Seam exists and is called —", "no-op until built"], "next"),
        ("PROVIDER GATING", ["Only BAA-covered", "providers for real data"], "next"),
        ("CONSENT & NOTICE", ["Recording and AI notice;", "jurisdictions differ"], "later"),
        ("MODEL CALL AUDIT", ["Provider, model, prompt", "recorded per call"], "live"),
        ("DATA RESIDENCY", ["A local-only lane —", "nothing leaves the tenant"], "live"),
        ("ACCESS CONTROL", ["Role-scoped access and", "an access audit trail"], "later"),
    ], "9 further controls specified separately"),
]
_by = 132
band_y = []
for _b in BANDS:
    band(BX, _by, BW, BH, *_b)
    band_y.append(_by)
    _by += BH + BGAP

# ---------------------------------------------------------------- personas ---
PX, PW, PH = 1614, 242, COL_H
text(PX + PW / 2, 112, "WHO IT SERVES", 11, "muted", bold=True, anchor="middle",
     ls="0.12em")
PE = [
    ("AGENT", ["Live guidance while", "the call is happening"], "navy", "later",
     "assist"),
    ("SUPERVISOR", ["Every call scored, not a", "sample — alerting later"],
     "green", "live", "bell"),
    ("LEADERSHIP", ["Trends, topics and agent", "quality — one set of numbers"],
     "green", "live", "chart"),
]
for i, (t, ls_, acc, st, g) in enumerate(PE):
    persona(PX, 132 + i * COL_PITCH, PW, PH, t, ls_, acc, st, g)

# ------------------------------------------------------ where this stands ----
# The single place the three status marks are defined, and the only place they are
# counted. It is both the legend and the tally on purpose: a reader who sees the
# dots on the tiles should learn what they mean and what they add up to at once,
# and should not have to meet the same three words in three corners of the page.
# Sized to its own content rather than to the left-hand box: with the commentary
# gone it holds a title and three rows, and stretching it to the band floor would
# leave a third of it empty. The two boxes share a top edge, not a bottom one.
SX_, SY, SW_, TALLY_H = PX, BOX_Y, PW, 232
rect(SX_, SY, SW_, TALLY_H, 12, "grey_bg", "grey_bd", 1.4)
text(SX_ + 18, SY + 34, "WHERE THIS BUILD STANDS", 11, "ink", bold=True, ls="0.09em")
# Indexed, not unpacked from the tail: the trust band carries a trailing note, so
# `*_, tiles` would count the note string instead of the tiles.
TILES_IDX = 6
_tally = {"live": 0, "next": 0, "later": 0}
for _b in BANDS:
    for _, _, st in _b[TILES_IDX]:
        _tally[st] += 1
for i, (st, lbl, why) in enumerate([
        # "in the POC" is the whole point of this line: a green dot means running
        # against a synthetic corpus on localhost, not running in production.
        ("live", "LIVE", ["Built and running", "in the POC"]),
        ("next", "NEXT", ["Seam exists, nothing yet"]),
        ("later", "LATER", ["Designed, not started"])]):
    ry = SY + 80 + i * 58
    circle(SX_ + 24, ry - 7, 4.5, STATUS[st])
    text(SX_ + 40, ry, str(_tally[st]), 21, STATUS[st], bold=True)
    text(SX_ + 74, ry - 8, lbl, 11, "body", bold=True, ls="0.06em")
    for j, ln in enumerate(why):
        fit(ln, 11, SW_ - 92, "tally")
        text(SX_ + 74, ry + 8 + j * 14, ln, 11, "muted")
    vfit(ry + 8 + (len(why) - 1) * 14, SY + TALLY_H, "tally box")

# ------------------------------------------------------------------ arrows ---
# Channels feed the intelligence layer; the experience layer is what reaches people.
arrow([(CHX + CHW + 6, band_y[2] + BH / 2), (BX - 8, band_y[2] + BH / 2)], sw=2.3)
arrow([(BX + BW + 6, band_y[0] + BH / 2), (PX - 8, band_y[0] + BH / 2)], sw=2.3)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
       f'height="{H}" role="img" aria-label="Product architecture: channels, five '
       f'capability layers from experience down to trust and governance, and the '
       f'audiences each serves, with build status per capability">\n'
       + "\n".join(out) + "\n</svg>\n")
dest = pathlib.Path("Gen Documents/13-product-architecture-diagram.svg")
dest.write_text(svg, encoding="utf-8")
ET.fromstring(svg)
print(f"wrote {dest} ({len(svg)} bytes) — XML OK")
print("\n".join(["FIT WARNINGS:"] + ["  - " + w for w in warn]) if warn
      else "no text-fit warnings")
