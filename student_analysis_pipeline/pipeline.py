from utils import ask
import json

def step1_topic_mapping(questions: dict) -> dict:
    """
    Step 1: Map each question to 1-3 calculus topics using LLM.
    Returns a dictionary {q_num: [topic1, topic2, ...]}
    """
    print("Running Step 1: Topic Mapping...")
    
    # Prepare the prompt
    questions_text = ""
    for q_num, q_text in questions.items():
        questions_text += f"Question {q_num}: {q_text}\n\n"
        
    system_prompt = """You are an expert Calculus tutor. Your task is to identify the calculus concepts each question tests.

Think step by step:
1. Read each question carefully
2. Identify the mathematical concepts being tested
3. Classify each concept by its calculus topic name
4. List 1-3 most relevant topics in order of importance

Rules:
1. For each question, list the topics tested.
2. Minimum 1 topic, Maximum 3 topics per question.
3. List topics in order of importance (primary topic first).
4. If a question text contains "[CONTEXT FOR AI... Please ignore this question...]", mark the topic as "N/A - Visual/Image-based".

Return your answer as a valid JSON object where keys are question numbers (strings) and values are lists of strings (topics).
Example:
{
  "1": ["Power Rule", "Chain Rule"],
  "2": ["N/A - Visual/Image-based"]
}
"""

    response = ask(questions_text, system=system_prompt, model="gpt-4o", response_format={"type": "json_object"})
    
    mapping = json.loads(response)
    # Ensure keys are integers
    return {int(k): v for k, v in mapping.items()}

def step2_evaluate_question(q_num: int, question: str, solution: str, chat_history: str) -> dict:
    """
    Step 2: Evaluate a single question for Attempted, Solved, and Error Type.
    Returns a dictionary {
        "attempted": bool,
        "solved": bool,
        "error_type": str or None
    }
    """
    print(f"Running Step 2: Evaluating Question {q_num}...")
    
    system_prompt = """You are an expert Calculus tutor acting as a judge. Evaluate the student's performance on a specific homework question based on their chat conversation with an AI tutor.

Think step by step:
1. First, search the chat history for any mentions of this question number
2. Determine if the student engaged with the question (attempted)
3. If attempted, check if they provided a final answer
4. Compare their final answer with the reference solution (solved)
5. If not solved, classify what type of error occurred

### Definitions

**1. Attempted**
- **Yes (True)** if:
    - Question was discussed (student asked about it OR tutor brought it up and student engaged).
    - Student engaged beyond just seeing the problem (asked follow-up, attempted solution, asked for clarification, discussed strategy).
- **No (False)** if:
    - Question never discussed.
    - Student saw problem but moved on immediately.
    - Student only said "show me problem X" and nothing else.

**2. Solved**
- **Yes (True)** if:
    - Student stated a final answer mathematically equivalent to the reference solution.
    - Equivalent forms/minor notation differences are OK.
- **No (False)** if:
    - Answer different from reference.
    - No final answer stated.
    - Student stopped mid-problem.

**3. Error Type** (Only if Attempted=True AND Solved=False)
- **Conceptual**: Wrong formula, misunderstood question, fundamental misunderstanding.
- **Procedural**: Correct formula but wrong order, skipped steps, algebraic errors.
- **Computational**: Arithmetic errors, sign errors.
- **Incomplete**: Stopped working, conversation ended mid-problem.
- **None**: If Solved=True or Attempted=False.

### Input
You will be given:
1. Question Text
2. Reference Solution
3. Chat History

### Output
Return a JSON object:
{
  "attempted": boolean,
  "solved": boolean,
  "error_type": "string" (one of: "Conceptual", "Procedural", "Computational", "Incomplete", null)
}
"""

    user_prompt = f"""
**Question {q_num}:**
{question}

**Reference Solution:**
{solution}

**Chat History:**
{chat_history}
"""

    response = ask(user_prompt, system=system_prompt, model="gpt-4o", response_format={"type": "json_object"})
    
    return json.loads(response)

