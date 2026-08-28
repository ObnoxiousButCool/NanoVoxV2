# Call #85 — Agent Reads From Script Without Listening to the Actual Question

- **Agent:** Kayla
- **Tier:** POOR
- **Score:** 39/100
- **Sentiment Arc:** NEUTRAL → ANNOYED
- **Resolution:** UNRESOLVED
- **Duration:** ~5 min
- **Topics:** not listening, script reading, maternity, hospital network, poor handling

**Member context:** Preeti Raman, 35, CalChoice HMO, asking whether a specific hospital is in network for a planned birth

## Transcript

Agent Kayla: Thank you for calling Choice Administrators, my name is Kayla, how can I provide you with excellent service today?
Member: Hi, I'm 32 weeks pregnant and I want to confirm that St. Catherine's Hospital is in my network for delivery. Member ID
CHM-6650092.
Agent Kayla: Absolutely, I can help you find a provider today. Are you looking for a primary care physician or a specialist?
Member: Neither. I'm asking about a hospital. St. Catherine's. For delivery.
Agent Kayla: Okay, and did you want me to search by zip code or by name?
Member: By name. St. Catherine's Hospital.
Agent Kayla: And what type of provider is that?
Member: It's a hospital.
Agent Kayla: Got it. Let me search... I'm showing a St. Catherine's Medical Group. Is that it?
Member: I don't know. I'm asking about the hospital where I'm scheduled to deliver.
Agent Kayla: The medical group is in-network.
Member: But is the hospital in-network? Those might be different entities. The medical group could be the physician practice.
Agent Kayla: It says in-network.
Member: What says in-network? The medical group or the hospital?
Agent Kayla: The St. Catherine's I'm seeing.
Member: Can you tell me the full entity name and the address?
Agent Kayla: It just says St. Catherine's Medical Group.
Member: So you can't confirm the hospital.
Agent Kayla: I mean, it's showing as in-network.
Member: I'm going to call the hospital directly. Thank you.
Agent Kayla: Thank you for calling Choice Administrators, have a wonderful day.

## AI Insights Panel — NanoVox 5-Layer Output

L1 — Transcription & Understanding: Call type: Hospital network verification — maternity. 2 speakers. Member: 32 weeks pregnant.
Member tone: neutral → annoyed. Agent tone: scripted, non-responsive to actual content. Duration: 5 min. Member abandoned the channel
to self-serve.
L2 — Call Insights: Member sought confirmation that a specific hospital is in-network for a scheduled delivery. Agent repeatedly failed to
distinguish between a medical group and a hospital facility, could not confirm the facility, and closed with a scripted farewell. Resolution:
UNRESOLVED — member left to verify independently.
L3 — Agent Quality & Scoring: Agent Score: 39/100. NEGATIVE MARKERS: opened with a scripted greeting and immediately asked a
question the member had already answered (-), did not register 'hospital' after three separate corrections (-), conflated a medical group with
a hospital facility — a material distinction for delivery coverage (-), could not provide entity name or address when asked (-), gave a
confident answer about an entity she could not identify (-), scripted close on an unresolved call with a 32-week pregnant member (-). Zero
listening markers detected.
L4 — Operational BI: AGENT COACHING — CRITICAL: active listening failure. The member stated her question clearly and corrected the
agent three times. PROCESS BREAKDOWN: provider search interface apparently does not distinguish facility type clearly, allowing a
medical group and a hospital to be conflated. This is a high-consequence error for maternity — delivering at an out-of-network facility can
cost a member tens of thousands. Recommend: (1) facility-type filter mandatory in provider search, (2) maternity delivery facility verification
protocol requiring entity name and address confirmation read back to the member, (3) QA review of Kayla's listening markers across all
calls.
L5 — Real-Time Agent Assist: RT Assist SHOULD have triggered at 0:45 — 32 weeks pregnant + hospital network verification is a
high-consequence verification requiring facility-level confirmation. Should have surfaced: hospital facility record with full entity name,
address, NPI, and delivery service line confirmation. No trigger fired.
