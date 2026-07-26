# prompt-forge — architecture patterns

Six patterns. Name the one you used in output block 3. Examples below are
skeletons, not templates to paste verbatim.

---

## 1. Role + Contract

**Use when** the output *shape* is the hard part and the reasoning is routine.

```
You are a <specific role, not "an expert">.

<Task in one sentence.>

Output contract:
- <field>: <type, constraint>
- <field>: <type, constraint>
Return nothing outside this structure.
```

- "You are a claims adjuster with 15 years in commercial property" outperforms
  "You are an expert" — a specific role carries priors a generic one doesn't.
- On Claude, back the contract with `output_config.format` rather than trusting
  prose. Prose is the fallback, not the mechanism.
- Don't stack a persona *and* a rubric *and* few-shot examples here. That's a
  different pattern.

---

## 2. Decomposed Steps

**Use when** order matters and skipping a stage silently degrades the output.

```
Complete these in order. Do not skip a step.

1. <observation step — gather, don't decide>
2. <analysis step>
3. <decision step>
4. <output step, referencing the contract>

If step N cannot be completed, say which and stop.
```

- The final clause matters: without it, models paper over a failed middle step.
- Numbered steps beat prose for anything with a real dependency chain.
- On literal-following models (Opus 4.7, Sonnet 5), each step is followed as
  written — so an imprecise step 2 produces an imprecise step 3, reliably.

---

## 3. Rubric-Graded

**Use when** quality is judgeable but not binary. Ship the rubric *inside* the
prompt — the model can only optimise against criteria it can see.

```
<Task.>

Your output will be judged on:
| Criterion | What full marks looks like |
|---|---|
| <name> | <concrete description> |
| <name> | <concrete description> |

Before finishing, check your output against each criterion.
```

- ⚠️ **The last line is model-dependent.** On Opus 5, self-check instructions
  cause over-verification — **omit it** there and let the model's own
  verification do the work. Keep it on models that don't self-verify.
- Rubric criteria must be independently gradeable. "Well-structured" is not;
  "each section has a heading and ≤3 paragraphs" is.

---

## 4. Few-Shot Anchored

**Use when** the format is idiosyncratic enough that describing it costs more
tokens than showing it.

```
<Task in one line.>

<input> → <output>
<input> → <output>
<input> → <output>

<actual input> →
```

- 2–5 examples. Beyond 5, returns diminish and cache cost rises.
- **Positive examples only.** A vivid negative example describes the thing you're
  trying to avoid, and current models sometimes reproduce it. If a failure mode
  must be named, use Constraint-Bounded instead.
- Examples should span the variance you expect, not cluster on the easy case.
- Cover the awkward edge case in an example rather than in a rule — it lands
  better and costs fewer tokens.

---

## 5. Constraint-Bounded

**Use when** you know the specific failure modes.

```
<Task.>

Boundaries:
- <boundary as a positive rule, e.g. "cite a line number for every claim">
- <boundary>

If the input falls outside these, say so rather than guessing.
```

- **State the boundary, not a list of prohibitions.** "Cite a line number for
  every claim" beats "don't make things up" — the first is checkable, the second
  is a mood.
- The escape hatch (last line) prevents the model from forcing a bad fit.
- Keep boundaries under ~6. More than that and they start conflicting; run the
  step 8 contradiction scan hard.

---

## 6. Tool-Mediated

**Use when** the model needs facts it cannot have, or must act rather than answer.

```
<Task.>

Use <tool> when <specific trigger condition>.
Do not answer from prior knowledge when <condition> applies.
```

- **The trigger condition belongs in the tool's own `description`, not only in
  the system prompt.** Prescriptive descriptions ("Call this when the user asks
  about current prices or recent events") measurably raise should-call rate over
  descriptions that only state what the tool does.
- Direction of the fix is model-dependent: Opus 4.7 and Opus 4.8 **under**-reach
  for tools and need encouragement; Opus 5 delegates to subagents **more** freely
  and needs a cap. Check the model file before writing either.
- For a fixed label set, a tool with an `enum` field beats a prose instruction.

---

## Combining

Two patterns compose cleanly. Common pairs:

| Combination | Fits |
|---|---|
| Role + Contract **and** Constraint-Bounded | Structured extraction with known failure modes |
| Decomposed Steps **and** Tool-Mediated | Agent loops |
| Rubric-Graded **and** Few-Shot Anchored | Subjective output with a house style |

Three is a smell. Four means the task should be two prompts.
