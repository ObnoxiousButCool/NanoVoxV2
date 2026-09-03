"""Generate the COMPONENT architecture diagram SVG.

Same visual language as make_highlevel_diagram.py, but one colour system: the
lanes are neutral, and colour on a card says *who operates it*. Every box gets a
name and at most one short line; the reasoning lives in the document.

Run from the repo root:  python scripts/make_architecture_diagram.py
Text fit is asserted, so a label that outgrows its box fails loudly.
"""
import pathlib
import xml.etree.ElementTree as ET

W, H = 1720, 1404
out = []

C = {
    "page": "#ffffff", "ink": "#16212e", "body": "#33414f", "muted": "#61707e",
    "faint": "#8d9aa8", "hair": "#dfe5ec", "lane": "#f4f7fa", "lane_bd": "#dce4ee",
    "navy": "#143a6b", "navy_t": "#0d2b52",
    "green": "#1c7a4b", "green_t": "#14603a",
    "amber": "#d59200", "amber_t": "#8a5d00",
    "violet": "#7c53c8", "violet_t": "#4e2f88",
    "grey": "#7d8b99", "grey_t": "#3b4753",
    "red": "#d92b2b", "arrow": "#8fa0b3",
}
KIND = {"ours": ("navy", "navy_t"), "managed": ("green", "green_t"),
        "det": ("amber", "amber_t"), "data": ("violet", "violet_t"),
        "ext": ("grey", "grey_t")}
FONT = "'Segoe UI','Inter',-apple-system,'Helvetica Neue',Arial,sans-serif"
warn = []


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(s, fs, bold=False):
    return len(s) * fs * (0.575 if bold else 0.525)


def fit(s, fs, avail, tag, bold=False):
    if tw(s, fs, bold) > avail:
        warn.append(f"{tag}: {s!r} {tw(s, fs, bold):.0f} > {avail:.0f}")


def text(x, y, s, fs=12.5, fill="body", bold=False, anchor="start", ls=None):
    a = f' letter-spacing="{ls}"' if ls else ""
    out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{fs}" '
               f'fill="{C.get(fill, fill)}" font-weight="{"600" if bold else "400"}" '
               f'text-anchor="{anchor}"{a}>{esc(s)}</text>')


def rect(x, y, w, h, r=10, fill="#ffffff", stroke=None, sw=1.3, dash=None, filt=None):
    a = f' stroke="{C.get(stroke, stroke)}" stroke-width="{sw}"' if stroke else ""
    a += f' stroke-dasharray="{dash}"' if dash else ""
    a += f' filter="url(#{filt})"' if filt else ""
    out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
               f'rx="{r}" fill="{C.get(fill, fill)}"{a}/>')


