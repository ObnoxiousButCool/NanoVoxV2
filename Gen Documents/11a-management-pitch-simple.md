# NanoVox — The Short Version

A plain-language summary for management. The long version, with the detailed
answers and the lines to use on a call, is `11-management-pitch.md`.

---

## The problem

A call centre handles thousands of calls a month. Managers can see how many
calls there were and how long they took. They cannot see **what was said**.

So nobody can answer simple questions:

- Are our people telling customers the right thing?
- What keeps going wrong?
- Which customers are about to leave?

Today, reviewers listen to about **2 calls in every 100**. At 3,000 calls a
month, that means **2,940 calls nobody ever hears**.

## What we built

> We turn conversations into text, and text into a scored record.

Two steps:

1. **Voice to text.** The call is transcribed, speaker by speaker. Personal
   details are hidden before anything else reads it.
2. **Text to a record.** Each call is sorted, scored, and stored — with the
   exact quote behind every judgement.

Every call gets scored, the same way every time. Human reviewers then spend
their time on the calls that actually need them.

## Why it is trustworthy

- **The AI does not decide the score.** It only finds the quotes. A rules file
  turns those quotes into a number. Same call plus same rules gives the same
  score, every time.
- **No proof, no claim.** If we cannot point at an approved document, we say
  nothing.
- **Privacy first.** Personal details are removed before any AI sees the text.

## Why it is a platform, not one project

Nothing we built knows it is in healthcare. Nothing we built knows the call
came from a phone.

Everything reads one simple thing: **who said what, when**. Email, chat, SMS
and meetings all produce that same thing. So they all plug into the same
engine.

| To add this | You write | Roughly |
|---|---|---|
| A new phone system | One connector | 1–2 weeks |
| Email, chat or SMS | One connector | ~1 week |
| A new report or alert | One layout | Days |
| A different AI vendor | One connector | Days |
| **A new industry** | Three config files, then tune | 3–4 weeks, **no code** |

The first client pays for the engine. The second is mostly configuration.

## Where we honestly are

| | Status |
|---|---|
| Scoring calls after they happen | **Working today** |
| Dashboards over scored calls | **Working today** |
| Four AI vendors, swappable | **Working today** |
| Live help during a call | Designed and priced, **not built** |
| Email and chat | Designed, **not built** |

## What it costs

| Stage | Time | Monthly cost |
|---|---|---|
| Tune it on real calls | ~6 weeks | ~$0.5–1.1k |
| Live pilot, a few queues | +6 weeks | ~$1.8–2.4k |
| Full production, all channels | +12 weeks | ~$2.4–3.1k |

Cost is fixed, not per person. Adding agents does not add licence fees.

## What we are asking for

1. Treat the engine as a **company asset**, not a one-client build.
2. **Name a second use case now** — another channel or another industry — so we
   prove the config-swap claim while the first build is still fresh.
3. **Fund the 6-week tuning phase** on real calls. That is what turns "the
   scores look about right" into "the scores hold up".

---

## Three lines to remember

- "Today we hear 2 calls in 100. We score all 100, the same way every time."
- "The AI finds the evidence. The rules file decides the number."
- "The industry is configuration. The engine is the asset."
