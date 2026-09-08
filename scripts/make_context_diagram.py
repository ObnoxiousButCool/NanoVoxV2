"""Generate the PRODUCT CONTEXT diagram SVG — everything around the product.

Companion to `make_product_diagram.py`. That one draws what NanoVox *is*; this one
draws what it sits inside: the systems it must talk to, the three shapes it can be
deployed in, and what it holds and for how long. Three questions a client asks in
the same meeting and that a capability diagram cannot answer without becoming
unreadable.

Every panel is drawn from `10-realtime-agent-assist-architecture.md` — §2 for the
integration points, §4 for the deployment options, §10.1 for retention — so this
file is a view of that document, never a second source of truth for it.

Run from the repo root:  python scripts/make_context_diagram.py
Text fit is asserted, so a label that outgrows its box fails loudly.
"""
import pathlib
import xml.etree.ElementTree as ET

W, H = 1880, 1060
out = []

C = {
    "page": "#ffffff",
    "ink": "#16212e", "body": "#33414f", "muted": "#61707e", "hair": "#dfe5ec",
    "navy": "#143a6b", "navy_d": "#0d2b52", "navy_bg": "#f3f6fa", "navy_bd": "#c9d7e8",
    "orange": "#e8791a", "orange_bg": "#fdf7f0", "orange_bd": "#f3d0aa",
    "green": "#1c7a4b", "green_bg": "#f0f8f3", "green_bd": "#bcdcca",
    "red": "#d92b2b", "red_bg": "#fdf3f3", "red_bd": "#f0c6c6",
    "grey": "#9aa8b6", "grey_bg": "#f7f9fb", "grey_bd": "#dde4ec",
    "arrow": "#8fa0b3",
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


def line(x1, y1, x2, y2, color="hair", sw=1.2):
    out.append(f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" '
               f'stroke="{C.get(color, color)}" stroke-width="{sw}"/>')


def arrow(x1, y1, x2, y2, color="arrow", sw=2.0, both=False):
    a = ' marker-start="url(#aS)"' if both else ""
    out.append(f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" fill="none" '
               f'stroke="{C.get(color, color)}" stroke-width="{sw}" '
               f'stroke-linecap="round" marker-end="url(#aN)"{a}/>')


def panel(x, y, w, h, title, sub, accent="navy"):
    rect(x, y, w, h, 14, "#ffffff", "hair", 1.4, filt="sh")
    text(x + 26, y + 38, title, 14.5, accent, bold=True, ls="0.07em")
    nw = tw(title, 14.5, True) + len(title) * 14.5 * 0.07
    text(x + 26 + nw + 16, y + 38, "·", 14.5, accent, bold=True)
    text(x + 26 + nw + 32, y + 38, sub, 12.5, "muted")


def sysbox(x, y, w, h, title, lines, accent, dashed=True):
    rect(x, y, w, h, 10, "#ffffff", "grey_bd" if dashed else accent, 1.4,
         "6 5" if dashed else None, filt=None if dashed else "sh")
    fit(title, 12.5, w - 32, f"sys {title}", True)
    text(x + 16, y + 26, title, 12.5, "grey" if dashed else accent, bold=True,
         ls="0.02em")
    ly = y + 48
    for ln in lines:
        fit(ln, 11.5, w - 32, f"sysline {title}")
        text(x + 16, ly, ln, 11.5, "muted" if dashed else "body")
        ly += 17


out.append(f'''<defs>
  <filter id="sh" x="-6%" y="-10%" width="112%" height="122%">
    <feDropShadow dx="0" dy="1.6" stdDeviation="2.6" flood-color="#0d2242"
                  flood-opacity="0.10"/></filter>
  <marker id="aN" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.2"
          markerHeight="6.2" orient="auto-start-reverse">
    <path d="M 0 1.6 L 9 5 L 0 8.4 z" fill="{C["arrow"]}"/></marker>
  <marker id="aS" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.2"
          markerHeight="6.2" orient="auto">
    <path d="M 0 1.6 L 9 5 L 0 8.4 z" fill="{C["arrow"]}"/></marker>
</defs>''')
out.append(f'<rect width="100%" height="100%" fill="{C["page"]}"/>')

text(24, 46, "NanoVox — Product Context", 22, "ink", bold=True)
text(24, 70, "What it connects to, how it can be deployed, and what it holds — "
             "the three questions a capability diagram cannot answer", 13, "muted")

# ================================================== A · integration points ===
AX, AY, AW, AH = 24, 100, 1832, 430
panel(AX, AY, AW, AH, "INTEGRATION POINTS", "what it must talk to")

LCX, LCW = 94, 380
SRC = [
    ("CONTACT CENTRE · TELEPHONY", ["Media stream + CTI events —", "Connect, Genesys, Five9"],
     "media + events", True),
    ("MICROSOFT 365 · OUTLOOK", ["Graph delta on shared", "mailboxes; thread-level"],
     "email threads", False),
    ("KNOWLEDGE SOURCES", ["SharePoint, Confluence,", "approved-content library"],
     "documents", False),
    ("ENTRA ID · SSO", ["OIDC; roles from group", "claims; no local accounts"],
     "identity", True),
]
CCX, CCW = 764, 380
CTOP, CBOT = 168, 502
for i, (t, ls_, lbl, two_way) in enumerate(SRC):
    sy = 168 + i * 86
    sysbox(LCX, sy, LCW, 76, t, ls_, "navy")
    ay = sy + 38
    arrow(LCX + LCW + 8, ay, CCX - 10, ay, both=two_way)
    fit(lbl, 10.5, 240, f"arrowlbl {lbl}")
    text((LCX + LCW + CCX) / 2, ay - 8, lbl, 10.5, "muted", anchor="middle")

rect(CCX, CTOP, CCW, CBOT - CTOP, 12, "navy_bg", "navy", 1.8, filt="sh")
text(CCX + CCW / 2, CTOP + 130, "NANOVOX", 20, "navy", bold=True, anchor="middle",
     ls="0.08em")
for i, ln in enumerate(["Five-layer analysis, scoring,", "dashboards and actions"]):
    fit(ln, 12.5, CCW - 40, "core")
    text(CCX + CCW / 2, CTOP + 162 + i * 19, ln, 12.5, "body", anchor="middle")

RCX, RCW = 1400, 380
sysbox(RCX, 298, RCW, 94, "ENTERPRISE DATA PLATFORM",
       ["Export only — analyses, scores", "and signals to the lakehouse,", "read by Power BI"],
       "navy")
arrow(CCX + CCW + 8, 345, RCX - 10, 345)
text((CCX + CCW + RCX) / 2, 337, "one set of numbers", 10.5, "muted", anchor="middle")

_an = "None of these are built today. The product ingests pasted transcripts only."
fit(_an, 11.5, AW - 60, "anote")
text(AX + AW - 26, AY + AH - 22, _an, 11.5, "muted", anchor="end")

# =================================================== B · deployment options ===
BX_, BY_, BW_, BH_ = 24, 560, 900, 470
panel(BX_, BY_, BW_, BH_, "DEPLOYMENT OPTIONS", "three shapes, one set of interfaces", "green")

LABW, COLG = 165, 12
_inner = BX_ + 24
COLW = (BW_ - 48 - LABW - 2 * COLG) / 3
OPTS = [("OPTION 1", "POC", "THIS BUILD", "live"),
        ("OPTION 2", "HYBRID", "RECOMMENDED", "next"),
        ("OPTION 3", "ENTERPRISE", None, None)]
for i, (num, nm, badge, st) in enumerate(OPTS):
    cx = _inner + LABW + i * (COLW + COLG)
    if badge:
        bw = tw(badge, 9.5, True) + 20
        rect(cx, BY_ + 62, bw, 17, 8.5, "green" if st == "live" else "orange")
        text(cx + bw / 2, BY_ + 74, badge, 9.5, "#ffffff", bold=True, anchor="middle",
             ls="0.06em")
    text(cx, BY_ + 100, num, 10.5, "muted", bold=True, ls="0.1em")
    fit(nm, 14, COLW - 8, f"opt {nm}", True)
    text(cx, BY_ + 120, nm, 14, "green", bold=True, ls="0.03em")

ROWS = [
    ("Where models run",
     [["All local — Ollama or", "vLLM on one machine"],
      ["Fast lane self-hosted,", "deep lane managed"],
      ["Fully managed —", "Azure OpenAI + Speech"]]),
    ("Where member data sits",
     [["Never leaves the", "machine"],
      ["In the tenant; only", "redacted text goes out"],
      ["Managed, CMK-encrypted,", "DLP available"]]),
    ("Cost per month",
     [["≈ $0.5k–1.2k"], ["≈ $2.4k–3.1k"], ["≈ $7k–11k"]]),
    ("Security posture",
     [["Strong isolation,", "weak operations"],
      ["Private endpoints, SSO,", "BAA on the deep lane"],
      ["Strongest — tenant", "isolation, managed DLP"]]),
    ("Best for",
     [["Calibrating the rubric", "on real calls"],
      ["Production pilot", "and beyond"],
      ["Multi-region, SLA-backed", "operation"]]),
]
_ry = BY_ + 142
for lab, cells in ROWS:
    line(_inner, _ry, BX_ + BW_ - 24, _ry)
    fit(lab, 11, LABW - 12, f"rowlab {lab}", True)
    text(_inner, _ry + 26, lab, 11, "ink", bold=True)
    for i, lines in enumerate(cells):
        cx = _inner + LABW + i * (COLW + COLG)
        for j, ln in enumerate(lines):
            fit(ln, 11, COLW - 10, f"cell {lab} {i}")
            text(cx, _ry + 26 + j * 16, ln, 11, "body")
    _ry += 62

# ====================================================== C · data lifecycle ===
DX, DY, DW, DH = 956, 560, 900, 470
panel(DX, DY, DW, DH, "DATA LIFECYCLE", "what is held, and for how long",
      "orange")

CLASSES = [
    ("Raw audio", "30–90 days", 0.12, "red", "Highest risk, least value once transcribed"),
    ("Logs", "1 yr hot · 7 yr archive", 0.30, "grey", None),
    ("Transcripts", "2 years", 0.45, "orange", None),
    ("Analyses", "7 years", 0.80, "navy", None),
    ("Aggregates", "Indefinite", 1.00, "green", "Carries no member identity"),
]
LABX, BARX, BARW = DX + 26, DX + 190, 420
_dy = DY + 96
for name, dur, frac, col, note in CLASSES:
    fit(name, 12, 150, f"class {name}", True)
    text(LABX, _dy + 4, name, 12, "ink", bold=True)
    rect(BARX, _dy - 9, BARW, 14, 7, "grey_bg")
    rect(BARX, _dy - 9, BARW * frac, 14, 7, col)
    fit(dur, 11, 250, f"dur {name}")
    text(BARX + BARW + 16, _dy + 3, dur, 11, "body")
    if note:
        fit(note, 10.5, DW - 60, f"cnote {name}")
        text(LABX, _dy + 24, note, 10.5, "muted")
    _dy += 62

line(DX + 26, DY + 400, DX + DW - 26, DY + 400)
for i, ln in enumerate([
        "Right-to-delete is honoured across the database, the lake, the vector store and",
        "object storage. Retention is configurable per class and enforced by a scheduled job.",
        "None of it is implemented in this build — the POC keeps everything, in one SQLite file."]):
    fit(ln, 11.5, DW - 52, "dnote")
    text(DX + 26, DY + 424 + i * 17, ln, 11.5,
         "body" if i < 2 else "muted")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
       f'height="{H}" role="img" aria-label="Product context: integration points, '
       f'three deployment options compared, and data retention by class">\n'
       + "\n".join(out) + "\n</svg>\n")
dest = pathlib.Path("Gen Documents/14-product-context-diagram.svg")
dest.write_text(svg, encoding="utf-8")
ET.fromstring(svg)
print(f"wrote {dest} ({len(svg)} bytes) — XML OK")
print("\n".join(["FIT WARNINGS:"] + ["  - " + w for w in warn]) if warn
      else "no text-fit warnings")