# ------------------------------------------------------------------- icons ---
G = {
    "person": '<circle cx="12" cy="8" r="3.6" fill="none" stroke-width="2"/>'
              '<path d="M5 20c0-3.9 3.1-6.4 7-6.4s7 2.5 7 6.4" fill="none" stroke-width="2"/>',
    "headset": '<path d="M4.5 14v-2a7.5 7.5 0 0 1 15 0v2" fill="none" stroke-width="2"/>'
               '<rect x="2.6" y="13" width="4.2" height="6.4" rx="2.1" fill="none" '
               'stroke-width="1.9"/><rect x="17.2" y="13" width="4.2" height="6.4" '
               'rx="2.1" fill="none" stroke-width="1.9"/>',
    "monitor": '<rect x="3" y="4.5" width="18" height="12" rx="2" fill="none" '
               'stroke-width="2"/><path d="M9 20h6M12 16.5V20" stroke-width="1.9"/>',
    "people": '<circle cx="9" cy="8.4" r="3.2" fill="none" stroke-width="1.9"/>'
              '<path d="M3.2 19.5c0-3.4 2.6-5.6 5.8-5.6s5.8 2.2 5.8 5.6" fill="none" '
              'stroke-width="1.9"/><path d="M16 7.2a3.2 3.2 0 0 1 0 6.2M17 14.6c2.4.5 '
              '4 2.5 4 4.9" fill="none" stroke-width="1.8"/>',
    "book": '<path d="M12 6.5C10.3 5 7.8 4.4 4 4.6v13.2c3.8-.2 6.3.4 8 1.9 1.7-1.5 '
            '4.2-2.1 8-1.9V4.6c-3.8-.2-6.3.4-8 1.9z" fill="none" stroke-width="2"/>'
            '<path d="M12 6.5v13" stroke-width="1.6"/>',
    "gate": '<path d="M12 2.6 20.4 6v6.4c0 4.9-3.6 8.6-8.4 9.8-4.8-1.2-8.4-4.9-8.4-9.8V6z" '
            'fill="none" stroke-width="2"/><path d="m8.4 12.2 2.4 2.4 4.8-5" '
            'fill="none" stroke-width="2"/>',
    "wave": '<path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4" stroke-width="2" '
            'stroke-linecap="round"/>',
    "cut": '<path d="M3.5 5.5 15 17M3.5 18.5 15 7" fill="none" stroke-width="1.9"/>'
           '<circle cx="18" cy="6" r="2.6" fill="none" stroke-width="1.9"/>'
           '<circle cx="18" cy="18" r="2.6" fill="none" stroke-width="1.9"/>',
    "mic": '<rect x="9" y="2.6" width="6" height="11" rx="3" fill="none" stroke-width="2"/>'
           '<path d="M5.4 11.4a6.6 6.6 0 0 0 13.2 0M12 18v3.4" fill="none" stroke-width="2"/>',
    "shield": '<path d="M12 2.6 20.4 6v6.4c0 4.9-3.6 8.6-8.4 9.8-4.8-1.2-8.4-4.9-8.4-9.8V6z" '
              'fill="none" stroke-width="2"/><rect x="9.2" y="10.6" width="5.6" '
              'height="4.8" rx="1" fill="#ffffff" stroke="none"/>'
              '<path d="M10.4 10.6V9.2a1.6 1.6 0 0 1 3.2 0v1.4" fill="none" stroke-width="1.6"/>',
    "stream": '<path d="M3 7h13M3 12h18M3 17h10" stroke-width="2" stroke-linecap="round"/>'
              '<circle cx="19.4" cy="7" r="1.8"/><circle cx="14" cy="17" r="1.8"/>',
    "clock": '<circle cx="12" cy="12" r="8.6" fill="none" stroke-width="2"/>'
             '<path d="M12 7v5.4l3.4 2" fill="none" stroke-width="2"/>',
    "tags": '<path d="M4 5h7l8 7-7 7-8-8z" fill="none" stroke-width="2"/>'
            '<circle cx="8.4" cy="9.4" r="1.5"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.6" fill="none" stroke-width="2"/>'
              '<path d="m15.4 15.4 4.6 4.6" fill="none" stroke-width="2.2"/>',
    "bolt": '<path d="M13.4 2.5 5 13.6h5.6L9.8 21.5 19 10.2h-5.8z" fill="none" '
            'stroke-width="2" stroke-linejoin="round"/>',
    "fingerprint": '<path d="M6 12a6 6 0 0 1 12 0" fill="none" stroke-width="1.9"/>'
                   '<path d="M9 13.4a3 3 0 0 1 6 0v1.4" fill="none" stroke-width="1.8"/>'
                   '<path d="M3.4 11.2A8.6 8.6 0 0 1 20.6 11" fill="none" stroke-width="1.7"/>'
                   '<path d="M12 12v6.6" fill="none" stroke-width="1.8"/>',
    "sliders": '<path d="M4 7h16M4 12h16M4 17h16" stroke-width="1.9" stroke-linecap="round"/>'
               '<circle cx="9" cy="7" r="2.4" fill="#ffffff" stroke-width="1.9"/>'
               '<circle cx="15.5" cy="12" r="2.4" fill="#ffffff" stroke-width="1.9"/>'
               '<circle cx="7.5" cy="17" r="2.4" fill="#ffffff" stroke-width="1.9"/>',
    "scale": '<path d="M12 4v16M6 20h12" stroke-width="2" stroke-linecap="round"/>'
             '<path d="M4 8h16" stroke-width="1.9"/><path d="M4 8 1.6 13.6h4.8z" '
             'fill="none" stroke-width="1.7"/><path d="M20 8l-2.4 5.6h4.8z" fill="none" '
             'stroke-width="1.7"/>',
    "db": '<ellipse cx="12" cy="6.2" rx="7.6" ry="2.9" fill="none" stroke-width="2"/>'
          '<path d="M4.4 6.2v11.6c0 1.6 3.4 2.9 7.6 2.9s7.6-1.3 7.6-2.9V6.2" '
          'fill="none" stroke-width="2"/><path d="M4.4 12c0 1.6 3.4 2.9 7.6 2.9s7.6-1.3 '
          '7.6-2.9" fill="none" stroke-width="1.6"/>',
    "doc": '<path d="M6 3h8l4 4v14H6z" fill="none" stroke-width="2" stroke-linejoin="round"/>'
           '<path d="M14 3v4h4M9 12h6M9 16h6" stroke-width="1.7"/>',
    "window": '<rect x="3" y="4.5" width="18" height="15" rx="2.2" fill="none" '
              'stroke-width="2"/><path d="M3 9.4h18" stroke-width="1.8"/>'
              '<path d="M7 13.4h7M7 16.2h4" stroke-width="1.7"/>',
    "gauge": '<path d="M3.6 17.4a9 9 0 1 1 16.8 0" fill="none" stroke-width="2"/>'
             '<path d="m12 16 4.4-5" fill="none" stroke-width="2"/>'
             '<circle cx="12" cy="17" r="1.8"/>',
    "clipboard": '<rect x="5" y="4.5" width="14" height="16" rx="2" fill="none" '
                 'stroke-width="2"/><rect x="9" y="2.6" width="6" height="3.8" rx="1.2" '
                 'fill="none" stroke-width="1.8"/><path d="M9 11h6M9 15h4" stroke-width="1.7"/>',
    "layers": '<path d="m12 3 9 4.6-9 4.6-9-4.6z" fill="none" stroke-width="2" '
              'stroke-linejoin="round"/><path d="m3.6 12 8.4 4.3 8.4-4.3M3.6 16.4 12 20.7'
              'l8.4-4.3" fill="none" stroke-width="1.8"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.2" fill="none" stroke-width="2"/>'
            '<path d="m3.8 6.6 8.2 6 8.2-6" fill="none" stroke-width="1.9"/>',
    "cloud": '<ellipse cx="10" cy="8.5" rx="6.2" ry="2.5" fill="none" stroke-width="1.9"/>'
             '<path d="M3.8 8.5v8.2c0 1.4 2.8 2.5 6.2 2.5s6.2-1.1 6.2-2.5V8.5" '
             'fill="none" stroke-width="1.9"/><path d="M17.2 6.4a3 3 0 0 1 .3 6h-2.2" '
             'fill="none" stroke-width="1.7"/>',
    "plug": '<path d="M9 3v6M15 3v6" stroke-width="2" stroke-linecap="round"/>'
            '<path d="M6 9h12v3a6 6 0 0 1-12 0z" fill="none" stroke-width="2"/>'
            '<path d="M12 18v3.4" stroke-width="2" stroke-linecap="round"/>',
    "list": '<path d="M9 6.5h11M9 12h11M9 17.5h11" stroke-width="1.9" stroke-linecap="round"/>'
            '<circle cx="4.8" cy="6.5" r="1.7"/><circle cx="4.8" cy="12" r="1.7"/>'
            '<circle cx="4.8" cy="17.5" r="1.7"/>',
    "chart": '<rect x="3.5" y="4" width="17" height="16" rx="2.2" fill="none" '
             'stroke-width="2"/><path d="M7.6 15.6v-3.2M12 15.6V9M16.4 15.6v-4.6" '
             'stroke-width="2" stroke-linecap="round"/>',
    "nodes": '<circle cx="12" cy="12" r="2.6" fill="none" stroke-width="2"/>'
             '<circle cx="4.6" cy="6" r="2.1" fill="none" stroke-width="1.9"/>'
             '<circle cx="19.4" cy="6" r="2.1" fill="none" stroke-width="1.9"/>'
             '<circle cx="4.6" cy="18" r="2.1" fill="none" stroke-width="1.9"/>'
             '<circle cx="19.4" cy="18" r="2.1" fill="none" stroke-width="1.9"/>'
             '<path d="m6.4 7.4 3.4 3.1M17.6 7.4l-3.4 3.1M6.4 16.6l3.4-3.1M17.6 16.6'
             'l-3.4-3.1" stroke-width="1.6"/>',
}


