"""Generate the HIGH-LEVEL architecture diagram SVG (stakeholder / slide view).

Shape of the story: sources on the left, a privacy boundary nothing crosses
unredacted, then two lanes — one during the call, one after it — sharing a single
AI foundation, with findings from the slow lane feeding the fast one.

Run from the repo root:  python scripts/make_highlevel_diagram.py
Text fit is asserted, so a label that outgrows its box fails loudly.
"""
import pathlib
import xml.etree.ElementTree as ET

W, H = 1880, 1030
out = []

C = {
    "page": "#ffffff",
    "ink": "#16212e", "body": "#33414f", "muted": "#61707e", "hair": "#dfe5ec",
    "navy": "#143a6b", "navy_d": "#0d2b52", "navy_bg": "#f3f6fa", "navy_bd": "#c9d7e8",
    "orange": "#e8791a", "orange_d": "#b45c0c", "orange_bg": "#fdf7f0",
    "orange_bd": "#f3d0aa", "orange_chip": "#fdefdf",
    "green": "#1c7a4b", "green_d": "#14603a", "green_bg": "#f0f8f3",
    "green_bd": "#bcdcca", "green_chip": "#e6f3ec",
    "red": "#d92b2b", "red_bg": "#fdf3f3",
    "arrow": "#8fa0b3",
}
FONT = "'Segoe UI','Inter',-apple-system,'Helvetica Neue',Arial,sans-serif"
warn = []


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(s, fs, bold=False):
    base = 0.575 if bold else 0.525
    caps = sum(1 for ch in s if ch.isupper())     # capitals run wider
    return (len(s) * base + caps * 0.11) * fs


def fit(s, fs, avail, tag, bold=False):
    if tw(s, fs, bold) > avail:
        warn.append(f"{tag}: {s!r} {tw(s, fs, bold):.0f} > {avail:.0f}")


def text(x, y, s, fs=13, fill="body", bold=False, anchor="start", ls=None, rot=None):
    a = f' letter-spacing="{ls}"' if ls else ""
    if rot is not None:
        a += f' transform="rotate({rot}, {x:.1f}, {y:.1f})"'
    out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{fs}" '
               f'fill="{C.get(fill, fill)}" font-weight="{"600" if bold else "400"}" '
               f'text-anchor="{anchor}"{a}>{esc(s)}</text>')


def rect(x, y, w, h, r=10, fill="#ffffff", stroke=None, sw=1.4, dash=None, filt=None):
    a = f' stroke="{C.get(stroke, stroke)}" stroke-width="{sw}"' if stroke else ""
    a += f' stroke-dasharray="{dash}"' if dash else ""
    a += f' filter="url(#{filt})"' if filt else ""
    out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
               f'rx="{r}" fill="{C.get(fill, fill)}"{a}/>')


# ------------------------------------------------------------------- icons ---
GLYPH = {
    "phone": '<path d="M7 3h4l2 5-2.5 1.5a12 12 0 0 0 4 4L16 11l5 2v4a2 2 0 0 1-2 2'
             'A16 16 0 0 1 5 5a2 2 0 0 1 2-2z"/>',
    "folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4l2 2.5h9A1.5 1.5 0 0 1 21 9v9.5'
              'A1.5 1.5 0 0 1 19.5 20h-15A1.5 1.5 0 0 1 3 18.5z"/>',
    "chat": '<path d="M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-5 4v-4H4a1 1 0 0 1-1-1'
            'V6a1 1 0 0 1 1-1z"/>',
    "wave": '<g stroke-linecap="round" stroke-width="2">'
            '<path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/></g>',
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
    "db": '<ellipse cx="12" cy="6.2" rx="7.5" ry="2.9" fill="none" stroke-width="2"/>'
          '<path d="M4.5 6.2v11.6c0 1.6 3.4 2.9 7.5 2.9s7.5-1.3 7.5-2.9V6.2" '
          'fill="none" stroke-width="2"/>'
          '<path d="M4.5 12c0 1.6 3.4 2.9 7.5 2.9s7.5-1.3 7.5-2.9" fill="none" '
          'stroke-width="1.6"/>',
    "chart": '<rect x="3.5" y="4" width="17" height="16" rx="2" fill="none" '
             'stroke-width="2"/><path d="M7.5 15.5v-3M12 15.5v-6.5M16.5 15.5v-4.5" '
             'stroke-width="2" stroke-linecap="round"/>',
    "cloud": '<ellipse cx="10" cy="8.5" rx="6.2" ry="2.5" fill="none" stroke-width="1.9"/>'
             '<path d="M3.8 8.5v8.2c0 1.4 2.8 2.5 6.2 2.5s6.2-1.1 6.2-2.5V8.5" '
             'fill="none" stroke-width="1.9"/>'
             '<path d="M17.2 6.4a3 3 0 0 1 .3 6h-2.2" fill="none" stroke-width="1.7"/>',
}


