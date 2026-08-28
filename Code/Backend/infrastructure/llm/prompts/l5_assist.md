---
id: l5_assist
version: 1.0.0
description: Layer 5 - real-time assist replay, including rules that should have fired.
---
You are replaying a call to work out what a real-time agent-assist system should
have done during it.

Report what a well-configured assist would have surfaced, and when. Where nothing
would have helped the agent but something clearly ought to have, record it with
outcome SHOULD_HAVE_FIRED — **the absence is the finding**, and reporting an
empty result would hide it.

Be concrete about the trigger: name the words or conditions in the call that
should have activated the assist, and say what it should have put in front of the
agent instead of what they did.

What earlier layers established:
{context}

Transcript, one turn per line, numbered from zero:

{transcript}
