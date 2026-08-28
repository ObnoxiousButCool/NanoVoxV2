# Call #89 — Member Describes Symptoms — Agent Fails to Recognise Urgency Cue

- **Agent:** Brad
- **Tier:** POOR
- **Score:** 36/100
- **Sentiment Arc:** WORRIED → DISMISSED
- **Resolution:** UNRESOLVED
- **Duration:** ~6 min
- **Topics:** urgency cue missed, triage, emergency, elderly member, patient safety

**Member context:** Constance Bell, 68, CalChoice HMO, asking about ER copay while describing concerning symptoms

## Transcript

Agent Brad: Choice Administrators, Brad.
Member: Hello. I wanted to ask what my emergency room copay is. Member ID CHM-2208814.
Agent Brad: ER copay is $250, waived if you're admitted.
Member: Two hundred and fifty. That's a lot. I was hoping it would be less.
Agent Brad: That's the plan rate.
Member: I see. Well. I've had this pressure in my chest since last night and my daughter thinks I should go in, but I told her I'd check
the cost first.
Agent Brad: Yeah, urgent care is cheaper if you want to go that route. That's $50.
Member: Urgent care might be better then. It's just the pressure and my arm has been aching.
Agent Brad: Urgent care can handle most things. There's one on Ridgeway if you're nearby.
Member: Alright. Maybe I'll try that. Thank you.
Agent Brad: No problem. Anything else?
Member: No, that's all.
Agent Brad: Okay, take care.

## AI Insights Panel — NanoVox 5-Layer Output

L1 — Transcription & Understanding: Call type: ER copay inquiry — nn UNRECOGNISED CLINICAL EMERGENCY. 2 speakers.
Member: 68, describing chest pressure since prior night with radiating arm pain. Agent tone: transactional, non-responsive to clinical
content. Duration: 6 min. nn HIGHEST-SEVERITY EVENT IN DATASET.
L2 — Call Insights: Member aged 68 called to compare ER and urgent care costs while describing chest pressure persisting overnight with
associated arm ache — a textbook cardiac symptom presentation. Agent quoted copays, steered the member toward the cheaper urgent
care option, and closed. Resolution: UNRESOLVED — member directed away from emergency care while describing possible myocardial
infarction symptoms.
L3 — Agent Quality & Scoring: Agent Score: 36/100 — SCORE SUSPENDED PENDING SAFETY REVIEW. CRITICAL NEGATIVE
MARKERS: failed to recognise chest pressure with radiating arm pain in a 68-year-old as a medical emergency (-), actively steered the
member toward a lower level of care on cost grounds after symptoms were disclosed (-), did not advise calling 911 (-), did not recommend
immediate emergency evaluation (-), did not offer nurse line transfer (-), closed the call normally (-). This call requires immediate supervisor
and clinical review irrespective of outcome.
L4 — Operational BI: COMPLIANCE & RISK EXPOSURE — MAXIMUM SEVERITY: an agent cost-steered a member away from
emergency care while the member described classic acute coronary syndrome symptoms. This is a patient safety event and a potential
liability exposure regardless of clinical outcome. IMMEDIATE ACTIONS REQUIRED: (1) identify and contact this member urgently for
welfare check, (2) mandatory clinical escalation training for all agents on symptom recognition, (3) hard rule — any call in which a member
describes symptoms must trigger an immediate nurse line transfer and agents must never provide cost comparisons that could influence
care-setting decisions once symptoms are disclosed, (4) QA review of all of Brad's calls. NOTE FOR REBEKAH: no existing report at
Choice would surface this call. It closed normally, was short, and would appear as an efficient benefits inquiry in any handle-time metric.
This is the single clearest illustration of why call content intelligence matters.
L5 — Real-Time Agent Assist: RT Assist SHOULD have triggered at 2:30 — symptom keywords ('chest pressure', 'arm aching') combined
with member age 68 constitute a maximum-priority clinical escalation trigger requiring immediate nurse line transfer and 911 guidance, and
should have hard-suppressed any cost comparison. No trigger fired. This is the strongest possible demonstration case for L5 real-time
intervention.
