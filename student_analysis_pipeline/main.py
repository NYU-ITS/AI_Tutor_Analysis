from data_loader import load_questions, load_solutions
from pipeline import step1_topic_mapping, step2_evaluate_question, step3_aggregate_metrics, step4_generate_practice
import os
import json
import time

# All files are now in the same directory as this script
QUESTIONS_PATH = "hw9_question.md"
SOLUTIONS_PATH = "hw9_reference_solution.md"
CONVERSATION_PATH = "ab12167_hw9_conversation.md"
OUTPUT_FILE = "analysis_results_hw9.json"

def load_conversation(file_path: str) -> str:
    """Load the conversation markdown file as a single string."""
    with open(file_path, 'r') as f:
        return f.read()

def main():
    print("Starting Student Analysis Pipeline...")
    start_time = time.time()
    
    # 1. Load Data
    print("\n[1/5] Loading Data...")
    questions = load_questions(QUESTIONS_PATH)
    solutions = load_solutions(SOLUTIONS_PATH)
    conversation = load_conversation(CONVERSATION_PATH)
    print(f"Loaded {len(questions)} questions, {len(solutions)} solutions.")
    print(f"Conversation length: {len(conversation)} characters")
    
    # 2. Step 1: Topic Mapping
    print("\n[2/5] Step 1: Topic Mapping...")
    topic_mapping = step1_topic_mapping(questions)
    print(f"Mapped topics for {len(topic_mapping)} questions.")
    
    # 3. Step 2: Per-Question Evaluation
    print("\n[3/5] Step 2: Per-Question Evaluation...")
    print("NOTE: LLM receives FULL conversation for each question evaluation")
    print("This ensures no details are missed, but may be slower\n")
    
    evaluations = {}
    for q_num in sorted(questions.keys()):
        if q_num not in solutions:
            print(f"Skipping Q{q_num} (No solution found)")
            continue
            
        result = step2_evaluate_question(q_num, questions[q_num], solutions[q_num], conversation)
        evaluations[q_num] = result
        print(f"Q{q_num}: Attempted={result['attempted']}, Solved={result['solved']}")
        
        # Add delay to avoid rate limiting (except after last question)
        if q_num != sorted(questions.keys())[-1]:
            time.sleep(5)  # 5 second delay to avoid rate limiting
        
    # 4. Step 3: Aggregation
    print("\n[4/5] Step 3: Aggregation...")
    metrics = step3_aggregate_metrics(evaluations, topic_mapping)
    print("Quantitative Metrics:", json.dumps(metrics["quantitative"], indent=2))
    print("Weak Topics:", metrics["qualitative"]["needs_practice_topics"])
    
    # 5. Step 4: Practice Problems
    print("\n[5/5] Step 4: Practice Problem Generation...")
    weak_topics_data = metrics["qualitative"]["needs_practice_topics"]
    # Extract just the topic names from the enhanced format
    weak_topics = [item["topic"] for item in weak_topics_data]
    practice_problems = []
    if weak_topics:
        practice_problems = step4_generate_practice(weak_topics, questions)
        print(f"Generated {len(practice_problems)} practice problems.")
    else:
        print("No weak topics identified. Skipping practice generation.")
        
    # Final Output
    final_output = {
        "metrics": metrics,
        "practice_problems": practice_problems,
        "details": {
            "topic_mapping": topic_mapping,
            "evaluations": evaluations
        }
    }
    
    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(final_output, f, indent=2)
        
    print(f"\nAnalysis Complete! Results saved to {OUTPUT_FILE}")
    print(f"Total Time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