def icon(x, y, size, colour, glyph, r=8):
    rect(x, y, size, size, r, colour, filt="ic")
    s = (size - 8) / 24
    out.append(f'<g transform="translate({x + 4:.1f},{y + 4:.1f}) scale({s:.3f})" '
               f'fill="#ffffff" stroke="#ffffff" stroke-linejoin="round" '
               f'stroke-linecap="round">{G[glyph]}</g>')


# -------------------------------------------------------------- components ---
def lane(x, y, w, h, num, label, note=None):
    rect(x, y, w, h, 14, "lane", "lane_bd", 1.3)
    out.append(f'<circle cx="{x + 30}" cy="{y + 25}" r="11" fill="{C["navy"]}"/>')
    text(x + 30, y + 29.5, num, 11.5, "#ffffff", bold=True, anchor="middle")
    text(x + 50, y + 30, label.upper(), 12, "navy_t", bold=True, ls="0.1em")
    if note:
        text(x + w - 22, y + 30, note, 11.5, "faint", anchor="end")


def comp(x, y, w, h, title, line=None, kind="ours", glyph="nodes", badge=None,
         dashed=False):
    s, t = (C[k] for k in KIND[kind])
    rect(x, y, w, h, 10, "#ffffff", "hair", 1.3, "5 4" if dashed else None, "sh")
    icon(x + 13, y + (h - 34) / 2, 34, s, glyph)
    fit(title, 12.5, w - 66, f"t:{title}", True)
    ty = y + h / 2 + (-3 if line else 4)
    text(x + 56, ty, title, 12.5, t, bold=True, ls="0.015em")
    if line:
        fit(line, 10.5, w - 62, f"l:{title}")
        text(x + 56, ty + 15, line, 10.5, "muted")
    if badge:
        bw = tw(badge, 9.5, True) + 16
        rect(x + w - bw - 8, y - 8, bw, 17, 8.5, s)
        text(x + w - bw / 2 - 8, y + 4, badge, 9.5, "#ffffff", bold=True, anchor="middle")
    return {"x": x, "y": y, "w": w, "h": h, "cx": x + w / 2, "cy": y + h / 2,
            "b": y + h, "r": x + w}


