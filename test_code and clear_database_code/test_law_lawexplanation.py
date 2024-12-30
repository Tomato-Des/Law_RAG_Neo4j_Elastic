from docx import Document
import re
from typing import List, Dict

def read_docx(filename: str) -> str:
    try:
        doc = Document(filename)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        print(f"Error reading DOCX file {filename}: {str(e)}")
        raise

def extract_laws(text: str) -> List[Dict[str, str]]:
    laws = []
    pattern = r'第\s*(\d+(?:-\d+)?)\s*條[：:]\s*([^第]+)'
    matches = re.finditer(pattern, text)
    for match in matches:
        laws.append({
            'number': match.group(1),
            'content': f'第{match.group(1)}條：{match.group(2).strip()}'
        })
    return laws

def simulate_node_creation(laws: List[Dict[str, str]], explanations: List[Dict[str, str]]):
    print("\n=== Simulated Law Nodes ===")
    for law in laws:
        print(f"\nLaw Node:")
        print(f"  Number: {law['number']}")
        print(f"  Content: {law['content']}")

    print("\n=== Simulated Law Explanation Nodes ===")
    for exp in explanations:
        print(f"\nLaw Explanation Node:")
        print(f"  Number: {exp['number']}")
        print(f"  Explanation: {exp['content']}")

    print("\n=== Simulated Relationships ===")
    # Find matching laws and explanations
    for law in laws:
        for exp in explanations:
            if law['number'] == exp['number']:
                print(f"\nRelationship:")
                print(f"  Law {law['number']} -> Explanation {exp['number']}")

def main():
    try:
        # Get law text file
        print("Enter filename for law text (DOCX):")
        law_file = input().strip()
        law_text = read_docx(law_file)

        # Get law explanation file
        print("Enter filename for law explanations (DOCX):")
        explanation_file = input().strip()
        law_explanation = read_docx(explanation_file)

        # Extract laws and explanations
        laws = extract_laws(law_text)
        explanations = extract_laws(law_explanation)

        # Simulate node creation
        simulate_node_creation(laws, explanations)

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()