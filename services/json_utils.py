import json
import re

def extract_json_blocks(text: str) -> list[dict]:
    """
    Extracts JSON objects from text by matching balanced braces.
    This is much more robust than regex for nested structures.
    """
    results = []
    stack = []
    start_index = -1
    
    for i, char in enumerate(text):
        if char == '{':
            if not stack:
                start_index = i
            stack.append('{')
        elif char == '}':
            if stack:
                stack.pop()
                if not stack:
                    # Found a complete block
                    candidate = text[start_index:i+1]
                    try:
                        results.append(json.loads(candidate))
                    except json.JSONDecodeError:
                        # Try to clean it up (e.g. handle common LLM markdown junk)
                        try:
                            # Remove potential markdown code block markers
                            cleaned = re.sub(r"```json\s*|\s*```", "", candidate)
                            results.append(json.loads(cleaned))
                        except:
                            pass
    return results

# Test cases
if __name__ == "__main__":
    test_text = 'Sure! { "a": { "b": 1 } } and { "c": 2 }'
    print(extract_json_blocks(test_text))