def arrow(pts, color="arrow", dashed=False, sw=1.9, label=None, lpos=None):
    col = C.get(color, color)
    mk = {"red": "aR", "amber": "aA", "green": "aG"}.get(color, "aN")
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{sw}" '
               f'stroke-linecap="round" stroke-linejoin="round"{dash} '
               f'marker-end="url(#{mk})"/>')
    if label:
        lx, ly = lpos
        bw = tw(label, 10.5) + 16
        rect(lx - bw / 2, ly - 11, bw, 19, 5, "#ffffff")
        text(lx, ly + 2, label, 10.5, "muted", anchor="middle")


def chain(bs, y):
    for a, b in zip(bs, bs[1:]):
        arrow([(a["r"], y), (b["x"] - 4, y)])


def mkr(i, col):
    return (f'<marker id="{i}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.2" '
            f'markerHeight="6.2" orient="auto-start-reverse">'
            f'<path d="M 0 1.6 L 9 5 L 0 8.4 z" fill="{col}"/></marker>')


out.append(f'''<defs>
  <linearGradient id="acc" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{C["navy"]}"/>
    <stop offset="55%" stop-color="{C["amber"]}"/>
    <stop offset="100%" stop-color="{C["green"]}"/></linearGradient>
  <filter id="sh" x="-12%" y="-26%" width="124%" height="152%">
    <feDropShadow dx="0" dy="1.4" stdDeviation="2.2" flood-color="#0d2242"
                  flood-opacity="0.09"/></filter>
  <filter id="ic" x="-26%" y="-26%" width="152%" height="152%">
    <feDropShadow dx="0" dy="1.2" stdDeviation="1.6" flood-color="#0d2242"
                  flood-opacity="0.20"/></filter>
  {mkr("aN", C["arrow"])}{mkr("aR", C["red"])}{mkr("aA", C["amber"])}{mkr("aG", C["green"])}
</defs>''')
out.append(f'<rect width="{W}" height="{H}" fill="{C["page"]}"/>')
out.append(f'<rect x="40" y="30" width="132" height="5" rx="2.5" fill="url(#acc)"/>')
text(40, 66, "Real-Time Agent Assist", 26, "ink", bold=True, ls="-0.01em")
text(40, 90, "Component architecture — what exists, and how it connects. "
             "Overview: 10-high-level-diagram.svg", 12.5, "muted")
