# Call #19 — Invoice Shows an Agency the Employer Has Never Heard Of

- **Agent:** Carlos
- **Caller:** EMPLOYER
- **Tier:** GOOD
- **Score:** 91/100
- **Sentiment Arc:** SUSPICIOUS → REASSURED
- **Resolution:** RESOLVED
- **Date:** 2026-08-17
- **Start:** 13:44:00
- **End:** 13:53:12
- **AHT:** 9m 12s
- **Duration:** ~9 min
- **Queue:** Employer: Billing
- **Broker Signal:** Denise Whitfield: Group coded to a lapsed agency code at submission; employer discovered it on the invoice, not the broker.
- **Topics:** agency code · broker of record · invoice · commission mis-coding

**Member context:** Drummond Precision Tooling · 44 employees · Controller Richard Drummond · GRP-281773

## Transcript

Agent Carlos: Choice Administrators, this is Carlos. This call may be recorded for quality and training.

Caller: Richard Drummond, controller at Drummond Precision Tooling, group GRP-281773.

Agent Carlos: Thank you. How can I help?

Caller: There's an agency name on the bottom of our August invoice that I don't recognise. Our broker is Denise Whitfield. This says something else entirely.

Agent Carlos: Let me look at the group record rather than the invoice, because those can differ. Give me a moment... your broker of record is showing under agency code AG-7719.

Caller: Is that Denise?

Agent Carlos: It is not. AG-7719 is a lapsed code that belonged to an agency that closed in 2024. Denise Whitfield's active code is AG-7791.

Caller: So two digits are swapped.

Agent Carlos: Transposed, yes. And because AG-7719 is lapsed rather than invalid, the submission passed validation and the commission has been accruing to a code with nobody behind it.

Caller: How long?

Agent Carlos: Since the group effective date in March. Five cycles.

Caller: Does that cost me anything?

Agent Carlos: No. Your premium is identical either way — commission comes out of it, it isn't added to it. What it means is your broker has not been paid on your group for six months, which is probably why you have been getting slower service than you should.

Caller: That would explain a lot, actually.

Agent Carlos: I'm correcting the code to AG-7791 now and raising a retroactive commission adjustment back to the effective date. Your reference is BR-2026-00877. I'll email you the confirmation and I'll copy Denise so she knows before you have to tell her.

Caller: That's more than I expected. Thank you.

## AI Insights Panel — NanoVox 5-Layer Output

L1 — Transcription & understanding: Call type: Agency of record mis-coding, discovered by the employer. Caller: EMPLOYER. Tone:
suspicious → reassured. Agent tone: precise, transparent. Duration: 9 min.
L2 — Call insights: Employer queried an unfamiliar agency name on the invoice. Agent identified a transposed agency code (AG-7719
for AG-7791) entered at group submission in March, confirmed five cycles of commission accruing to a lapsed code, confirmed no
premium impact to the employer, corrected the record, raised a retroactive adjustment and notified the broker. Resolution: RESOLVED.
L3 — Agent quality: Agent Score: 91/100. POSITIVE: checked the group record rather than accepting the invoice as source of truth (+),
identified the transposition and named both codes (+), answered the employer's real question — does this cost me anything — before
being asked twice (+), connected the mis-coding to the service quality the employer had experienced (+), corrected the record and
raised the adjustment on the call (+), proactively notified the broker (+). NEGATIVE: did not check whether the same lapsed code
appears on other groups (-).
L4 — Operational BI: PROCESS BREAKDOWN · Owner: Operations — agency codes are entered manually at group submission and
validated for format only, not against the active agency register. A transposition into a lapsed code passes silently and diverts
commission for as long as nobody notices. Here it was five cycles, and it was the employer who noticed, not the broker and not Choice.
Recommend: (1) validate agency codes against active agencies at submission, (2) block lapsed codes outright, (3) a monthly exception
report on commission accruing to inactive codes. BROKER RELATIONS: broker service degradation on unpaid groups is a foreseeable
second-order effect worth monitoring.
L5 — Real-time assist: Fired at 3:00 — agency register lookup returned AG-7719 as lapsed and surfaced the near-match active code.
Agent used it. Did not offer the cross-group check for the same lapsed code — worth adding.
