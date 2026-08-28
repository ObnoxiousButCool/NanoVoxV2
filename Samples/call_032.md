# Call #32 — Coverage Showing Inactive at Pharmacy — Plan Year Start Glitch

- **Agent:** Michael
- **Tier:** GOOD
- **Score:** 96/100
- **Sentiment Arc:** ANXIOUS → RELIEVED
- **Resolution:** RESOLVED
- **Duration:** ~9 min
- **Topics:** coverage effective date, enrollment gap, pharmacy claim, plan year, system error

**Member context:** Alicia Santos, 27, CalChoice HMO, coverage showing inactive on January 2nd despite enrolling in November

## Transcript

Agent Michael: Choice Administrators member services, this is Michael.
Member: Hi, Michael, Alicia Santos, member ID CHM-9901774. I enrolled in my plan in November for January 1st. It's January 2nd
today and I went to pick up a prescription and the pharmacy is saying my coverage isn't active in their system. Did something go
wrong?
Agent Michael: Alicia, this is actually more common than it should be at the very start of a new plan year. Let me look at your account
right now. I can see your enrollment — effective January 1st, and your status in our system shows active. The issue is likely a pharmacy
system lag — insurance carrier data sometimes takes 24 to 48 hours to propagate fully to pharmacy networks at the start of a plan year.
Member: So I'm active but the pharmacy doesn't know it yet?
Agent Michael: That's exactly right. I can give you a temporary override code to give to the pharmacist — they can use it to process your
claim directly through our system while their cached data catches up. Are you still at the pharmacy or did you leave?
Member: I'm still here. I was waiting to call you.
Agent Michael: Perfect. Give the pharmacist the following information: BIN number 610097, PCN number ADV, Group number
CHOICE2026, and your member ID CHM-9901774. Tell them to clear their current response and re-adjudicate using these numbers
manually.
Member: BIN 610097, PCN ADV, Group CHOICE2026. Okay, giving this to her now.
Agent Michael: I'll stay on the line while they process it.
Member: She's entering it... she's getting a response... she says it went through. My copay is $15.
Agent Michael: Perfect. That's exactly right for your tier. The pharmacy system will fully update over the next day or two, so this
shouldn't happen again. But if it does in the next 48 hours with any prescription, you can call us back and we'll do the same thing.
Member: That was genuinely stressful for a minute there. I thought I didn't have insurance.
Agent Michael: I completely understand — that feeling of 'my insurance isn't working' is one of the worst moments as a patient. You
have coverage. It just took a quick manual push to confirm it. Is there anything else I can help with today?
Member: No, I'm good. Thank you for staying on the line. That made all the difference.

## AI Insights Panel — NanoVox 5-Layer Output

L1 — Transcription & Understanding: Call type: Coverage verification — pharmacy system lag, plan year start. 2 speakers. Member tone:
anxious at pharmacy, relieved. Duration: 9 min. Real-time resolution: member at pharmacy during call.
L2 — Call Insights: New plan year enrollment not yet propagated to pharmacy network. Agent provided BIN/PCN/Group override codes,
stayed on line while pharmacist processed, confirmed successful claim. Resolution: RESOLVED — prescription filled during call.
L3 — Agent Quality & Scoring: Agent Score: 96/100. Root cause identified immediately as system lag (+), override codes provided
efficiently (+), stayed on line until resolution confirmed (+), explained propagation timeline for future reference (+), empathetic framing of
member's 'insurance not working' stress (+). Exemplary real-time problem-solving.
L4 — Operational BI: BI Flag: Plan year start (January 1-3) generates 3x normal pharmacy coverage verification call volume — 89%
caused by pharmacy system propagation lag, not actual enrollment errors. Recommend: proactive member SMS on Jan 1 with
BIN/PCN/Group codes and instructions for pharmacist, reducing call volume significantly. Pharmacy network real-time API sync at plan year
transition is a longer-term fix.
L5 — Real-Time Agent Assist: RT Assist triggered at 2:00: 'inactive at pharmacy + January 2nd + enrollment confirmed in system' pattern
recognized — plan year propagation lag identified immediately, BIN/PCN/Group override codes surfaced to agent without manual lookup.
Resolution protocol prepared in <30 seconds.
