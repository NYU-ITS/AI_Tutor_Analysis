# Student Analysis Pipeline - Flow Diagram

## Overview
Automated homework analysis using LLM-as-judge to evaluate student performance and generate personalized practice problems.

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           INPUT FILES                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  • hw9_question.md              (Homework questions)                    │
│  • hw9_reference_solution.md    (Correct solutions)                    │
│  • ab12167_hw9_conversation.md  (Student-AI tutor chat)                │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 1: DATA LOADING                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  data_loader.py                                                         │
│  • Parse questions → {q_num: question_text}                            │
│  • Parse solutions → {q_num: solution_text}                            │
│  • Load conversation → full_text_string                                 │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 2: TOPIC MAPPING (LLM Call #1)                  │
├─────────────────────────────────────────────────────────────────────────┤
│  pipeline.py → step1_topic_mapping()                                    │
│                                                                         │
│  Input: All questions                                                   │
│  LLM Task: Identify 1-3 calculus topics per question                    │
│  Output: {q_num: [topic1, topic2, ...]}                                 │
│                                                                         │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐     │
│  │   GPT-4o     │────────▶│  Portkey API │────────▶│  JSON Map    │     │
│  │  (via utils) │         │  (NYU)       │         │  {1: [...],  │     │
│  └──────────────┘         └──────────────┘         │   2: [...],  │     │
│                                                    │   ...}       │     │
│                                                    └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              STEP 3: PER-QUESTION EVALUATION (LLM Calls #2-N)           │
├─────────────────────────────────────────────────────────────────────────┤
│  pipeline.py → step2_evaluate_question()                                │
│                                                                          │
│  For EACH question:                                                     │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  Input:                                                       │      │
│  │  • Question text                                              │      │
│  │  • Reference solution                                         │      │
│  │  • FULL conversation (entire chat history)                   │      │
│  │                                                               │      │
│  │  LLM Task: Determine:                                        │      │
│  │  • attempted: Did student engage with this question?         │      │
│  │  • solved: Did student get correct answer?                   │      │
│  │  • error_type: Conceptual/Procedural/Computational/Incomplete│      │
│  │                                                               │      │
│  │  ┌──────────────┐         ┌──────────────┐                  │      │
│  │  │   GPT-4o     │────────▶│  Portkey API │                  │      │
│  │  │  (via utils) │         │  (NYU)       │                  │      │
│  │  └──────────────┘         └──────────────┘                  │      │
│  │                                                               │      │
│  │  Output: {attempted: bool, solved: bool, error_type: str}   │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  Note: 5-second delay between calls to avoid rate limiting              │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 4: AGGREGATION (Python Logic)                   │
├─────────────────────────────────────────────────────────────────────────┤
│  pipeline.py → step3_aggregate_metrics()                                │
│                                                                          │
│  Input:                                                                 │
│  • evaluations: {q_num: {attempted, solved, error_type}}              │
│  • topic_mapping: {q_num: [topics]}                                    │
│                                                                          │
│  Process:                                                               │
│  1. Calculate quantitative metrics:                                     │
│     • total_questions, total_attempted, total_solved, total_errors     │
│                                                                          │
│  2. Group by topic and calculate proficiency:                          │
│     • For each topic, count attempted/solved questions                  │
│     • Mastered: All questions attempted AND all solved                 │
│     • Needs Practice: Not all attempted OR not all solved              │
│                                                                          │
│  3. Build evidence for each topic:                                      │
│     • questions_tested: [q_num, ...]                                   │
│     • performance: "X/Y solved"                                        │
│     • details: ["Q1: Solved", "Q2: Attempted (Conceptual)", ...]      │
│     • reason: Explanation for mastery/practice classification           │
│                                                                          │
│  Output:                                                                │
│  {                                                                       │
│    "quantitative": {...},                                               │
│    "qualitative": {                                                     │
│      "mastered_topics": [...],                                          │
│      "needs_practice_topics": [...]                                    │
│    }                                                                    │
│  }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│          STEP 5: PRACTICE PROBLEM GENERATION (LLM Call #N+1)            │
├─────────────────────────────────────────────────────────────────────────┤
│  pipeline.py → step4_generate_practice()                                │
│                                                                          │
│  Input:                                                                 │
│  • weak_topics: List of topics needing practice                        │
│  • original_questions: Sample questions for style reference             │
│                                                                          │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐   │
│  │   GPT-4o     │────────▶│  Portkey API │────────▶│  JSON Array  │   │
│  │  (via utils) │         │  (NYU)       │         │  [{problem,  │   │
│  └──────────────┘         └──────────────┘         │   topic,     │   │
│                                                      │   hint,      │   │
│                                                      │   answer}]   │   │
│                                                      └──────────────┘   │
│                                                                          │
│  Output: 4-5 practice problems (one per weak topic)                    │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           OUTPUT FILE                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  analysis_results_hw9.json                                              │
│                                                                          │
│  {                                                                       │
│    "metrics": {                                                         │
│      "quantitative": {...},                                             │
│      "qualitative": {...}                                               │
│    },                                                                    │
│    "practice_problems": [...],                                           │
│    "details": {                                                          │
│      "topic_mapping": {...},                                             │
│      "evaluations": {...}                                               │
│    }                                                                    │
│  }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Components

### Data Flow
1. **Input Parsing** → Structured data (dicts)
2. **Topic Mapping** → Question-to-topic relationships
3. **Evaluation** → Per-question performance metrics
4. **Aggregation** → Topic-level proficiency analysis
5. **Generation** → Personalized practice problems

### LLM Integration
- **API**: Portkey Gateway (NYU)
- **Model**: GPT-4o
- **Retry Logic**: 3 attempts with exponential backoff
- **Rate Limiting**: 5-second delays between question evaluations

### Key Design Decisions
- **Full conversation context**: Each question evaluation receives the entire chat history to ensure no details are missed
- **Evidence-based metrics**: All topic classifications include detailed evidence (question numbers, performance, reasons)
- **Automatic retries**: Robust error handling for API failures

## Execution Time
- **Typical**: 30-60 seconds
- **Breakdown**:
  - Topic mapping: ~2-3 seconds
  - Per-question evaluation: ~2 seconds × N questions (with 5s delays)
  - Aggregation: <1 second (Python logic)
  - Practice generation: ~3-5 seconds