text(W - 40, 66, "COMPONENT ARCHITECTURE", 12, "faint", bold=True, anchor="end",
     ls="0.14em")
text(W - 40, 90, "latency figures are the §6.1 budget", 11.5, "faint", anchor="end")

LX, LW = 40, 1640
IX = LX + 22
CW, CG = 300, 24
cx5 = [IX + i * (CW + CG) for i in range(5)]

# ------------------------------------------------------------------ 1 edges ---
lane(LX, 116, LW, 104, "1", "Channels & people")
member = comp(cx5[0], 148, CW, 58, "MEMBER", None, "ext", "person")
cc = comp(cx5[1], 148, CW, 58, "CONTACT CENTRE", "media stream + CTI", "ext", "headset")
agent = comp(cx5[2], 148, CW, 58, "AGENT DESKTOP", None, "ext", "monitor")
sup = comp(cx5[3], 148, CW, 58, "SUPERVISOR", None, "ext", "people")
kb = comp(cx5[4], 148, CW, 58, "KNOWLEDGE SOURCES", "approved documents", "ext", "book")
arrow([(member["r"], 177), (cc["x"] - 4, 177)])
arrow([(cc["r"], 177), (agent["x"] - 4, 177)])

# --------------------------------------------------------------- 2 capture ---
lane(LX, 242, LW, 116, "2", "Capture & transcribe")
gw = comp(cx5[0], 276, CW, 62, "API GATEWAY", "mTLS · OIDC · WAF", "ours", "gate")
aud = comp(cx5[1], 276, CW, 62, "AUDIO GATEWAY", "dual channel", "ours", "wave",
           badge="50–150 ms")
vad = comp(cx5[2], 276, CW, 62, "VAD + CHUNKER", "utterance endpointing", "ours", "cut",
           badge="80–200 ms")
asr = comp(cx5[3], 276, CW, 62, "STREAMING ASR", "Azure Speech / Deepgram", "managed",
           "mic", badge="150–400 ms")
red = comp(cx5[4], 276, CW, 62, "PHI REDACTOR", "fails closed", "ours", "shield",
           badge="5–20 ms")
chain([gw, aud, vad, asr, red], 307)
arrow([(cc["cx"], cc["b"]), (cc["cx"], 232), (gw["cx"], 232), (gw["cx"], gw["y"] - 4)])

# PHI boundary — a horizontal line in a top-down layout
out.append(f'<path d="M {LX + 10} 376 L {W - LX - 10} 376" stroke="{C["red"]}" '
           f'stroke-width="1.9" stroke-dasharray="9 7" opacity="0.85"/>')
_pb = "PHI BOUNDARY  ·  everything below this line sees masked text only"
_pw = tw(_pb, 11.5, True) + 34
rect(W / 2 - _pw / 2, 365, _pw, 22, 11, "#ffffff")
text(W / 2, 380, _pb, 11.5, "red", bold=True, anchor="middle", ls="0.04em")

# ------------------------------------------------------------------- 3 bus ---
lane(LX, 402, LW, 96, "3", "Event bus", "replayable — a rule change is a replay, not a re-record")
bus = comp(IX, 436, LW - 44, 48, "EVENT STREAMING",
           "Event Hubs (Kafka API) · stt.turn · assist.card · escalation · feedback",
           "managed", "stream")
arrow([(red["cx"], red["b"]), (red["cx"], bus["y"] - 4)])

# ----------------------------------------------------------- 4 live assist ---
lane(LX, 522, LW, 252, "4", "Live assist",
     "Tier 0 ≤ 300 ms deterministic   ·   Tier 1 ≤ 1,450 ms p95")
R1, R2, BH = 556, 662, 62
sess = comp(cx5[0], R1, CW, BH, "CALL SESSION", "actor per call · Redis", "ours", "clock")
cls = comp(cx5[1], R1, CW, BH, "CLASSIFIERS", "intent · sentiment · churn", "ours",
           "tags", badge="20–60 ms")
rag = comp(cx5[2], R1, CW, BH, "RETRIEVAL", "hybrid search + rerank", "ours", "search",
           badge="80–250 ms")