def icon(x, y, size, bg, glyph, r=9):
    """A rounded tile with a white glyph, drawn from a 24x24 grid."""
    rect(x, y, size, size, r, bg, filt="ic")
    s = (size - 10) / 24
    out.append(f'<g transform="translate({x + 5:.1f},{y + 5:.1f}) scale({s:.3f})" '
               f'fill="#ffffff" stroke="#ffffff" stroke-linejoin="round" '
               f'stroke-linecap="round" color="{C.get(bg, bg)}">{GLYPH[glyph]}</g>')


# -------------------------------------------------------------- components ---
def source(x, y, w, h, title, lines, accent, dashed=False, glyph="phone"):
    rect(x, y, w, h, 12, "#ffffff", accent, 1.6, "7 5" if dashed else None, "sh")
    icon(x + 18, y + h / 2 - 22, 44, accent, glyph)
    fit(title, 15, w - 96, f"src {title}", True)
    text(x + 78, y + h / 2 - 12, title, 15, accent, bold=True, ls="0.02em")
    ly = y + h / 2 + 8
    for ln in lines:
        fit(ln, 12.5, w - 90, f"srcline {title}")
        text(x + 78, ly, ln, 12.5, "body")
        ly += 17


def lane(x, y, w, h, title, sub, bg, bd, tcol):
    rect(x, y, w, h, 16, bg, bd, 1.5)
    text(x + 26, y + 40, title, 17, tcol, bold=True, ls="0.06em")
    if sub:
        # tw() measures glyphs only; add the tracking back so "·" clears the title
        twid = tw(title, 17, True) + len(title) * 17 * 0.06
        text(x + 26 + twid + 20, y + 40, "·", 17, tcol, bold=True)
        text(x + 26 + twid + 38, y + 40, sub, 15, tcol, bold=True, ls="0.05em")


def cardbox(x, y, w, h, titles, lines, accent, glyph):
    rect(x, y, w, h, 11, "#ffffff", "hair", 1.3, filt="sh")
    icon(x + 18, y + 18, 40, accent, glyph, 8)
    ty = y + 36 if len(titles) == 1 else y + 30
    for tl in titles:
        fit(tl, 15, w - 88, f"card {tl}", True)
        text(x + 70, ty, tl, 15, accent, bold=True, ls="0.02em")
        ty += 19
    ly = ty + (12 if len(titles) == 1 else 10)
    for ln in lines:
        fit(ln, 12.5, w - 84, f"cardline {titles[0]}")
        text(x + 70, ly, ln, 12.5, "body")
        ly += 18


def arrow(pts, color="arrow", dashed=False, sw=2.1):
    col = C.get(color, color)
    mk = {"orange": "aO", "green": "aG", "red": "aR"}.get(color, "aN")
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{sw}" '
               f'stroke-linecap="round" stroke-linejoin="round"{dash} '
               f'marker-end="url(#{mk})"/>')


def mk(i, col):
    return (f'<marker id="{i}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.4" '
            f'markerHeight="6.4" orient="auto-start-reverse">'
            f'<path d="M 0 1.6 L 9 5 L 0 8.4 z" fill="{col}"/></marker>')


out.append(f'''<defs>
  <filter id="sh" x="-14%" y="-24%" width="128%" height="150%">
    <feDropShadow dx="0" dy="1.6" stdDeviation="2.6" flood-color="#0d2242"
                  flood-opacity="0.10"/></filter>
  <filter id="ic" x="-24%" y="-24%" width="148%" height="148%">
    <feDropShadow dx="0" dy="1.4" stdDeviation="1.8" flood-color="#0d2242"
                  flood-opacity="0.22"/></filter>
  {mk("aN", C["arrow"])}{mk("aO", C["orange"])}{mk("aG", C["green"])}{mk("aR", C["red"])}
</defs>''')
out.append(f'<rect width="100%" height="100%" fill="{C["page"]}"/>')

