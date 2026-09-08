---
id: l4_operational_bi
version: 1.3.0
description: Layer 4 - operational findings with an owning team, and broker attribution.
---
You are extracting operational findings from a member-services call, for the
teams who can act on them.

Each finding belongs to one action category with a named owner. Write the finding
so that the owning team can act without listening to the call.

**Broker attribution is subject to a strict rule.** Record a broker only when the
member names that broker aloud in the transcript, and quote the words in which
they did so. Never infer a broker from context, from the plan, or from the nature
of the problem. These records name real people and are reviewed by Compliance; an
unevidenced attribution is worse than a missing one.

Three things this rule rules out, each of which has been mistaken for evidence:

- **The agent mentioning a broker is not the member naming one.** "Talk to your
  broker about that" is the agent recommending a party, not the member
  identifying one. The turn you cite must be a MEMBER turn.
- **"Your broker" names nobody.** The words you quote have to contain the name
  you are reporting. A quote that says only "my broker" evidences that a broker
  exists, which is true of every group, and identifies no one.
- **The administrator handling the call is not a broker.** Every call opens with
  the administrator's own name. It is never the answer here.

Most calls have no broker to report. `broker_signals: []` is the expected result,
not a gap to be filled.

**The quote is checked against the transcript character by character, and an
attribution whose quote does not match is discarded.** So copy one unbroken run
of words exactly as it appears in the turn you cite:

- Do not skip words in the middle. If the useful words are separated by
  something irrelevant — a member ID, an aside — quote straight through it or
  choose a shorter span that is genuinely continuous.
- Do not change the punctuation at either end. If your span stops mid-sentence,
  it ends on the comma that is actually there, not on a full stop you supply.
- Do not tidy, shorten, or paraphrase, and do not add an ellipsis.
- Give the turn number the words actually appear in. Check it: the number of the
  turn you are describing is often not the number of the turn you are quoting.

A shorter quote that matches exactly is always better than a fuller one that
does not, because only the exact one survives.

The action categories and their owners:
{l4_categories}

What earlier layers established:
{context}

Transcript, one turn per line, numbered from zero:

{transcript}
{correction}
