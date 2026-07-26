# prompt-forge — the 9-step pipeline in detail

Each step names its gate. A gate that fails stops the pipeline; it does not
degrade into a guess.

---

## Step 1 — Resolve the target model

A prompt is not portable. The same instruction can be optimal on one model,
neutral on a second, and a **400 error** on a third.

1. Did the user name a model? Use it.
2. Not named but the surface is obvious (a Claude Code skill, an `anthropic` SDK
   call) → assume that family and **say so in the output**.
3. Otherwise **ask**. One question, in step 5's batch.

Then open `references/models/<family>.md`, read `last_verified:`, and quote both
the ID and the date in output block 1.

**Gate:** never invent a model ID. If the file doesn't list it, say the file
doesn't list it.

---

## Step 2 — Score the input

Score the *request*, before writing. This sets expectations and tells you whether
step 5 is mandatory.

| Axis | 0 | 10 |
|---|---|---|
| **Clarity of task** | "make it better" | one unambiguous operation named |
| **Success criteria** | absent | falsifiable, checkable by a third party |
| **Input specification** | unknown shape | shape + variability + volume stated |
| **Output contract** | unstated | exact schema/format given |
| **Constraint awareness** | none | length, cost, latency, tone all stated |

Total < 20/50 → step 5 is **mandatory**, not optional.

---

## Step 3 — Extract the 9 intent dimensions

Fill the table from SKILL.md. Mark genuine gaps `?` rather than defaulting
silently — a silent default is a decision the user didn't make.

Order the `?` entries by how much a wrong assumption would cost. That ordering
*is* your step 5 question list.

---

## Step 4 — Gate on success criteria

Write one sentence: *"This prompt succeeds when …"*

It must be falsifiable. Test it: could a third party, given an output, decide
pass or fail without asking you? If not, it isn't criteria.

| Not criteria | Criteria |
|---|---|
| "a good summary" | "≤120 words, mentions every numbered finding, no new claims" |
| "clean JSON" | "parses; matches schema X; `price` is a number not a string" |
| "sounds professional" | "no contractions, no exclamation marks, second person" |

**Gate: STOP if you cannot write it.** Do not proceed with a plausible-sounding
placeholder. This is the most common root cause of a prompt that "doesn't work" —
it was never evaluable in the first place.

---

## Step 5 — Clarify, max 3 questions

Use `AskUserQuestion`. All questions in **one** call.

- Hard cap 3. If you have more, you have not prioritised — pick the three whose
  answers change the prompt most.
- Never drip-feed one question per turn.
- Each option gets a real consequence in its `description`, not a restatement.
- Recommend one, put it first, mark it `(Recommended)`.

If the user already answered something earlier in the session, don't re-ask it.

---

## Step 6 — Select an architecture

Pick exactly one from `architectures.md` and name it in output block 3. Naming it
makes the shape reviewable; an unnamed prompt is just prose.

Signals:

- Output shape is the hard part → **Role + Contract**
- Order of operations matters → **Decomposed Steps**
- "Good" is a spectrum → **Rubric-Graded**
- Format is weird and hard to describe → **Few-Shot Anchored**
- Specific known failure to prevent → **Constraint-Bounded**
- Needs facts it can't have → **Tool-Mediated**

Combining two is fine. Combining four means the task should be split.

---

## Step 7 — Apply the model-specific transform

Write the prompt using **only** constructs the model file permits.

Checklist per construct:

- [ ] Sampling params — is `temperature` even accepted? (Not on Fable 5 / Opus 5 / 4.8 / 4.7)
- [ ] Reasoning — the lever is `effort`, not `budget_tokens`. Is thinking on by default on this model?
- [ ] Output shape — structured outputs, not prefill
- [ ] Instruction intensity — literal-following models overtrigger on `CRITICAL:`
- [ ] Self-verification — does this model already do it? (Opus 5: yes, so **omit** the instruction)
- [ ] Verbosity — prompt for it; don't reach for `effort`
- [ ] Tool guidance — state the *trigger condition* inside each tool's `description`
- [ ] Cache shape — if volume is high, is the prefix byte-stable?

---

## Step 8 — Contradiction and dead-construct scan

Two passes over the drafted prompt.

**Dead constructs.** Grep your own draft against the model file's dead-construct
table. Any hit → fix before shipping. This is the step that justifies the skill
existing; do not skip it because the prompt "looks fine".

**Contradictions.** Common pairs:

| A | B | Why it conflicts |
|---|---|---|
| "be concise" | "explain your reasoning in detail" | Directly opposed |
| "output only JSON" | "explain any assumptions" | Explanation breaks the contract |
| "never ask questions" | "clarify if ambiguous" | Unresolvable |
| "think step by step" | thinking-on model + effort set | Redundant; adds noise |
| "double-check your work" | Opus 5 | Verified to cause over-verification |
| a rubric | a conflicting hard rule elsewhere | Model picks one, unpredictably |

Also scan for: instructions with no observable effect, prohibitions that describe
the target vividly enough to suggest it, and rules that apply to one example but
were meant to generalise (literal-following models will not generalise them).

---

## Step 9 — Self-critique and re-score

| Axis | 0 | 10 |
|---|---|---|
| **Model fit** | uses constructs this model rejects | idiomatic for this exact model |
| **Specificity** | vague adjectives | concrete, checkable instructions |
| **Contract clarity** | output shape implied | output shape unambiguous |
| **Failure coverage** | known failure modes unaddressed | each one has a counter |
| **Efficiency** | bloated, cache-hostile | tight, stable prefix |
| **Evaluability** | can't tell pass from fail | success criteria embedded or explicit |

Report the total, the **delta against step 2**, the weakest axis, and the single
change that would lift it most.

If total < 42/60: iterate **once**. If it's still below, ship it and say so
plainly with the reason — a scored-6 prompt with an honest note beats a scored-6
prompt described as finished.

Never round up. Never describe an unverified model fact as verified.
