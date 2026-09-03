# Conversation Intelligence — Pitch Notes for Senior Management

**For:** tonight's call
**Structure:** Why → What → How → **Scaling irrespective of platform** (spend most of your time here)
**Origin:** the member call-centre use case Karim raised
**Status of the work:** an analysis engine that runs today, plus a costed design for the live and multi-channel parts

---

## 0. The 30-second open

> "Karim brought us a member call-centre problem: several thousand conversations a month
> and no idea what is being said in them. We built the engine that answers it — it turns a
> conversation into text, and text into a scored, evidence-backed record.
>
> What I want to talk about tonight is not that one client. It's that **nothing we built
> knows it is in healthcare, and nothing we built knows it came from a phone.** The engine
> reads one object: a list of who said what, when. Every channel we will ever be asked
> about produces that same object. That is why this is a platform and not a project."

Then stop talking and let them ask. If you only land one idea tonight, land the bolded one.

---

## 1. WHY — the need is already in the room

**The client-side problem, stated plainly.** A contact centre handles thousands of
conversations a month. Leadership can see *how long* they took and *how many* there were.
They cannot see *what was said*. So they cannot answer:

- Are agents giving people correct and complete information?
- Which issues keep coming back, and why?
- Which customers are about to leave, and did we see it coming?
- Which calls should a supervisor have stepped into?

**Why it is a clean sale, not a research project.** Every client conversation lands on the
same three asks — *are my people saying the right thing*, *what keeps going wrong*, *warn me
earlier*. That is not a healthcare question. It is a contact-centre question, and every
client with agents talking to customers has it.

**The number that makes the case.** Manual QA in a typical contact centre reviews **1–2% of
calls** (industry norm, not our figure). At ~3,000 calls a month that is around 60 reviewed
and **~2,940 nobody ever looks at**. Compliance exposure lives in the unread 98%.

> **The line to use:** "Today QA listens to two calls in a hundred. We score a hundred in a
> hundred — with the same rubric every time — and then point the human reviewers at the ones
> that deserve them."

**What it is worth.** Three things clients pay for, in rising order of value: an audit trail
they can defend, a coaching signal per agent, and an early-warning signal on churn and
repeat contact. The first sells itself in regulated industries.

---

## 2. WHAT — voice to text, and stop there

Keep the scope sentence tight. When the WHAT sprawls, the room stops believing it.

> **"We turn conversations into text, and text into a structured, scored record."**

That is the whole product. Two steps:

| Step | What happens |
|---|---|
| **Voice to text** | The conversation is captured and transcribed, speaker by speaker, with timings. Personal detail is masked *before* anything else sees it. |
| **Text to a record** | The transcript is classified, scored against a written rubric, and stored as one comparable record per conversation — with the quote behind every judgement. |

Two boundaries worth saying out loud, because they are what make it defensible:

- **The model never invents the score.** It supplies evidence — quotes from the transcript.
  A rubric file turns evidence into a number. *Same conversation plus same rubric equals the
  same score, on any vendor's model.* That is what survives a performance review or an audit;
  a bare number out of an AI does not.
- **No citation, no claim.** Anything factual we put in front of an agent points at an
  approved document. If we cannot cite it, we say nothing.

If asked "is this live coaching or after-the-fact analytics?" — both, same engine, different
tempo. After-the-fact is running now; live is designed and costed.

---

## 3. HOW — three seams, and none of them care where the conversation came from

This is the engineering answer to *"how do you do this irrespective of industry, channel or
format?"*. There are exactly three seams, and each one absorbs a different kind of change.

### Seam 1 — Channel: everything becomes a list of turns

In our codebase there is one object at the centre. Its definition is literally:

> *"An ordered sequence of speaker turns."* — `domain/entities/transcript.py`

A turn is: **who spoke, what they said, when**. Nothing more. Every analysis layer, every
rule, every score, every dashboard reads that object and *only* that object. None of them
can tell how it was produced.

So a channel is an adapter that produces turns:

| Channel | What the adapter does | Needs speech-to-text? |
|---|---|---|
| **Phone call** (Genesys, Amazon Connect, Five9, Teams, NICE, Avaya, Twilio) | Take the audio stream, transcribe, emit turns | Yes |
| **Email** (M365 / Graph, Gmail) | Stitch the thread, one turn per message | No — already text |
| **Chat / web messaging** | One turn per message | No |
| **SMS / WhatsApp** | One turn per message | No |
| **Meetings** (Teams, Zoom, Meet) | Recording or live stream, transcribe, emit turns | Yes |
| **Voice notes / voicemail** | Transcribe, emit turns | Yes |

