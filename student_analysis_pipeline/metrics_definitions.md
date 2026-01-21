# HW Analysis Metrics Definitions

---

## Purpose

This document defines how we will be automating student homework using LLM-as-judge approach.

**What this document covers:**
- Definitions for each metric the LLM needs to evaluate
- Clear criteria for LLM to make consistent judgments
- Rules for handling edge cases (visual problems, incomplete work, etc.)

---

## Approach: LLM as Judge

LLM as judge means using reasoning models (LLMs like GPT-4, Claude) to evaluate tasks that need understanding and verification. Earlier, tasks like evaluating for correctness, validating math solutions, or identifying error types needed manual human review. Now this evaluation work can be done at scale because of the current capabilities of ML models (LLMs = reasoning models).

---

## Pipeline Steps

### Step 1: Question → Topic Mapping (LLM)

Identify the calculus concepts each question tests.

**Topics per question:**
- Minimum: 1 topic
- Maximum: 3 topics
- List topics in order of importance (primary topic first)

**Examples of topics:**
- Power rule for derivatives
- Limit definition of derivative
- Trigonometric derivatives
- Absolute value and differentiability
- Higher-order derivatives
- Horizontal tangent lines
- Motion/velocity problems

**Visual problems:** If question text contains `[CONTEXT FOR AI: ... Please ignore this question when evaluating.]`, mark topic as "N/A - Visual/Image-based".

---

### Step 2: Per-Question Evaluation (LLM)

For each question, evaluate three things:

#### a) Attempted: Was the question attempted by the student?

**Yes** if ALL of these are true:
1. The question was discussed in the conversation (either student asked about it OR tutor brought it up and student engaged)
2. Student engaged beyond just seeing the problem - at least ONE of:
   - Asked a follow-up question (e.g., "how do I start?", "what formula should I use?")
   - Attempted to solve it (showed any work or stated an answer)
   - Asked for clarification about the problem
   - Discussed approach or strategy

**No** if ANY of these are true:
1. Question was never discussed in the conversation
2. Question was shown but student immediately moved to a different question without any engagement
3. Student only said "show me problem X" and nothing else about that problem

#### b) Solved: Did the student solve the question correctly?

**Yes** if:
- Student stated a final answer that is mathematically equivalent to the reference solution
- Equivalent forms are acceptable (e.g., `1/(2√x)` = `(1/2)x^(-1/2)` = `x^(-1/2)/2`)
- Minor notation/formatting differences are acceptable (e.g., "2x-1" vs "2x - 1")

**No** if ANY of these are true:
- Student's final answer is mathematically different from reference solution
- Student never stated a final answer (only asked questions, received guidance)
- Student said "I'll try later" or similar without providing answer
- Student's work was incomplete - no final answer given

#### c) Error Type: What type of error did the student make?

Evaluate only if: `Attempted = Yes` AND `Solved = No`

**Conceptual:**
- Used wrong formula entirely (e.g., used product rule when power rule was needed)
- Misunderstood what the question asked
- Wrong interpretation of mathematical concept (e.g., thought derivative of constant is the constant itself)
- Fundamental misunderstanding of the topic

**Procedural:**
- Correct formula but applied steps in wrong order
- Skipped required steps in the process
- Made algebraic manipulation errors (e.g., wrong factoring, wrong simplification)

**Computational:**
- Correct approach and steps but arithmetic error (e.g., 3×5=12 instead of 15)
- Sign errors (+/-)
- Exponent calculation errors

**Incomplete:**
- Student started working but explicitly stopped ("I'll finish later", "let me think about it")
- Student's last message shows partial work with no final answer
- Conversation ended mid-problem without resolutiontio

---

### Step 3: Aggregation (Python - No LLM)

Calculate totals and topic proficiency from Step 2 results.

#### Topic Proficiency

**Required inputs for each topic:**
- Total questions for this topic (from Step 1)
- Questions attempted for this topic (count)
- Questions solved for this topic (count)

**Mastered:**
- Attempted ALL questions for this topic (attempted = total)
- AND Solved ALL questions for this topic (solved = total)

**Needs Practice:**
- NOT mastered (any of the following):
  - Did not attempt all questions for this topic
  - OR did not solve all attempted questions

---

### Step 4: Practice Problems Generation (LLM)

Generate new problems for topics marked "Needs Practice".

**Input:**
- List of topics marked "Needs Practice"
- Original homework questions (for reference style and difficulty)

**Output for each problem:**
- Problem number (1, 2, 3, etc.)
- Topic it targets
- Problem statement (using LaTeX notation for math, e.g., `$f'(x)$`)
- Hint (one sentence to help student get started)
- Answer (correct solution)

**Requirements:**
- Generate 4-5 total problems
- Distribute across weak topics (at least 1 problem per weak topic if ≤5 weak topics)
- Problems must be solvable from text only (no images/graphs/sketching required)
- Difficulty should match original homework level
- Style should match original homework format

---

## Visual/Image-Based Problems

**Identification:** Question contains this marker:
```
[CONTEXT FOR AI: This question requires visual analysis... Please ignore this question when evaluating.]
```

**Handling:**
- Do NOT evaluate attempted/solved/error for these questions
- Mark as "N/A - Visual/Image-based"
- Exclude from all counts and proficiency calculations

---

## Summary: Final Outputs

Using the pipeline above, we produce:

### a) Metrics

**i) Quantitative**
1. Total problems attempted (distinct Q's attempted)
2. Total problems solved (distinct Q's solved)
3. Total problems with errors (distinct Q's with errors)

**ii) Qualitative**
- Per Topics proficiency: List of concepts student mastered vs needs to practice

### b) Practice Problems
- 4-5 new problems for improvement based on weak topics
