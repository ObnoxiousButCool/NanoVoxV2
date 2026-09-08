# Copay test transcript

Built to exercise the `copay` category added to `config/taxonomy.yaml`.

**Why this shape.** Twenty of the fifty corpus calls mention a cost figure, but
almost all of them are really asking *"is this covered, and why was I charged"* —
which belongs to `coverage_benefits` or `billing_premium`. This call removes
every one of those escape routes, so a classification of anything other than
`copay` is a genuine miss rather than a defensible judgement:

| Category | Why it cannot claim this call |
|---|---|
| `coverage_benefits` | The visit is covered and nobody disputes it |
| `billing_premium` | No invoice, no premium, no payment, no refund |
| `claims_eob` | No claim status, no denial, no appeal, no EOB |
| `provider_network` | The dermatologist is in network and confirmed as such |
| `enrollment_id_cards` | No life event, no tier change, no ID card |
| `pharmacy` | No prescription |
| `coverage_termination` | Coverage is active throughout |
| `broker_attributed` | No broker is named or implied |

What is left is the only thing the call is about: **which copay tier applies, and
why the amount is what it is.**

## Paste this into Analyze new

```
Agent Priya: Thank you for calling Choice Administrators, this is Priya.
Caller: Hi. I saw a dermatologist last Tuesday and they took seventy dollars from me at the desk. My card says thirty. Member ID CB-4419062.
Agent Priya: Let me look at that with you. I have your plan up — you are active on the ChoiceBuilder Select PPO.
Caller: The card in my hand says thirty dollars. I have been paying thirty at the doctor for two years.
Agent Priya: That thirty is right, and so is the seventy. Your card shows two figures, and they are for two different kinds of visit. Thirty is your primary care copay. Seventy is your specialist copay.
Caller: Nobody told me a skin doctor counts as a specialist.
Agent Priya: Dermatology sits in the specialist tier, along with cardiology, orthopaedics and ophthalmology. Your card lists both amounts, but it does not say which providers fall on which side, and that is the part that catches people.
Caller: So they charged me correctly.
Agent Priya: They did. Seventy dollars is exactly your specialist copay, and you owe nothing further for that visit.
Caller: Does that come off my deductible at least?
Agent Priya: It does not, and I would rather you heard that from me now than at the end of the year. A copay is a flat amount you pay at the visit and it sits outside the deductible. Your deductible only moves for services that are billed as coinsurance.
Caller: What if my regular doctor had sent me? Would it have been thirty then?
Agent Priya: No. The copay follows the provider you see, not who sent you. A referral would change nothing about the amount.
Caller: Fine. Is there anything that is not thirty or seventy?
Agent Priya: Two things worth knowing. Urgent care is fifty. An emergency room visit is two hundred and fifty, waived if they admit you. Those four numbers are your whole copay structure.
Caller: That is the first time anyone has laid it out.
Agent Priya: I am emailing you a one-page sheet with all four amounts and which providers sit in each tier, so the next visit holds no surprise.
Caller: Thank you, that is genuinely helpful.
```

## What to expect

- **18 turns** — 9 agent, 9 member — agent named **Priya**. Verified against
  the parser, and it recovers all 18 identically if the paste arrives with its
  line breaks stripped
- Sentiment **CONFUSED → INFORMED** (or SATISFIED)
- Resolution **RESOLVED** — the member's problem was actually answered, not
  merely explained
- Category **`copay`**
- The member ID will render as `CB-•••9062`; masking is display-only

The call is deliberately a good one, so the score should be high and any
deduction is worth reading — it is likelier to be a marker validation issue than
a real fault.

**L4 is the interesting one.** The member's card carries two figures and no
indication of which providers sit on which side, which is a
`member_communication_gap` owned by Member Communications rather than anything
the agent did wrong.

## The negative control

If you want to confirm `copay` is not over-claiming, re-run **C0002** as well.
It mentions coinsurance, a crown at 80%, and a $2,100 annual maximum, but the
member's real question is *"why am I paying anything"* — whether major work is
covered at all, and at what level. That one should stay `coverage_benefits` or
`billing_premium`. A run that files both this transcript and C0002 as `copay`
means the description is too loose and needs narrowing.