> **The line to use:** "Adding a channel is writing one adapter. The AI does not change, the
> rules do not change, the scoring does not change, the dashboards do not change."

### Seam 2 — Format: inbound normalises, outbound renders

*Format* cuts the other way and is even cheaper.

- **Inbound formats** — audio, email MIME, chat JSON, a webhook payload — all normalise into
  turns at the edge. One adapter each.
- **Outbound formats** — an assist card on a desktop, a supervisor notification, a dashboard
  tile, an emailed digest, a webhook into someone else's system — are **renderers of the same
  analysis record**. Adding an output format is a rendering job, not an architecture change.

So "channel can be phone, format can be message or text or notification" is not a
complication for us. It is two lists of adapters either side of one unchanged core.

### Seam 3 — Vendor and industry: configuration, not code

- **AI vendor.** Every model call goes through one interface. We have **four** adapters
  written today — a local open-source model, OpenAI, Anthropic, and an Azure slot. Switching
  is a configuration line, and the platform refuses to silently substitute one for another,
  because the record has to say which model produced it.
- **Industry.** Three files and a document set carry all the domain knowledge:
  `taxonomy.yaml` (what we are allowed to classify things as), `rubric.yaml` (what good
  handling looks like and what each failure costs), and the approved-knowledge corpus.
  **Nothing in the engine knows the word "claim".** Change those, and the same platform does
  mortgage servicing, patient scheduling, utility billing, retail support, collections.

> **The line to use:** "The vertical is configuration. The engine is the asset."

---

## 4. SCALING IRRESPECTIVE OF PLATFORM ← spend your time here

Everything above exists to make this section credible. This is the part they should
remember, so slow down and make it concrete.

### The claim

**We are not building a healthcare call-analytics product. We are building a conversation
intelligence engine whose industry, channel, vendor and cloud are all configuration.**

The first client funds the engine. The second and third are an adapter and a config file.

### Why that is true and not marketing

Three properties, each already in the code rather than on a roadmap:

1. **One canonical object.** Turns in, structured record out. The core has no idea what a
   phone is.
2. **Everything domain-specific is a file.** Taxonomy, rubric, knowledge — all versioned
   config, reviewable by someone who does not read code.
3. **Every external thing sits behind an interface.** Model vendor, transcription vendor,
   database, telephony. Four model adapters exist today; that is the seam proven twice over,
   not asserted once.

### What it actually takes to add something — the table to put on screen

Rough effort, engineering estimates:

| Add this | What you write | Estimate |
|---|---|---|
| A new telephony platform | One audio/event adapter | 1–2 weeks |
| A new text channel (chat, SMS, WhatsApp) | One message adapter — **no transcription needed** | ~1 week |
| A new output (notification, webhook, digest) | One renderer | days |
| A new AI vendor | One provider adapter | days |
| **A new industry** | Taxonomy + rubric + approved documents, then calibrate | 3–4 weeks, **no code** |
| A new cloud | Redeploy the same containers | weeks, no redesign |

That table is the pitch. Nothing on it says "rebuild".

### The commercial shape

- **Cost does not scale per seat.** Roughly **$2.4–3.1k a month** of infrastructure carries
  ~10,000 interactions a month. Adding agents does not add licence cost.
- **The expensive part is bought once.** The rubric engine, the citation discipline, the
  privacy boundary, the multi-vendor model layer — built once, reused by every client.
- **Multi-tenant from the start.** Every stored row already carries a tenant identifier, so
  serving a second client is not a retrofit.

### If they ask "so what could we sell next?"

Same engine, no rebuild:

- **New channels for the same client** — email, chat, SMS, portal messages, meetings.
- **New verticals** — any regulated industry where an employee explains a rule to a customer.
- **Adjacent use cases** — sales-call coaching, collections compliance, complaint handling
  and regulatory reporting, onboarding and clinical-intake QA, supplier and partner calls.
- **The QA engine on its own** — deterministic, auditable conversation scoring is a product
  in its own right, independent of the live-assist half.

---

## 5. Where we honestly are (do not oversell this bit)

