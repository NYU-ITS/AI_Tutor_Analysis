# Student Analysis Pipeline

Automated homework analysis using LLM-as-judge to evaluate student performance and generate personalized practice problems.

## Overview

This pipeline analyzes student homework conversations and produces:
- **Quantitative metrics**: Total attempted, solved, and errors
- **Qualitative metrics**: Topic proficiency (Mastered vs Needs Practice)
- **Practice problems**: 4-5 new problems for weak topics

## Requirements

- Python 3.7+
- `requests` library (for Portkey API calls)

## File Structure

```
student_analysis_pipeline/
├── main.py              # Pipeline orchestrator (run this)
├── pipeline.py          # Core pipeline logic (Steps 1-4)
├── data_loader.py       # Input file parsers
├── utils.py             # Portkey API client with retry logic
└── analysis_results.json # Output file (generated)
```

## How to Run

### Basic Usage

```bash
cd /Users/prashant/Desktop/development/Data_pipeline/student_analysis_pipeline
python3 main.py
```

### What Happens

1. **Loads data** from:
   - `hw4/hw4_question.md`
   - `hw4/hw4_reference_solution.md`
   - `hw4/student_conversations/ab12167_hw4_chats.json`

2. **Runs 4-step pipeline**:
   - Step 1: Topic Mapping (LLM)
   - Step 2: Per-Question Evaluation (LLM)
   - Step 3: Aggregation (Python)
   - Step 4: Practice Problem Generation (LLM)

3. **Outputs results** to: `analysis_results.json`

### Expected Runtime

- **~30-60 seconds** (depends on API response time)
- 15 questions × ~2 seconds each for evaluation
- Plus topic mapping and practice generation

## Output Format

```json
{
  "metrics": {
    "quantitative": {
      "total_questions": 13,
      "total_attempted": 12,
      "total_solved": 11,
      "total_errors": 1
    },
    "qualitative": {
      "mastered_topics": [
        {
          "topic": "Power Rule",
          "evidence": {
            "questions_tested": [2, 3, 5],
            "performance": "3/3 solved",
            "details": ["Q2: Solved", "Q3: Solved", "Q5: Solved"],
            "reason": "All questions attempted and solved correctly"
          }
        }
      ],
      "needs_practice_topics": [...]
    }
  },
  "practice_problems": [...],
  "details": {...}
}
```

## Error Handling

- **Automatic retries**: 3 attempts per LLM call with exponential backoff
- **Failure mode**: Pipeline crashes with exception if API fails after retries
- **No silent failures**: All errors are raised explicitly

## Configuration

To analyze a different student or homework:

Edit paths in `main.py`:
```python
QUESTIONS_PATH = "hw4/hw4_question.md"
SOLUTIONS_PATH = "hw4/hw4_reference_solution.md"  
CHAT_PATH = "hw4/student_conversations/ab12167_hw4_chats.json"
```

## API Configuration

The pipeline uses NYU's Portkey gateway:
- Base URL: `https://ai-gateway.apps.cloud.rt.nyu.edu/v1`
- Model: GPT-4o (`@gpt-4o/gpt-4o`)
- Credentials are in `utils.py`

---

## Adapting for Different Subjects

**IMPORTANT:** This pipeline is currently configured for **Calculus I** assignments.

To use it for other subjects (Algebra, Statistics, Physics, etc.), you MUST update the following in `pipeline.py`:

### Changes Required:

**1. Step 1: Topic Mapping (Line 16)**
```python
# Current (Calculus-specific):
system_prompt = """You are an expert Calculus tutor. Your task is to identify the calculus concepts each question tests."""

# Change to (Generic):
system_prompt = """You are an expert [SUBJECT] tutor. Your task is to identify the [SUBJECT] concepts each question tests."""

# Examples:
# - "You are an expert Algebra tutor. Your task is to identify the algebra concepts..."
# - "You are an expert Statistics tutor. Your task is to identify the statistics concepts..."
# - "You are an expert Physics tutor. Your task is to identify the physics concepts..."
```

**2. Step 2: Per-Question Evaluation (Line 49)**
```python
# Current (Calculus-specific):
system_prompt = """You are an expert Calculus tutor acting as a judge."""

# Change to (Generic):
system_prompt = """You are an expert [SUBJECT] tutor acting as a judge."""
```

**3. Step 4: Practice Problem Generation (Line 238)**
```python
# Current (Calculus-specific):
system_prompt = """You are an expert Calculus tutor. Generate practice problems..."""

# Change to (Generic):
system_prompt = """You are an expert [SUBJECT] tutor. Generate practice problems..."""
```

### Examples for Different Subjects:

**For Algebra:**
- Replace "Calculus tutor" with "Algebra tutor"
- Replace "calculus concepts" with "algebra concepts"

**For Statistics:**
- Replace "Calculus tutor" with "Statistics tutor"
- Replace "calculus concepts" with "statistics concepts"

**For Physics:**
- Replace "Calculus tutor" with "Physics tutor"
- Replace "calculus concepts" with "physics concepts"

**For Chemistry:**
- Replace "Calculus tutor" with "Chemistry tutor"
- Replace "calculus concepts" with "chemistry concepts"

**Note:** The rest of the pipeline (evaluation criteria, metrics, error types) remains the same across subjects.

---

## Documentation Files

This project includes several documentation files to help you understand and use the pipeline:

**Core Documentation:**
- `README.md` (this file) - Main documentation and usage guide
- `metrics_definitions.md` - Detailed definitions of all metrics and evaluation criteria

**Technical Documentation:**
- `HOW_LLM_WORKS.md` - Explanation of how LLM evaluation works and why we send full conversation
- `LLM_CALLS_ANALYSIS.md` - Breakdown of all 17 LLM calls, input data, and efficiency analysis

**Input Files:**
- `hw4_question.md` - Homework questions
- `hw4_reference_solution.md` - Reference solutions
- `ab12167_hw4_conversation.md` - Student conversation with AI tutor

**Code Files:**
- `main.py` - Pipeline orchestrator (run this)
- `pipeline.py` - Core pipeline logic (Steps 1-4)
- `data_loader.py` - Input file parsers
- `utils.py` - Portkey API client with retry logic
- `export_conversation.py` - Script to convert JSON chats to markdown

**Output:**
- `analysis_results.json` - Generated analysis report

**Start by reading `metrics_definitions.md` to understand what the pipeline measures, then read `HOW_LLM_WORKS.md` to understand the implementation.**