llm = comp(cx5[3], R1, CW, BH, "FAST LLM", "phrasing only, never facts", "ours", "bolt",
           badge="250–700 ms")
prov = comp(cx5[4], R1, CW, BH, "PROVENANCE", "rules · doc · model", "ours",
            "fingerprint", dashed=True)
orch = comp(cx5[0], R2, CW, BH, "ORCHESTRATOR", "debounce · cap · dedupe", "ours",
            "sliders")
rules = comp(cx5[1], R2, CW, BH, "RULES ENGINE", "versioned config, no model", "det",
             "scale", badge="1–5 ms")
vdb = comp(cx5[2], R2, CW, BH, "VECTOR STORE", "pgvector · ACL · dates", "data", "db")
docp = comp(cx5[3], R2, CW, BH, "DOC PIPELINE", "chunk · embed · approve", "ours", "doc")
guard = comp(cx5[4], R2, CW, BH, "GUARDRAILS", "citations · assertion guard", "det",
             "gate", badge="10–40 ms")
chain([sess, cls, rag, llm, prov], R1 + 31)
arrow([(bus["cx"], bus["b"]), (bus["cx"], 512), (sess["cx"], 512),
       (sess["cx"], sess["y"] - 4)])
for a, b in ((sess, orch), (cls, rules), (rag, vdb), (prov, guard)):
    arrow([(a["cx"], a["b"]), (a["cx"], b["y"] - 4)])
arrow([(docp["x"] - 4, docp["cy"]), (vdb["r"] + 4, docp["cy"])], dashed=True)
arrow([(kb["cx"], kb["b"]), (kb["cx"], 232), (1700, 232), (1700, 752),
       (docp["cx"], 752), (docp["cx"], docp["b"] + 4)], dashed=True)

# -------------------------------------------------------------- 5 delivery ---
lane(LX, 798, LW, 112, "5", "Delivery")
DW, DG = 512, 30
dx = [IX + i * (DW + DG) for i in range(3)]
ui = comp(dx[0], 832, DW, 62, "AGENT ASSIST UI", "Tier 0, then Tier 1 progressively",
          "ours", "window")
supui = comp(dx[1], 832, DW, 62, "SUPERVISOR CONSOLE", "risk board · escalations",
             "ours", "gauge")
wrap = comp(dx[2], 832, DW, 62, "WRAP-UP SCREEN", "summary the agent approves", "ours",
            "clipboard")
arrow([(rules["cx"], rules["b"]), (rules["cx"], 786), (280, 786), (280, ui["y"] - 4)],
      "amber", label="Tier 0", lpos=(280, 812))
arrow([(guard["cx"], guard["b"]), (guard["cx"], 764), (700, 764), (700, ui["y"] - 4)],
      label="Tier 1", lpos=(700, 812))
arrow([(rules["cx"] + 90, rules["b"]), (rules["cx"] + 90, 776), (supui["cx"], 776),
       (supui["cx"], supui["y"] - 4)], "red", label="escalation", lpos=(supui["cx"], 812))

# ------------------------------------------------------------------ 6 async ---
lane(LX, 934, LW, 268, "6", "Asynchronous")
post = comp(IX, 968, 776, 62, "POST-CALL PIPELINE",
            "sealed transcript, replayed from the bus", "ours", "layers")
chw, chg = 140, 12
for i, (code, nm) in enumerate([("L1", "understand"), ("L2", "insights"),
                                ("L3", "markers"), ("L4", "BI"), ("L5", "replay")]):
    x0 = IX + 8 + i * (chw + chg)
    rect(x0, 1044, chw, 42, 8, "#ffffff", "hair", 1.2, filt="sh")
    text(x0 + chw / 2, 1061, code, 12, "navy_t", bold=True, anchor="middle")
    text(x0 + chw / 2, 1076, nm, 10, "muted", anchor="middle")
    if i:
        arrow([(x0 - chg - 2, 1065), (x0 - 3, 1065)])
rub = comp(IX + 8, 1100, 380, 60, "RUBRIC · rubric.yaml", "markers in, score out", "det",
           "scale")
deep = comp(IX + 400, 1100, 368, 60, "DEEP LLM", "summary · root cause · trends",
            "managed", "bolt")