Being precise here is what buys you credibility for everything above.

| | Status |
|---|---|
| Transcript → classified, scored, evidence-backed record | **Built and running** |
| Deterministic scoring from a rubric file | **Built** |
| Operational dashboards over analysed conversations | **Built** |
| Four AI vendor adapters, switchable at run time | **Built** |
| Live transcription and in-call assistance | **Designed and costed, not built** |
| Email and chat channels | **Designed, not built** |

> **If pressed:** "The analysis engine is real — I can run a conversation through it on this
> call. The live and multi-channel parts are designed, costed and phased, not written."

**Phasing and money** (from the architecture document):

| Phase | Duration | Infrastructure |
|---|---|---|
| POC calibrated on real conversations | ~6 weeks | ~$0.5–1.1k/mo |
| Live pilot, a couple of queues | +6 weeks | ~$1.8–2.4k/mo |
| Production, all channels | +12 weeks | ~$2.4–3.1k/mo |

---

## 6. The ask

Pick one and be specific — vague asks get deferred.

1. **Endorse the engine as a horizontal asset**, not a one-client build.
2. **Name the second use case now** — a different channel or a different industry — so we
   prove the config-swap claim while the first build is still warm.
3. **Fund the 6-week calibration phase** on real conversations, which is what turns "the
   scores look sensible" into "the scores are defensible".

---

## 7. Hard questions, and short answers

**"How is this different from what Genesys or NICE already sell?"**
Theirs is bundled to their platform, priced per seat, and you cannot take it with you. Ours
sits *above* the platform — it can run on theirs. The rubric is the client's, the data is the
client's, and the vendor can be swapped.

**"Isn't this just ChatGPT over a transcript?"**
No. A raw model score drifts between runs and between vendors, and cannot be defended in a
performance conversation. Ours comes from a rubric file: same conversation, same rubric, same
number, every time, on any vendor. The model supplies quotes; the configuration decides.

**"What if the AI gets it wrong in front of a customer?"**
It never speaks to a customer. It puts a suggestion in front of an employee, who accepts,
edits or ignores it. Every factual claim carries a citation to an approved document, and if
there is no citation there is no suggestion.

**"What about privacy and PHI?"**
Personal detail is masked *before* any model, log, cache or index sees the text — that is a
hard boundary in the design, and it fails closed. The platform also holds no customer
records; it only analyses the conversation in front of it.

**"Which vendor are we locked into?"**
None. Four model adapters exist today, including one that runs entirely inside our own
network at effectively zero marginal cost. That local option is also what keeps the paid
vendors' pricing honest.

**"Does the cost run away as volume grows?"**
The costly path is deliberately a fixed-cost, self-hosted model rather than per-token billing.
Volume raises transcription minutes, not AI spend.

**"What is the biggest risk?"**
Transcription accuracy on poor telephone audio — everything downstream inherits it. Which is
why the first six weeks are calibration against real recordings with a measured error rate,
not a vendor demo on clean audio.

---

## 8. Lines to keep in your pocket

- "Nothing we built knows it is in healthcare, and nothing we built knows it came from a phone."
- "The engine reads one object: who said what, when. Every channel produces that object."
- "The vertical is configuration. The engine is the asset."
- "Adding a channel is one adapter. Adding an industry is three files."
- "Today QA hears two calls in a hundred. We score all hundred, the same way every time."
- "The model supplies the evidence. The configuration decides the number."
- "No citation, no claim."
- "The first client funds the engine. The second is a config file."

---

## 9. Supporting material for the call

| | |
|---|---|
| One-page overview diagram | `Gen Documents/10-high-level-diagram.svg` |
| Component architecture | `Gen Documents/10-architecture-diagram.svg` |
| Full technical architecture, options and costs | `Gen Documents/10-realtime-agent-assist-architecture.md` |
| The channel seam, in code | `Code/Backend/domain/entities/transcript.py` |
| The scoring policy, in config | `Code/Backend/config/rubric.yaml` |
| The four model adapters | `Code/Backend/infrastructure/llm/providers/` |

**If you can share your screen:** open the high-level diagram at section 4, and use the
`EMAIL · CHAT` box on the left as the proof point — it joins the same pipeline at redaction
and skips transcription entirely, because it is already text. That single box is the whole
"irrespective of channel" argument in one picture.
