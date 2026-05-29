import os
import sys
import json
import requests
from typing import Dict, Any
from backend.core.config import settings

# Ensure we can import from vector_store
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vector_store.chroma_client import query_similar

# We initialize this lazily so it doesn't slow down imports if not needed
_embedder_model = None

def _get_embedder():
    global _embedder_model
    if _embedder_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading sentence-transformers model 'all-MiniLM-L6-v2'...")
            _embedder_model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            raise ImportError("sentence-transformers is not installed. Please install it.")
    return _embedder_model

OLLAMA_API_URL = settings.OLLAMA_API_URL
OLLAMA_MODEL = settings.OLLAMA_MODEL

def generate_review(code_snippet: str) -> Dict[str, Any]:
    """
    Takes a new PR code snippet, finds similar historical reviews via ChromaDB,
    and uses Ollama to generate a team-specific review comment and suggested fix.
    """
    if not code_snippet or not code_snippet.strip():
        return {
            "review_comment": "No code provided to review.",
            "suggested_fix": ""
        }

    # 1. Generate embedding for the new snippet
    model = _get_embedder()
    embedding = model.encode(code_snippet).tolist()

    # 2. Query ChromaDB for top 5 similar historical examples
    results = query_similar(embedding, n_results=5)
    
    historical_context = ""
    if results and results['metadatas'] and len(results['metadatas']) > 0:
        metadatas = results['metadatas'][0]
        
        for i, meta in enumerate(metadatas):
            score = meta.get("score")
            # Determine classification label
            if score is None:
                label = "Standard Reference Pattern (Recommended)"
            else:
                try:
                    score_val = float(score)
                    if score_val.is_integer():
                        score_str = f"{int(score_val):+d}" if score_val > 0 else f"{int(score_val):d}"
                    else:
                        score_str = f"+{score_val:.2f}" if score_val > 0 else f"{score_val:.2f}"

                    if score_val > 0:
                        label = f"Recommended Pattern (Approved: Team feedback {score_str})"
                    elif score_val < 0:
                        label = f"⚠️ Anti-Pattern to Avoid (Disapproved: Team feedback {score_str})"
                    else:
                        label = "Standard Reference Pattern"
                except (ValueError, TypeError):
                    label = "Standard Reference Pattern"

            historical_context += f"--- Example {i+1} [{label}] ---\n"
            historical_context += f"Historical Code:\n{meta.get('problematic_code', '')}\n"
            historical_context += f"Review Comment:\n{meta.get('review_comment', '')}\n"
            historical_context += f"Fix Applied by Team:\n{meta.get('fixed_code', '')}\n\n"

    if not historical_context:
        historical_context = "No relevant historical examples found."

    # 3. Construct prompt for Ollama
    system_prompt = """You are an expert AI code reviewer integrated into a development team's workflow.
Your goal is to review the provided code snippet and suggest improvements. 
Crucially, you must follow the team's historical coding patterns when making suggestions, and avoid suggestions they have rejected.

You will be provided with:
1. Historical Examples: Past code reviews. These are classified into:
   - "Recommended Pattern" or "Standard Reference Pattern": Approved review patterns you should match and mimic.
   - "⚠️ Anti-Pattern to Avoid": Review suggestions that developers previously rejected as incorrect or unhelpful. You MUST NOT repeat these rejected suggestions or suggest similar incorrect changes for matching code.
2. New Code Snippet: The code you need to review now.

Instructions:
1. Analyze the New Code Snippet.
2. If the code resembles a "Recommended Pattern" or "Standard Reference Pattern", suggest a review comment and fix that aligns with the team's historical patterns.
3. If the code resembles an "⚠️ Anti-Pattern to Avoid", pay close attention: do NOT generate the review comments or suggestions from that example. Instead, identify why it was disliked, and either skip suggesting it entirely or suggest a correct alternative if applicable.
4. If there are other bugs, security issues, or performance problems, explain them clearly.
5. Output your response as a valid JSON object with EXACTLY two keys: "review_comment" (string) and "suggested_fix" (string). If no fix is needed, leave "suggested_fix" empty. Do NOT include markdown code blocks around the JSON output, just output raw JSON."""

    user_prompt = f"""
## Historical Examples (Team Context)
{historical_context}

## New Code Snippet (To Review)
{code_snippet}
"""

    prompt = f"{system_prompt}\n\n{user_prompt}"

    # 4. Call Ollama API
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json" # Force JSON output if the model supports it
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        result_data = response.json()
        
        reply_text = result_data.get("response", "")
        
        # Parse the JSON from the LLM response
        try:
            # Clean up the response in case the model added markdown blocks
            clean_reply = reply_text.strip()
            if clean_reply.startswith("```json"):
                clean_reply = clean_reply[7:]
            if clean_reply.startswith("```"):
                clean_reply = clean_reply[3:]
            if clean_reply.endswith("```"):
                clean_reply = clean_reply[:-3]
            clean_reply = clean_reply.strip()
                
            parsed_reply = json.loads(clean_reply)
            
            return {
                "review_comment": parsed_reply.get("review_comment", "No comment provided."),
                "suggested_fix": parsed_reply.get("suggested_fix", "")
            }
            
        except json.JSONDecodeError:
            print(f"Error: Failed to parse LLM output as JSON. Raw output: {reply_text}")
            return {
                "review_comment": "The AI generated a review, but it was not in the expected format.\n\nRaw output:\n" + reply_text,
                "suggested_fix": ""
            }

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Ollama: {e}")
        return {
            "review_comment": f"Error communicating with local LLM. Please make sure Ollama is running and the model {OLLAMA_MODEL} is pulled. Error: {str(e)}",
            "suggested_fix": ""
        }

if __name__ == "__main__":
    # Test the pipeline
    test_code = '''
def calculate_total(items):
    total = 0
    for i in range(len(items)):
        total = total + items[i].price
    return total
    '''
    print(f"Testing review pipeline with code:\n{test_code}")
    print("Generating review... (this may take a moment)")
    
    result = generate_review(test_code)
    
    print("\n--- Review Results ---")
    print(f"Comment:\n{result['review_comment']}")
    print(f"\nSuggested Fix:\n{result['suggested_fix']}")
    print("----------------------")
