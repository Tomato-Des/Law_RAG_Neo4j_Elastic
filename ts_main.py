# ts_main.py
import sys
from datetime import datetime
import os
import re
from sklearn.metrics.pairwise import cosine_similarity
from docx import Document
import pandas as pd
from dotenv import load_dotenv
from ts_models import EmbeddingModel
from ts_text_processor import TextProcessor
from ts_elasticsearch_utils import ElasticsearchManager
from ts_neo4j_manager import Neo4jManager
from ts_define_case_type import get_case_type
from typing import List, Dict
import warnings

warnings.filterwarnings("ignore")

class LegalRAGSystem:
    def __init__(self):
        load_dotenv()
        self.embedding_model = EmbeddingModel()
        self.es_manager = ElasticsearchManager(
            host="https://localhost:9200",
            username=os.getenv('ELASTIC_USER'),
            password=os.getenv('ELASTIC_PASSWORD')
        )
        self.neo4j_manager = Neo4jManager(
            uri=os.getenv('NEO4J_URI'),
            user=os.getenv('NEO4J_USER'),
            password=os.getenv('NEO4J_PASSWORD')
        )
        
        sample_embedding = self.embedding_model.embed_texts(["測試文本"])[0]
        self.es_manager.setup_indices(len(sample_embedding))

    def read_docx(self, filename: str) -> str:
        try:
            doc = Document(filename)
            return '\n'.join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"讀取 DOCX 檔案錯誤: {str(e)}")
            raise

    def process_lawyer_input(self, case_text: str, case_id: int):
        """Process lawyer_input: store full text and chunks in Elasticsearch using chunking and LLM classification"""
        try:
            # Classify the case type
            case_type = get_case_type(case_text)
            print(f"案件 {case_id} 分類為: {case_type}")
            
            # Store full text in Elasticsearch with case_type
            full_embedding = self.embedding_model.embed_texts([case_text])[0]
            full_chunk_id = f"{case_id}-full"
            self.es_manager.store_embedding(
                "full",
                case_id,
                full_chunk_id,
                case_text,
                full_embedding.tolist(),
                case_type=case_type  # Add case_type parameter
            )
            
            # Truncate the text - remove part starting with a space or newline followed by "三、"
            truncated_text = re.split(r'[\s\n]三、', case_text)[0]
    
            # Remove all spaces and newlines from the truncated text
            truncated_text = re.sub(r'\s+', '', truncated_text)
    
            # Chunk the text using semantic chunking
            chunks = self.chunk_text(truncated_text)
            for chunk in chunks:
                chunk_type = TextProcessor.classify_chunk(chunk)
                embedding = self.embedding_model.embed_texts([chunk])[0]
                chunk_id = f"{case_id}-{chunk_type}-{self._generate_chunk_sequence(case_id, chunk_type)}"
                self.es_manager.store_embedding(
                    chunk_type,
                    case_id,
                    chunk_id,
                    chunk,
                    embedding.tolist(),
                    case_type=case_type  # Add case_type parameter
                )
        except Exception as e:
            print(f"處理 lawyer_input 案件 {case_id} 時發生錯誤: {str(e)}")
            raise
        
    def _generate_chunk_sequence(self, case_id: int, chunk_type: str) -> int:
        """Generate sequence number for chunk ID in Elasticsearch"""
        count = self.es_manager.get_chunk_count(case_id, chunk_type)
        return count + 1

    def process_indictment(self, indictment_text: str, case_id: int):
        """Process indictment: store full text and split into nodes in Neo4j"""
        try:
            # Store full text in Neo4j and split into nodes
            self.neo4j_manager.create_case_node(case_id, indictment_text, "indictment")
            self.neo4j_manager.create_indictment_nodes(case_id, indictment_text)
        except Exception as e:
            print(f"處理 indictment 案件 {case_id} 時發生錯誤: {str(e)}")
            raise

    def process_used_laws(self, case_id: int, used_laws_str: str):
        """Process used laws for indictment cases in Neo4j"""
        try:
            law_numbers = TextProcessor.extract_law_numbers(used_laws_str)
            if not law_numbers:
                print(f"警告：案件 {case_id} 沒有有效的法條")
                return
            
            for law_number in law_numbers:
                self.neo4j_manager.create_law_relationships(case_id, law_number)
        except Exception as e:
            print(f"處理案件 {case_id} 的法條時發生錯誤: {str(e)}")
            raise

    def chunk_text(self, text: str, percentage: int = 70, min_chunk_chars: int = 50, max_chunk_chars: int = 230) -> List[str]:
        sentences = re.split(r'[，。]', text)
        sentences = [{'sentence': x.strip(), 'index': i} for i, x in enumerate(sentences) if x.strip()]

        embeddings = self.embedding_model.embed_texts([x['sentence'] for x in sentences])

        distances = []
        for i in range(len(sentences) - 1):
            similarity = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            distances.append(similarity)
            sentences[i]['distance_to_next'] = similarity

        sorted_distances = sorted(distances)
        cutoff_index = int(len(sorted_distances) * (100 - percentage) / 100)
        threshold = sorted_distances[cutoff_index]

        indices_above_thresh = [i for i, x in enumerate(distances) if x < threshold]

        chunks = []
        start_index = 0
        current_chars = 0

        for i in range(len(sentences)):
            current_sentence = sentences[i]['sentence']
            sentence_chars = len(current_sentence)

            # If adding this sentence would exceed max_chunk_chars, split here
            if i > start_index and current_chars + sentence_chars > max_chunk_chars:
                group = sentences[start_index:i]
                combined_text = '。'.join([d['sentence'] for d in group]) + '。'
                chunks.append(combined_text)
                start_index = i
                current_chars = sentence_chars
            else:
                current_chars += sentence_chars

            # If this is a semantic split point and we have at least min_chunk_chars
            if i < len(distances) and distances[i] < threshold and current_chars >= min_chunk_chars:
                group = sentences[start_index:i+1]
                combined_text = '。'.join([d['sentence'] for d in group]) + '。'
                chunks.append(combined_text)
                start_index = i + 1
                current_chars = 0

        # Add the last chunk if there's anything left
        if start_index < len(sentences):
            combined_text = '。'.join([d['sentence'] for d in sentences[start_index:]]) + '。'
            chunks.append(combined_text)

        return chunks

    def close(self):
        self.neo4j_manager.close()

    def main(self):
        try:
            # Let user choose what to process
            print("\n請選擇要處理的類型：")
            print("1: lawyer_input (僅存入 Elasticsearch)")
            print("2: indictment (僅存入 Neo4j)")
            choice = input("輸入 1 或 2: ").strip()

            if choice not in ['1', '2']:
                print("無效選擇，程序終止")
                return

            # Determine max_case_id based on choice
            if choice == '1':
                max_case_id = self.es_manager.get_max_case_id()
                print(f"\n從 Elasticsearch 取出最大 case_id 為 {max_case_id}")
                start_case_id = max_case_id + 1
                print(f"lawyer_input 將從 case_id {start_case_id} 開始編號")
            else:
                max_case_id = self.neo4j_manager.get_max_case_id()
                print(f"\n從 Neo4j 取出最大 case_id 為 {max_case_id}")
                start_case_id = max_case_id + 1
                print(f"indictment 將從 case_id {start_case_id} 開始編號")

            # Ask user if they want to continue
            proceed = input("是否要繼續處理？(yes/no): ").strip().lower()
            if proceed != 'yes':
                print("程序終止")
                return

            ## Process law and explanation texts (common for both)
            #print("處理法條文本...")
            #law_file = input("Enter filename for law text (DOCX): ").strip()
            #law_text = self.read_docx(law_file)
