import pandas as pd
from docx import Document
import re
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
import requests
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity

class SimulatedLegalSystem:
    def __init__(self):
        # Initialize simulation storage
        self.nodes = {
            'law_node': [],
            'law_explain_node': [],
            'case_node': [],
            'fact_text': [],
            'law_text': [],
            'compensation_text': [],
            'used_law_node': []
        }
        self.relationships = []
        
        # Initialize the tokenizer and model for embeddings
        self.tokenizer = AutoTokenizer.from_pretrained('TencentBAC/Conan-embedding-v1')
        self.model = AutoModel.from_pretrained('TencentBAC/Conan-embedding-v1')
        
        # Create output file
        self.output_file = f"simulation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    def log_operation(self, message: str):
        print(message)
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(message + '\n')

    def read_docx(self, filename: str) -> str:
        try:
            doc = Document(filename)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return '\n'.join(full_text)
        except Exception as e:
            print(f"Error reading DOCX file {filename}: {str(e)}")
            raise

    def create_law_nodes(self, law_text: str, law_explanation: str):
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

        # Extract and simulate creating law nodes
        laws = extract_laws(law_text)
        law_explanations = extract_laws(law_explanation)

        # Simulate creating nodes
        for law in laws:
            self.nodes['law_node'].append({
                'number': law['number'],
                'content': law['content']
            })
            self.log_operation(f"Created law_node: {law['number']}")

        for explanation in law_explanations:
            self.nodes['law_explain_node'].append({
                'number': explanation['number'],
                'explanation': explanation['content']
            })
            self.log_operation(f"Created law_explain_node: {explanation['number']}")

        # Simulate relationships
        for law in laws:
            self.relationships.append({
                'from_type': 'law_node',
                'from_number': law['number'],
                'to_type': 'law_explain_node',
                'to_number': law['number'],
                'relation': 'law_explain_relation'
            })
            self.log_operation(f"Created relationship: law_node-[law_explain_relation]->law_explain_node for number {law['number']}")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        inputs = self.tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].numpy()

    def chunk_text(self, text: str, percentage: int = 90) -> List[str]:
        # Split into sentences
        sentences = re.split(r'[，。]', text)
        sentences = [{'sentence': x.strip(), 'index': i} for i, x in enumerate(sentences) if x.strip()]
        
        # Get embeddings
        embeddings = self.embed_texts([x['sentence'] for x in sentences])
        
        # Calculate distances
        distances = []
        for i in range(len(sentences) - 1):
            similarity = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            distances.append(similarity)
            sentences[i]['distance_to_next'] = similarity

        # Calculate threshold
        sorted_distances = sorted(distances)
        cutoff_index = int(len(sorted_distances) * (100 - percentage) / 100)
        threshold = sorted_distances[cutoff_index] if distances else 0
        
        # Find breakpoints
        indices_above_thresh = [i for i, x in enumerate(distances) if x < threshold]
        
        # Create chunks
        chunks = []
        start_index = 0
        for index in indices_above_thresh:
            group = sentences[start_index:index + 1]
            combined_text = '。'.join([d['sentence'] for d in group]) + '。'
            chunks.append(combined_text)
            start_index = index + 1
            
        if start_index < len(sentences):
            combined_text = '。'.join([d['sentence'] for d in sentences[start_index:]]) + '。'
            chunks.append(combined_text)
            
        return chunks

    def classify_chunk(self, chunk: str) -> str:
        try:
            response = requests.post('http://localhost:11434/api/generate', 
                                   json={
                                       "model": "llama3.1:latest",
                                       "prompt": f"""將以下文本分類成3類中的一類: 
                                        'fact' (若文本是對案件的描述或解釋), 
                                        'law' (法條使用), 
                                        'compensation' (所有賠償及金錢相關事宜).
                                        Text: {chunk}
                                        Respond with only one word - either 'fact', 'law', or 'compensation'.
                                        Category:""",
                                       "stream": False
                                   })
            
            if response.status_code == 200:
                result = response.json()['response'].strip().lower()
                if 'fact' in result:
                    return 'fact'
                elif 'law' in result:
                    return 'law'
                elif 'compensation' in result:
                    return 'compensation'
                else:
                    return 'fact'
            else:
                return 'fact'
                
        except Exception as e:
            print(f"Exception in classify_chunk: {str(e)}")
            return 'fact'

    def process_case_data(self, case_text: str, case_id: int):
        chunks = self.chunk_text(case_text)
        
        # Simulate creating case node
        self.nodes['case_node'].append({
            'case_id': case_id,
            'case_text': case_text
        })
        self.log_operation(f"Created case_node: {case_id}")

        # Process chunks
        for chunk in chunks:
            chunk_type = self.classify_chunk(chunk)
            
            if chunk_type == 'fact':
                self.nodes['fact_text'].append({
                    'case_id': case_id,
                    'chunk': chunk
                })
                self.relationships.append({
                    'from_type': 'case_node',
                    'from_id': case_id,
                    'to_type': 'fact_text',
                    'to_chunk': chunk,
                    'relation': 'fact_text_relation'
                })
                self.log_operation(f"Created fact_text node and relationship for case {case_id}")

            elif chunk_type == 'law':
                self.nodes['law_text'].append({
                    'case_id': case_id,
                    'chunk': chunk
                })
                self.relationships.append({
                    'from_type': 'case_node',
                    'from_id': case_id,
                    'to_type': 'law_text',
                    'to_chunk': chunk,
                    'relation': 'law_text_relation'
                })
                self.log_operation(f"Created law_text node and relationship for case {case_id}")

            elif chunk_type == 'compensation':
                self.nodes['compensation_text'].append({
                    'case_id': case_id,
                    'chunk': chunk
                })
                self.relationships.append({
                    'from_type': 'case_node',
                    'from_id': case_id,
                    'to_type': 'compensation_text',
                    'to_chunk': chunk,
                    'relation': 'compensation_text_relation'
                })
                self.log_operation(f"Created compensation_text node and relationship for case {case_id}")

    def process_used_laws(self, case_id: int, used_laws: str):
        # Simulate creating used_law_node
        self.nodes['used_law_node'].append({
            'case_id': case_id,
            'used_laws': used_laws
        })
        self.relationships.append({
            'from_type': 'case_node',
            'from_id': case_id,
            'to_type': 'used_law_node',
            'to_laws': used_laws,
            'relation': 'used_law_node_relation'
        })
        self.log_operation(f"Created used_law_node and relationship for case {case_id}")

        # Simulate updating used_law property in other nodes
        for node_type in ['fact_text', 'law_text', 'compensation_text']:
            for node in self.nodes[node_type]:
                if node['case_id'] == case_id:
                    node['used_law'] = used_laws
                    self.log_operation(f"Updated used_law property for {node_type} in case {case_id}")

    def print_summary(self):
        summary = "\n=== SIMULATION SUMMARY ===\n"
        for node_type, nodes in self.nodes.items():
            summary += f"\n{node_type} nodes created: {len(nodes)}\n"
            for node in nodes[:3]:  # Show first 3 nodes of each type
                summary += f"Sample: {str(node)[:100]}...\n"
        
        summary += f"\nTotal relationships created: {len(self.relationships)}\n"
        summary += "Sample relationships:\n"
        for rel in self.relationships[:3]:  # Show first 3 relationships
            summary += f"{rel['from_type']}-[{rel['relation']}]->{rel['to_type']}\n"
            
        self.log_operation(summary)

    def main(self):
        try:
            print("Enter filename for law text (DOCX):")
            law_file = input().strip()
            law_text = self.read_docx(law_file)

            print("Enter filename for law explanations (DOCX):")
            explanation_file = input().strip()
            law_explanation = self.read_docx(explanation_file)

            self.create_law_nodes(law_text, law_explanation)

            print("Enter filename for case data (XLSX):")
            case_file = input().strip()
            xl = pd.ExcelFile(case_file)
            print("Available sheets:", xl.sheet_names)
            
            sheet_name = input("Enter sheet name: ").strip()
            df = pd.read_excel(case_file, sheet_name=sheet_name)
            print("Available columns:", df.columns.tolist())
            
            column = input("Enter column name: ").strip()
            print(f"Available rows: 0 to {len(df)-1}")
            
            start_row = int(input("Enter start row: ").strip())
            end_row = int(input("Enter end row: ").strip())

            for new_idx, (original_idx, row) in enumerate(df[column][start_row:end_row+1].items()):
                self.process_case_data(row, new_idx)

            print("Enter filename for used laws (XLSX):")
            laws_file = input().strip()
            xl = pd.ExcelFile(laws_file)
            print("Available sheets:", xl.sheet_names)
            
            sheet_name = input("Enter sheet name: ").strip()
            laws_df = pd.read_excel(laws_file, sheet_name=sheet_name)
            print("Available columns:", laws_df.columns.tolist())
            
            column = input("Enter column name: ").strip()
            print(f"Available rows: 0 to {len(laws_df)-1}")
            
            start_row = int(input("Enter start row: ").strip())
            end_row = int(input("Enter end row: ").strip())

            for new_idx, (original_idx, row) in enumerate(laws_df[column][start_row:end_row+1].items()):
                self.process_used_laws(new_idx, row)

            self.print_summary()

        except Exception as e:
            self.log_operation(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    load_dotenv()
    sim_system = SimulatedLegalSystem()
    sim_system.main()