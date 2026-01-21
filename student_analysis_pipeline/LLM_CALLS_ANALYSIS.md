# LLM Calls Analysis - Current Pipeline

## **TOTAL LLM CALLS: 17**

---

## **Breakdown by Step:**

### **Step 1: Topic Mapping - 1 LLM Call**

**Context Sent:**
-  **ALL 15 questions** (~108 lines from hw4_question.md)
-  NO conversation history
-  NO solutions

**What LLM Does:**
- Maps each question to 1-3 calculus topics
- Returns topics for all 15 questions in one call

**Input Size:** ~108 lines
**Efficient?**  YES - Batch processing all questions at once

---

### **Step 2: Per-Question Evaluation - 15 LLM Calls**

**For EACH of the 15 questions, separately:**

**Context Sent (per call):**
-  **FULL conversation** (~991 lines, all 246 messages)
-  **ONE question text** (~5-10 lines per question)
-  **ONE solution text** (~10-30 lines per solution)

**What LLM Does:**
- Searches through ENTIRE conversation
- Finds mentions of this specific question
- Evaluates: attempted? solved? error type?

**Input Size per call:** ~1,000 lines (991 conversation + ~10-40 question/solution)
**Total for Step 2:** ~15,000 lines (1,000 lines × 15 calls)

**Efficient?**  **NO - VERY INEFFICIENT**
- Sends same 991-line conversation 15 times
- 97% of data is redundant
- But guarantees accuracy (no missed details)

---

### **Step 3: Aggregation - 0 LLM Calls**

**Pure Python logic:**
- Counts metrics
- Builds evidence
- No LLM needed 

---

### **Step 4: Practice Problem Generation - 1 LLM Call**

**Context Sent:**
-  **List of weak topics** (~5-10 lines)
-  **First 3 original questions** (sample for style, ~20-30 lines)
-  NO conversation history
-  NO solutions

**What LLM Does:**
- Generates 4-5 new practice problems
- Matches style of original questions

**Input Size:** ~30-40 lines
**Efficient?**  YES - Minimal context needed

---

## **TOTAL INPUT DATA:**

**Step 1 (Topic Mapping):**
- LLM Calls: 1
- Input per Call: ~108 lines
- Total Input: ~108 lines

**Step 2 (Per-Question Evaluation):**
- LLM Calls: 15
- Input per Call: ~1,000 lines
- Total Input: ~15,000 lines

**Step 3 (Aggregation):**
- LLM Calls: 0
- Input per Call: N/A
- Total Input: 0 lines

**Step 4 (Practice Problems):**
- LLM Calls: 1
- Input per Call: ~40 lines
- Total Input: ~40 lines

**TOTAL SUMMARY:**
- Total LLM Calls: 17
- Total Input Data: ~15,188 lines

---

## **INEFFICIENCY ANALYSIS:**

### **The Big Problem: Step 2**

**Current behavior:**
```
Call 1 (Q1): 35KB conversation + Q1 text + Q1 solution
Call 2 (Q2): 35KB conversation + Q2 text + Q2 solution  ← Same 35KB repeated!
Call 3 (Q3): 35KB conversation + Q3 text + Q3 solution  ← Same 35KB repeated!
...
Call 15 (Q15): 35KB conversation + Q15 text + Q15 solution ← Same 35KB repeated!
```

**Result:**
- Same conversation sent 15 times = 525KB
- Only unique data per call: 1KB (question + solution)
- **Redundancy: 98.7%**

---

## **WHY WE DO THIS (Your Choice):**

You prioritized **ACCURACY over EFFICIENCY**:
- "focus on accuracy, we can't miss details, even if it's full it's fine"
- LLM sees complete context every time
- No risk of missing cross-question references
- No risk of segmentation errors

**Trade-off:**
-  Slower (15 separate calls instead of 1)
-  More expensive (525KB vs ~50KB if batched)
-  More accurate (100% context guaranteed)

---

## **POTENTIAL OPTIMIZATION (If You Want Speed Later):**

### **Option 1: Batch Evaluation (1 call instead of 15)**
```
Context Sent: 35KB conversation + ALL 15 questions + ALL 15 solutions
Output: Evaluation for all 15 questions at once
```
**Pros:** 97% less data, faster
**Cons:** Single point of failure, harder to debug

### **Option 2: Smart Segmentation (5-7 calls instead of 15)**
```
Pre-process conversation to find question boundaries
Send only relevant segments per question
```
**Pros:** 80% less data, still accurate
**Cons:** Risk of missing cross-references

### **Option 3: Keep Current (17 calls)**
```
Accept inefficiency for guaranteed accuracy
```
**Pros:** Zero risk of missing data
**Cons:** Slower, more expensive

---

## **CURRENT CHOICE: Option 3** 

You chose accuracy, which is the right call for a homework analysis system where missing student work would be worse than being slow.