#
            #print("處理法條說明文本...")
            #explanation_file = input("Enter filename for law explanations (DOCX): ").strip()
            #law_explanation = self.read_docx(explanation_file)
#
            #self.neo4j_manager.create_law_nodes(law_text, law_explanation)

            if choice == '1':
                # Process lawyer_input
                print("處理 lawyer_input 資料...")
                lawyer_file = input("Enter filename for lawyer_input data (XLSX): ").strip()
                xl = pd.ExcelFile(lawyer_file)
                print("Available sheets:", xl.sheet_names)
                
                sheet_name = input("Enter sheet name: ").strip()
                df = pd.read_excel(lawyer_file, sheet_name=sheet_name)
                print("Available columns:", df.columns.tolist())
                
                column = input("Enter column name: ").strip()
                print(f"Available rows: 0 to {len(df)-1}")
                
                start_row = int(input("Enter start row: ").strip())
                end_row = int(input("Enter end row: ").strip())

                for i, (_, row) in enumerate(df[column][start_row:end_row+1].items()):
                    current_case_id = start_case_id + i
                    print(f"\n處理 lawyer_input 案件 {current_case_id}...")
                    self.process_lawyer_input(row, current_case_id)

            else:
                # Process indictment
                print("處理 indictment 資料...")
                indictment_file = input("Enter filename for indictment data (XLSX): ").strip()
                xl = pd.ExcelFile(indictment_file)
                print("Available sheets:", xl.sheet_names)
                
                sheet_name = input("Enter sheet name: ").strip()
                df = pd.read_excel(indictment_file, sheet_name=sheet_name)
                print("Available columns:", df.columns.tolist())
                
                column = input("Enter column name: ").strip()
                print(f"Available rows: 0 to {len(df)-1}")
                
                start_row = int(input("Enter start row: ").strip())
                end_row = int(input("Enter end row: ").strip())

                for i, (_, row) in enumerate(df[column][start_row:end_row+1].items()):
                    current_case_id = start_case_id + i
                    print(f"\n處理 indictment 案件 {current_case_id}...")
                    self.process_indictment(row, current_case_id)

                # Process used laws for indictment
                print("\n處理法條...")
                laws_file = input("Enter filename for used laws (XLSX): ").strip()
                xl = pd.ExcelFile(laws_file)
                print("Available sheets:", xl.sheet_names)
                
                sheet_name = input("Enter sheet name: ").strip()
                laws_df = pd.read_excel(laws_file, sheet_name=sheet_name)
                print("Available columns:", laws_df.columns.tolist())
                
                column = input("Enter column name: ").strip()
                print(f"Available rows: 0 to {len(laws_df)-1}")
                start_row = int(input("Enter start row: ").strip())
                end_row = int(input("Enter end row: ").strip())
                        
                for i, (_, row) in enumerate(laws_df[column][start_row:end_row+1].items()):
                    current_case_id = start_case_id + i
                    print(f"\n處理案件 {current_case_id} 的法條...")
                    self.process_used_laws(current_case_id, row)

        except Exception as e:
            print(f"執行過程中發生錯誤: {str(e)}")
        finally:
            self.close()

if __name__ == "__main__":
    import time
    start_time = time.time()
    
    rag_system = LegalRAGSystem()
    rag_system.main()
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = int(elapsed_time % 60)
    
    print(f"\nTotal execution time: {hours}h {minutes}m {seconds}s")