# ------------------------------------------------------------------ sources --
SX, SW = 24, 270
s1y, s2y, s3y, SH_ = 122, 288, 454, 104
source(SX, s1y, SW, SH_, "LIVE CALLS", ["Contact-Centre Platform"], "navy",
       glyph="phone")
source(SX, s2y, SW, SH_, "RECORDED CALLS",
       ["Recording Archive +", "Existing Transcripts"], "navy", glyph="folder")
source(SX, s3y, SW, SH_, "EMAIL · CHAT",
       ["Already Text — Joins at", "Redaction, Not Built Yet"], "navy", dashed=True,
       glyph="chat")

# ------------------------------------------------------------------ listen ---
LX, LY, LW, LH = 326, 138, 220, 404
rect(LX, LY, LW, LH, 12, "#ffffff", "navy", 1.6, filt="sh")
icon(LX + 20, LY + 22, 44, "navy", "wave")
text(LX + 78, LY + 42, "LISTEN & CONVERT", 15, "navy", bold=True, ls="0.02em")
text(LX + 78, LY + 61, "TO TEXT", 15, "navy", bold=True, ls="0.02em")
_ly = LY + 106
for grp in (["Streaming Speech-to-", "Text with Speaker", "Separation"],
            ["Member | Agent Kept", "as Separate Voices"],
            ["Numbers, Dates and", "Plan Codes Normalised"]):
    for ln in grp:
        fit(ln, 12.5, LW - 44, "listen")
        text(LX + 22, _ly, ln, 12.5, "body")
        _ly += 18
    _ly += 18

# ---------------------------------------------------------- privacy boundary --
PB = 574
text(PB, 36, "PRIVACY BOUNDARY", 16, "red", bold=True, anchor="middle", ls="0.06em")
text(PB, 60, "No Unredacted Text Crosses This Line", 13, "red", anchor="middle")

RX, RY, RW_, RH_ = 594, 244, 128, 192
rect(RX, RY, RW_, RH_, 12, "#ffffff", "red", 1.7, filt="sh")
icon(RX + RW_ / 2 - 24, RY + 20, 48, "red", "shield", 11)
text(RX + RW_ / 2, RY + 98, "REDACT", 15.5, "red", bold=True, anchor="middle",
     ls="0.03em")
for i, ln in enumerate(["Personal Details", "Masked Before", "Any Model Call"]):
    fit(ln, 12.5, RW_ - 14, "redact")
    text(RX + RW_ / 2, RY + 126 + i * 18, ln, 12.5, "body", anchor="middle")

# -------------------------------------------------------------------- lanes --
ZX, ZW = 742, 880
INSET = 22
c_g = 24
c_w = (ZW - 2 * INSET - 2 * c_g) / 3        # fills the lane exactly
cx = [ZX + INSET + i * (c_w + c_g) for i in range(3)]
assert abs(cx[2] + c_w - (ZX + ZW - INSET)) < 0.01, 'cards must fit the lane'

# Card height follows the content. cardbox() puts the first body line at
# y + 67 (title baseline 36, + 19 for the title row, + 12 leading) and steps 18
# per line.
LINE1, LINE_H, PAD = 67, 18, 18
CARD_H = LINE1 + 3 * LINE_H + PAD          # tallest case: four body lines
FCARD_H = LINE1 + 1 * LINE_H + PAD + 5     # foundation cards: two lines
TOP, BOT, GAP = 72, 28, 26

L1Y = 20
L1H = TOP + CARD_H + BOT
R1 = L1Y + TOP
FY = L1Y + L1H + GAP
FH = 52 + FCARD_H + 18
FR = FY + 52
L3Y = FY + FH + GAP
L3H = TOP + CARD_H + BOT
R3 = L3Y + TOP
LIVE_Y, POST_Y = R1 + 84, R3 + 84

lane(ZX, L1Y, ZW, L1H, "DURING THE CALL", "", "orange_bg", "orange_bd",
     "orange_d")
cardbox(cx[0], R1, c_w, CARD_H, ["UNDERSTAND"],
        ["Intent & Topic", "Mood Over Time", "Risk Signals"], "orange", "head")
cardbox(cx[1], R1, c_w, CARD_H, ["VERIFY"],
        ["Retrieve the Approved", "Answer, with Source", "Compliance by Rules,",
         "Never Guessed"], "orange", "check")
cardbox(cx[2], R1, c_w, CARD_H, ["ASSIST"],
        ["Guidance Card to", "the Agent's Desktop", "Escalate When Risk",
         "Crosses a Set Line"], "orange", "assist")