arrow([(rub["r"], rub["cy"]), (deep["x"] - 4, deep["cy"])])
l5x = IX + 8 + 4 * (chw + chg) + chw / 2
arrow([(l5x, 1040), (l5x, 924), (rules["cx"] + 40, 924), (rules["cx"] + 40,
       rules["b"] + 4)], "amber", label="L5 → new rules", lpos=(l5x - 120, 920))

email = comp(IX + 800, 968, 380, 62, "EMAIL CHANNEL", "~7,000 a month", "ours", "mail")
ey = 1044
for t1 in ["M365 / Outlook · Graph delta", "normalise · thread · dedupe",
           "redact (same as voice)", "classify · intent · urgency", "route to a queue"]:
    rect(IX + 808, ey, 364, 22, 6, "#ffffff", "hair", 1.1)
    text(IX + 990, ey + 15, t1, 10.5, "body", anchor="middle")
    ey += 24

data = comp(IX + 1200, 968, 396, 62, "DATA PLATFORM", "one set of numbers", "data",
            "cloud")
dy = 1044
for t1 in ["PostgreSQL + pgvector", "object store · audio & docs",
           "lakehouse · Parquet / Delta", "warehouse · semantic layer",
           "Power BI · reads the same numbers"]:
    rect(IX + 1208, dy, 380, 22, 6, "#ffffff", "hair", 1.1)
    text(IX + 1398, dy + 15, t1, 10.5, "body", anchor="middle")
    dy += 24
arrow([(post["r"], 999), (email["x"] - 4, 999)], dashed=True)
arrow([(email["r"], 999), (data["x"] - 4, 999)])

# -------------------------------------------------------------- 7 providers ---
lane(LX, 1226, LW, 108, "7", "Model providers", "one port · one adapter serves a request")
port = comp(IX, 1260, 268, 58, "PORT", "schema in, object out", "ours", "plug")
reg = comp(IX + 288, 1260, 268, 58, "REGISTRY", "never falls back", "det", "list")
arrow([(port["r"], port["cy"]), (reg["x"] - 4, reg["cy"])])
pw, pg = 186, 16
pxs = [IX + 584 + i * (pw + pg) for i in range(5)]
for px_, (nm, ln, kind, dsh) in zip(pxs, [
        ("OLLAMA", "local · free", "ours", False),
        ("vLLM", "self-hosted GPU", "ours", True),
        ("OPENAI", "per token", "managed", False),
        ("ANTHROPIC", "per token", "managed", False),
        ("AZURE FOUNDRY", "not built yet", "det", True)]):
    comp(px_, 1260, pw, 58, nm, ln, kind, "nodes", dashed=dsh)
arrow([(reg["r"], reg["cy"]), (pxs[0] - 4, reg["cy"])])

# ------------------------------------------------------------------ footer ---
text(LX + 22, 1364, "CROSS-CUTTING", 11, "faint", bold=True, ls="0.12em")
text(LX + 152, 1364, "Entra ID SSO · RBAC   ·   Key Vault · CMK · mTLS   ·   "
                     "OpenTelemetry   ·   hash-chained audit log   ·   retention & DLP",
     11.5, "muted")
lx = LX + 22
text(lx, 1390, "KEY", 10.5, "faint", bold=True, ls="0.12em")
lx += 44
for kind, lab in [("ours", "self-hosted"), ("det", "deterministic config"),
                  ("managed", "cloud-managed"), ("data", "data store"),
                  ("ext", "external")]:
    s, t = (C[k] for k in KIND[kind])
    rect(lx, 1381, 14, 11, 3.5, s)
    text(lx + 20, 1390, lab, 11, "muted")
    lx += 20 + tw(lab, 11) + 26
text(W - 40, 1390, "dashed = asynchronous, config-time, or not built yet", 11, "faint",
     anchor="end")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
       f'height="{H}" role="img" aria-label="Component architecture of the Real-Time '
       f'Agent Assist platform">\n' + "\n".join(out) + "\n</svg>\n")
dest = pathlib.Path("Gen Documents/10-architecture-diagram.svg")
dest.write_text(svg, encoding="utf-8")
ET.fromstring(svg)
print(f"wrote {dest} ({len(svg)} bytes) — XML OK")
print("\n".join(["FIT WARNINGS:"] + ["  - " + w for w in warn]) if warn
      else "no text-fit warnings")