def step3_aggregate_metrics(evaluations: dict, topic_mapping: dict) -> dict:
    """
    Step 3: Aggregate metrics with evidence and references.
    
    evaluations: {q_num: {"attempted": bool, "solved": bool, "error_type": str}}
    topic_mapping: {q_num: [topic1, topic2]}
    
    Returns enhanced metrics with evidence.
    """
    print("Running Step 3: Aggregating Metrics...")
    
    total_questions = 0
    total_attempted = 0
    total_solved = 0
    total_errors = 0
    
    # Topic stats: {topic: {"total": 0, "attempted": 0, "solved": 0, "questions": []}}
    topic_stats = {}
    
    for q_num, eval_result in evaluations.items():
        # Skip visual questions if marked in topic mapping
        topics = topic_mapping.get(q_num, [])
        is_visual = any("Visual/Image-based" in t for t in topics)
        
        if is_visual:
            continue
            
        total_questions += 1
        
        # Quantitative
        if eval_result["attempted"]:
            total_attempted += 1
            if eval_result["solved"]:
                total_solved += 1
            else:
                total_errors += 1
                
        # Topic Stats
        for topic in topics:
            if topic not in topic_stats:
                topic_stats[topic] = {
                    "total": 0, 
                    "attempted": 0, 
                    "solved": 0, 
                    "questions": []
                }
            
            topic_stats[topic]["total"] += 1
            topic_stats[topic]["questions"].append({
                "q_num": q_num,
                "attempted": eval_result["attempted"],
                "solved": eval_result["solved"],
                "error_type": eval_result.get("error_type")
            })
            
            if eval_result["attempted"]:
                topic_stats[topic]["attempted"] += 1
            if eval_result["solved"]:
                topic_stats[topic]["solved"] += 1
                
    # Build enhanced topic proficiency with evidence
    mastered = []
    needs_practice = []
    
    for topic, stats in topic_stats.items():
        evidence = {
            "questions_tested": [q["q_num"] for q in stats["questions"]],
            "performance": f"{stats['solved']}/{stats['total']} solved",
            "details": []
        }
        
        # Add details for each question
        for q in stats["questions"]:
            status = "Solved" if q["solved"] else ("Attempted" if q["attempted"] else "Not Attempted")
            if q["error_type"]:
                status += f" ({q['error_type']})"
            evidence["details"].append(f"Q{q['q_num']}: {status}")
        
        # Determine mastery with reason
        if stats["attempted"] == stats["total"] and stats["solved"] == stats["total"]:
            evidence["reason"] = "All questions attempted and solved correctly"
            mastered.append({"topic": topic, "evidence": evidence})
        else:
            # Explain why needs practice
            reasons = []
            if stats["attempted"] < stats["total"]:
                not_attempted = stats["total"] - stats["attempted"]
                reasons.append(f"{not_attempted} question(s) not attempted")
            if stats["solved"] < stats["attempted"]:
                failed = stats["attempted"] - stats["solved"]
                reasons.append(f"{failed} question(s) attempted but not solved")
            
            evidence["reason"] = "; ".join(reasons)
            needs_practice.append({"topic": topic, "evidence": evidence})
            
    return {
        "quantitative": {
            "total_questions": total_questions,
            "total_attempted": total_attempted,
            "total_solved": total_solved,
            "total_errors": total_errors
        },
        "qualitative": {
            "mastered_topics": sorted(mastered, key=lambda x: x["topic"]),
            "needs_practice_topics": sorted(needs_practice, key=lambda x: x["topic"])
        },
        "methodology": {
            "description": "Analysis based on hw4/metrics_definitions.md",
            "mastered_criteria": "All questions for this topic were attempted AND all were solved correctly",
            "needs_practice_criteria": "Not all questions attempted OR not all solved correctly",
            "visual_questions_excluded": "Questions 12 and 13 (visual/image-based) were excluded from analysis"
        }
    }

def step4_generate_practice(weak_topics: list, original_questions: dict) -> list:
    """
    Step 4: Generate 4-5 practice problems for weak topics.
    Returns a list of problem dictionaries.
    """
    print("Running Step 4: Generating Practice Problems...")
    
    if not weak_topics:
        return []
        
    # Prepare context
    questions_sample = ""
    # Include a few original questions for style reference (first 3)
    for q_num in sorted(original_questions.keys())[:3]:
        questions_sample += f"Q{q_num}: {original_questions[q_num]}\n"
        
    system_prompt = """You are an expert Calculus tutor. Generate practice problems for a student based on their weak topics.

Think step by step:
1. Review the weak topics the student needs to practice
2. Look at the style and difficulty of the original homework questions
3. For each weak topic, design a similar but different problem
4. Ensure problems are clear, solvable, and appropriately challenging
5. Provide helpful hints and correct answers

Rules:
1. Generate exactly 4-5 problems total.
2. Distribute problems across the provided "Weak Topics".
3. Problems must be text-based (no images/graphs required).
4. Match the difficulty and style of the "Original Homework Questions".
5. Use LaTeX for math notation (e.g., $f'(x)$).

Return a JSON object with a key "problems" containing a list of objects.
Each object must have:
- "problem_number": integer (1 to 5)
- "topic": string (the weak topic it targets)
- "question": string (the problem statement)
- "hint": string (one sentence hint)
- "answer": string (the final answer)
"""

    user_prompt = f"""
**Weak Topics:**
{", ".join(weak_topics)}

**Original Homework Questions (Style Reference):**
{questions_sample}

Generate 4-5 practice problems now.
"""

    response = ask(user_prompt, system=system_prompt, model="gpt-4o", response_format={"type": "json_object"})
    
    data = json.loads(response)
    return data.get("problems", [])