lane(ZX, FY, ZW, FH, "SHARED AI FOUNDATION", "USED BY BOTH LANES", "navy_bg",
     "navy_bd", "navy")
cardbox(cx[0], FR, 286, FCARD_H, ["LLM GATEWAY"],
        ["One Interface,", "Interchangeable Models"], "navy", "nodes")
cardbox(cx[0] + 306, FR, cx[2] + c_w - cx[0] - 306, FCARD_H,
        ["KNOWLEDGE BASE  ·  RAG"],
        ["Approved Plan Documents, Billing Rules, Procedures —",
         "Indexed for Retrieval; Only Approved Content Is Usable"], "navy", "book")

lane(ZX, L3Y, ZW, L3H, "AFTER THE CALL", "EVERY CALL, AT SCALE", "green_bg",
     "green_bd", "green_d")
cardbox(cx[0], R3, c_w, CARD_H, ["ANALYSE  ·  L1–L5"],
        ["What Happened, How", "Well It Was Handled,", "Score, Patterns,",
         "Root-Cause Signals"], "green", "analyse")
cardbox(cx[1], R3, c_w, CARD_H, ["INSIGHT STORE"],
        ["One Structured Record", "per Call — Queryable,", "Comparable, Auditable"],
        "green", "db")
cardbox(cx[2], R3, c_w, CARD_H, ["DASHBOARDS &", "ACTIONS"],
        ["Overview · Scorecards", "Follow-Up Queue", "Trends · Reports"],
        "green", "chart")

# ------------------------------------------------------------ data platform --
DPY, DPH = L3Y + L3H + GAP, 76
rect(ZX, DPY, ZW, DPH, 12, "#ffffff", "navy", 1.6, filt="sh")
icon(ZX + 20, DPY + 16, 44, "navy", "cloud", 11)
text(ZX + 78, DPY + 45, "DATA PLATFORM", 15.5, "navy", bold=True, ls="0.03em")
H = DPY + DPH + 22
out.append(f'<path d="M {PB} 78 L {PB} {DPY - 8}" stroke="{C["red"]}" '
           f'stroke-width="2" stroke-dasharray="9 7" opacity="0.9"/>')
# spread the three holdings across the bar instead of trailing off to the left
_items = ["Recordings & Transcripts", "Analyses & Events",
          "Warehouse — One Set of Numbers"]
_w = [tw(t, 12.5) for t in _items]
_x0, _x1 = ZX + 240, ZX + ZW - 26
_gap = (_x1 - _x0 - sum(_w)) / (len(_items) - 1)
assert _gap > 30, f"data-platform items are crowded: gap {_gap:.0f}"
_px = _x0
for _t, _tw in zip(_items, _w):
    text(_px, DPY + 45, _t, 12.5, "body")
    _px += _tw + _gap

# ----------------------------------------------------------------- plumbing --
arrow([(SX + SW, s1y + SH_ / 2), (LX - 5, s1y + SH_ / 2)], "navy")
arrow([(SX + SW, s2y + SH_ / 2), (LX - 5, s2y + SH_ / 2)], "navy")
arrow([(LX + LW, 340), (RX - 5, 340)], "navy")
# email needs no speech-to-text, so it bypasses that box entirely
EBY = 574
arrow([(SX + SW, s3y + SH_ / 2), (SX + SW + 16, s3y + SH_ / 2), (SX + SW + 16, EBY),
       (RX + RW_ / 2, EBY), (RX + RW_ / 2, RY + RH_ + 4)], "navy", dashed=True)

ELB = ZX - 12
arrow([(RX + RW_, 300), (ELB, 300), (ELB, LIVE_Y), (cx[0] - 6, LIVE_Y)], "orange",
      sw=2.4)
arrow([(RX + RW_, 380), (ELB, 380), (ELB, POST_Y), (cx[0] - 6, POST_Y)], "green",
      sw=2.4)
arrow([(cx[0] + c_w, LIVE_Y), (cx[1] - 6, LIVE_Y)], "orange", sw=2.4)
arrow([(cx[1] + c_w, LIVE_Y), (cx[2] - 6, LIVE_Y)], "orange", sw=2.4)
arrow([(cx[0] + c_w, POST_Y), (cx[1] - 6, POST_Y)], "green", sw=2.4)
arrow([(cx[1] + c_w, POST_Y), (cx[2] - 6, POST_Y)], "green", sw=2.4)

