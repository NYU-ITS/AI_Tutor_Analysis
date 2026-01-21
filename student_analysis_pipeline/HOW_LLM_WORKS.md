# How LLM Evaluation Works - Current Implementation

## Question: How does the LLM identify and evaluate each question?

---

## **CURRENT BEHAVIOR: LLM RECEIVES FULL CONVERSATION FOR EVERY QUESTION** 

### What happens when evaluating Question 8:

**Input to LLM:**
```
1. Question Text: "Use the limit definition of the derivative to find f'(x) if f(x) = x² - x"
2. Reference Solution: [Full solution for Q8]
3. Chat History: [ALL 246 messages - entire conversation from start to finish]
```

**The LLM must:**
- Read through ALL 92,000+ characters of conversation
- Search for mentions of "Question 8", "problem 8", "number 8"
- Identify student engagement with Q8
- Determine if they attempted it
- Check if their final answer matches the reference solution
- Classify error type if incorrect

---

## **Why We Send FULL Conversation:**

###  **PROS (Accuracy Guaranteed):**
1. **No missed details** - LLM sees everything student said
2. **Context preserved** - Can see if student worked on Q8 multiple times
3. **Handles edge cases** - If student says "back to problem 8" later, we catch it
4. **No assumptions** - Don't need to guess which messages are relevant

###  **CONS (Inefficiency):**
1. **Slow** - Each question evaluation requires LLM to read 92KB
2. **Expensive** - 15 questions × 92KB = ~1.4MB of input tokens
3. **Redundant** - Same text sent 15 times

---

## **Alternative Approach (If You Want Speed):**

### **Segment Conversation by Question Number**

Looking at the conversation, the AI assistant ALWAYS starts with the question:

```markdown
### Message 22 - ASSISTANT
For number 2, we need to find f'(x) if f(x) = 5x³ + 2x² - x + 4...

### Message 36 - ASSISTANT
Alright! Which problem would you like to work on next?

### Message 37 - USER
3

### Message 38 - ASSISTANT
For problem 3, we need to find f'(x)...
```

**We could:**
1. Parse conversation by question markers
2. Extract only messages related to each question
3. Send ONLY relevant segment to LLM

**Example for Q8:**
```python
# Instead of 92KB, send only ~5KB:
- Messages 89-120 (where Q8 was discussed)
```

---

## **RECOMMENDATION:**

### **Current approach is CORRECT for your use case:**

You said: **"focus on accuracy, we can't miss details so even if it's full it's fine"**

 **KEEP sending full conversation because:**
1. Student might mention Q8 multiple times across different sessions
2. Student might say "like I did in problem 8" when doing problem 10
3. Student might go back and revise earlier answers
4. **Better to be slow and accurate than fast and wrong**

---

## **Current Flow (Step 2 - Per Question Evaluation):**

```
For Q1:
  LLM receives: Q1 text + Solution 1 + FULL conversation (92KB)
  LLM outputs: {attempted: true, solved: true, error_type: null}

For Q2:
  LLM receives: Q2 text + Solution 2 + FULL conversation (92KB)
  LLM outputs: {attempted: true, solved: true, error_type: null}

... repeat for all 15 questions ...

For Q15:
  LLM receives: Q15 text + Solution 15 + FULL conversation (92KB)
  LLM outputs: {attempted: false, solved: false, error_type: null}
```

**Total LLM calls:** 15 (one per question)
**Total input data:** ~1.4MB
**Total time:** ~30-60 seconds

---

## **Key Point:**

The LLM is smart enough to:
- Scan through the full conversation
- Identify which messages discuss the specific question
- Evaluate only those relevant parts
- Ignore everything else

**This is exactly what you want for accuracy.**

---

## **If You Want Speed Optimization Later:**

I can add a pre-processing step to segment the conversation:

```python
def segment_conversation_by_question(conversation: str) -> dict:
    """
    Split conversation into segments per question.
    Returns: {1: "messages about Q1", 2: "messages about Q2", ...}
    """
    # Parse and extract relevant segments
    pass
```

But for now, **full conversation = maximum accuracy** 
