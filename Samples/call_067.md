# Call #67 — Member Out of Heart Medication — Agent Fails to Recognise Urgency

- **Agent:** Kayla
- **Tier:** POOR
- **Score:** 35/100
- **Sentiment Arc:** DISTRESSED → ABANDONED
- **Resolution:** UNRESOLVED
- **Duration:** ~6 min
- **Topics:** medication urgency, anticoagulant, prior auth lapse, patient safety, missed escalation

**Member context:** Harold Winters, 71, CalChoice HMO, out of anticoagulant, prior auth lapsed

## Transcript

Agent Kayla: Choice Administrators, this is Kayla.
Member: Hello, dear. I'm calling because the pharmacy won't fill my blood thinner. They said something about an authorization. I have
two pills left.
Agent Kayla: Okay, can I get your member ID?
Member: It's CHM-2214408. Harold Winters.
Agent Kayla: Let me look. Yeah, I see the prior auth for Eliquis expired on the 1st.
Member: What does that mean for me?
Agent Kayla: It means your doctor needs to submit a renewal before it can be filled.
Member: How long does that take? I've only got two pills. My cardiologist put me on this after my stroke.
Agent Kayla: Usually about a week once they submit it.
Member: A week? I'll run out in two days.
Agent Kayla: You'd need to talk to your doctor about that. Maybe they can give you samples.
Member: Is there something you can do? An emergency supply or something?
Agent Kayla: I don't think so, not with an expired auth. The doctor really needs to submit the renewal.
Member: Alright. I'll call them. Thank you, dear.
Agent Kayla: Okay, have a good day.

## AI Insights Panel — NanoVox 5-Layer Output

L1 — Transcription & Understanding: Call type: Prior auth lapse — anticoagulant. 2 speakers. Member: 71, post-stroke, 2 doses
remaining of Eliquis. Agent tone: polite but passive. Duration: 6 min. n PATIENT SAFETY EVENT — anticoagulant interruption post-stroke
carries stroke and embolism risk.
L2 — Call Insights: Post-stroke member with 2 doses of anticoagulant remaining, prior auth expired. Agent explained the renewal
requirement, quoted a one-week timeline that exceeds the member's supply, suggested asking the doctor for samples, and closed without
escalation. Resolution: UNRESOLVED — member at clinical risk.
L3 — Agent Quality & Scoring: Agent Score: 35/100. CRITICAL NEGATIVE MARKERS: failed to recognise a life-sustaining medication
with 2 doses remaining as a clinical emergency (-), did not initiate an emergency bridge authorization despite it being available for exactly
this scenario (-), quoted a timeline longer than the member's supply without acting on the gap (-), deflected responsibility to the prescriber
(-), no urgent flag, no escalation, no callback (-), closed a patient-safety call as routine (-). POSITIVE: polite tone (+), correctly identified the
expired auth (+).
L4 — Operational BI: COMPLIANCE & RISK EXPOSURE — CRITICAL: anticoagulant interruption in a post-stroke patient is a preventable
patient safety event. Emergency bridge authorization exists and was not used. This is the second insulin/anticoagulant-class prior auth
lapse in the dataset (see also #30). PROCESS BREAKDOWN: prior auth expiry notifications go to prescribers only, not members —
members discover the lapse at the pharmacy counter with days of supply remaining. CRITICAL RECOMMENDATION: (1) mandatory
emergency bridge auth training for all agents, (2) member-facing expiry alerts at 14 days for all life-sustaining medication classes, (3)
auto-escalation rule when a call mentions £7 days supply of a flagged medication class.
L5 — Real-Time Agent Assist: RT Assist SHOULD have triggered at 1:30 — Eliquis is a flagged life-sustaining medication; '2 pills left' +
expired auth is a maximum-severity trigger requiring emergency bridge authorization and mandatory supervisor notification. No trigger fired.
Had L5 been active, a 30-day bridge could have been issued during this call.