def tag(x, y, lab):
    w_ = tw(lab, 11.5) + 16
    rect(x, y - 11, w_, 19, 5, "#ffffff")
    text(x + 8, y + 2, lab, 11.5, "muted")


for lx_, lab, up in ((cx[0] + 118, "Fast Model", True), (cx[1] + 118, "Cited Facts", True),
                     (cx[0] + 118, "Deep Model", False),
                     (cx[1] + 118, "Policy Context", False)):
    # stop at the lane edges: running into the cards would cross the lane titles
    if up:
        arrow([(lx_, FY), (lx_, L1Y + L1H - 10)], dashed=True, sw=1.8)
        tag(lx_ + 10, FY - 9, lab)
    else:
        arrow([(lx_, FY + FH), (lx_, L3Y)], dashed=True, sw=1.8)
        tag(lx_ + 10, L3Y - 9, lab)

arrow([(LX + 180, LY + LH), (LX + 180, DPY - 16), (ZX + 40, DPY - 16),
       (ZX + 40, DPY - 6)], dashed=True, sw=1.8)
tag(LX + 190, DPY - 62, "Audio + Text Stored")
tag(LX + 6, EBY - 8, "Already Text, No Speech-to-Text")
arrow([(cx[1] + 118, L3Y + L3H), (cx[1] + 118, DPY - 6)], dashed=True, sw=1.8)

# ------------------------------------------------------------- who sees it ---
def dest(x, y, w, h, title, lines, accent, glyph, badge=None):
    rect(x, y, w, h, 12, "#ffffff", accent, 1.6, filt="sh")
    icon(x + w / 2 - 21, y + 16, 42, accent, glyph, 10)
    fit(title, 15, w - 24, f"dest {title}", True)
    text(x + w / 2, y + 78, title, 15, accent, bold=True, anchor="middle", ls="0.03em")
    ly = y + 98
    for ln in lines:
        fit(ln, 12, w - 22, f"destline {title}")
        text(x + w / 2, ly, ln, 12, "body", anchor="middle")
        ly += 17
    if badge:
        bw = tw(badge, 10.5, True) + 22
        rect(x + w / 2 - bw / 2, y - 10, bw, 20, 10, accent)
        text(x + w / 2, y + 4, badge, 10.5, "#ffffff", bold=True, anchor="middle",
             ls="0.06em")
    return {"x": x, "y": y, "w": w, "h": h, "cx": x + w / 2, "cy": y + h / 2,
            "b": y + h, "r": x + w}


PPX, PPW = ZX + ZW + 34, 200
text(PPX + PPW / 2, 46, "WHO SEES IT", 11, "muted", bold=True, anchor="middle",
     ls="0.12em")
sv = dest(PPX, R1 + CARD_H / 2 - 82, PPW, 164, "SUPERVISOR",
          ["Alert on the Dashboard", "and a Notification —", "Listen In, or Step In"],
          "red", "bell", badge="ESCALATION")
# leadership reads the dashboards, so the arrow leaves the post-call lane
ld = dest(PPX, R3 + CARD_H / 2 - 75, PPW, 150, "LEADERSHIP",
          ["Dashboards and", "Scorecards — Trends,", "Topics, Agent Quality"],
          "green", "chart")
arrow([(cx[2] + c_w, sv["cy"]), (sv["x"] - 6, sv["cy"])], "red", sw=2.4)
arrow([(cx[2] + c_w, ld["cy"]), (ld["x"] - 6, ld["cy"])], "green", sw=2.2)
_lab = "Risk Crosses the Line"
_lw = tw(_lab, 11) + 16
_lx = (cx[2] + c_w + sv["x"]) / 2 - _lw / 2
rect(_lx, sv["cy"] - 32, _lw, 19, 5, "#ffffff")
text(_lx + 8, sv["cy"] - 19, _lab, 11, "red")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
       f'height="{H}" role="img" aria-label="High-level architecture: sources, privacy '
       f'boundary, live lane and post-call lane over a shared AI foundation">\n'
       + "\n".join(out) + "\n</svg>\n")
dest = pathlib.Path("Gen Documents/10-high-level-diagram.svg")
dest.write_text(svg, encoding="utf-8")
ET.fromstring(svg)
print(f"wrote {dest} ({len(svg)} bytes) — XML OK")
print("\n".join(["FIT WARNINGS:"] + ["  - " + w for w in warn]) if warn
      else "no text-fit warnings")
