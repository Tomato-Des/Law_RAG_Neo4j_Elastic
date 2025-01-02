# main.py
import logging
import sys
from datetime import datetime
import os
import re
from sklearn.metrics.pairwise import cosine_similarity
from docx import Document
import pandas as pd
from dotenv import load_dotenv
from models import EmbeddingModel
from text_processor import TextProcessor
from elasticsearch_utils import ElasticsearchManager
from neo4j_manager import Neo4jManager
from typing import List, Dict
import warnings

#from models_temp import EmbeddingModel
#from text_processor_temp import TextProcessor

warnings.filterwarnings("ignore")
def setup_logging(case_id_range: str = None):
    """Setup logging to both file and console"""
    # Create timestamp for log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"processing_log_{timestamp}"
    if case_id_range:
        filename += f"_cases_{case_id_range}"
    filename += ".txt"

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create file handler
    file_handler = logging.FileHandler(filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
class LegalRAGSystem:
    def __init__(self):
        load_dotenv()
        self.logger = setup_logging()
        # 初始化各個組件
        self.embedding_model = EmbeddingModel()
        self.es_manager = ElasticsearchManager(
            host="https://localhost:9200",
            username=os.getenv('ELASTIC_USER'),
            password=os.getenv('ELASTIC_PASSWORD'),
            logger=self.logger
        )
        self.neo4j_manager = Neo4jManager(
            uri=os.getenv('NEO4J_URI'),
            user=os.getenv('NEO4J_USER'),
            password=os.getenv('NEO4J_PASSWORD'),
            logger=self.logger
        )
        
        # 初始化 Elasticsearch 索引
        sample_embedding = self.embedding_model.embed_texts(["測試文本"])[0]
        self.es_manager.setup_indices(len(sample_embedding))

    def read_docx(self, filename: str) -> str:
        try:
            doc = Document(filename)
            return '\n'.join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"讀取 DOCX 檔案錯誤: {str(e)}")
            raise

    def process_case_data(self, case_text: str, case_id: int):
        try:
            # 創建案件節點
            self.neo4j_manager.create_case_node(case_id, case_text)
            
            # 分割文本並處理每個 chunk
            chunks = self.chunk_text(case_text)
            for chunk in chunks:
                chunk_type = TextProcessor.classify_chunk(chunk)
                # Generate embedding
                embedding = self.embedding_model.embed_texts([chunk])[0]              
                # 創建 Neo4j 節點並獲取 chunk ID
                chunk_id = self.neo4j_manager.create_chunk_node(case_id, chunk, chunk_type)
                self.es_manager.store_embedding(
                    chunk_type,
                    case_id,
                    chunk_id,
                    chunk,
                    embedding.tolist()
                )              
        except Exception as e:
            print(f"處理案件 {case_id} 時發生錯誤: {str(e)}")
            raise

    def process_used_laws(self, case_id: int, used_laws_str: str):
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

    def chunk_text(self, text: str, percentage: int = 80) -> List[str]:
        # Split into sentences
        sentences = re.split(r'[，。]', text)
        sentences = [{'sentence': x.strip(), 'index': i} for i, x in enumerate(sentences) if x.strip()]

        # Get embeddings
        embeddings = self.embedding_model.embed_texts([x['sentence'] for x in sentences])

        # Calculate distances
        distances = []
        for i in range(len(sentences) - 1):
            similarity = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            distances.append(similarity)
            sentences[i]['distance_to_next'] = similarity

        # Calculate threshold
        sorted_distances = sorted(distances)
        cutoff_index = int(len(sorted_distances) * (100 - percentage) / 100)
        threshold = sorted_distances[cutoff_index]

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

    def close(self):
        self.neo4j_manager.close()

    def main(self):
        try:
            max_case_id = self.neo4j_manager.get_max_case_id()
            start_case_id = max_case_id + 1
            print(f"\n當前最大 case_id 為 {max_case_id}，新資料將從 {start_case_id} 開始編號")
            self.logger.info(f"\n當前最大 case_id 為 {max_case_id}，新資料將從 {start_case_id} 開始編號")

            choice = input("是否要繼續處理新的資料？(yes/no): ").strip().lower()
            if choice != 'yes':
                print("程序終止")
                self.logger.info("程序終止")
                return
            
            ## 處理法條和說明文本
            #print("處理法條文本...")
            #law_file = input("Enter filename for law text (DOCX): ").strip()
            #law_text = self.read_docx(law_file)
#
            #print("處理法條說明文本...")
            #explanation_file = input("Enter filename for law explanations (DOCX): ").strip()
            #law_explanation = self.read_docx(explanation_file)
#
            #self.neo4j_manager.create_law_nodes(law_text, law_explanation)

            # [後續案件處理代碼...]
            print("處理案件資料...")
            case_file = input("Enter filename for case data (XLSX): ").strip()
            xl = pd.ExcelFile(case_file)
            print("Available sheets:", xl.sheet_names)
            
            sheet_name = input("Enter sheet name: ").strip()
            df = pd.read_excel(case_file, sheet_name=sheet_name)
            print("Available columns:", df.columns.tolist())
            
            column = input("Enter column name: ").strip()
            print(f"Available rows: 0 to {len(df)-1}")
            
            
            start_row = int(input("Enter start row: ").strip())
            end_row = int(input("Enter end row: ").strip())
            self.logger = setup_logging(f"{start_case_id+start_row}_to_{start_case_id+end_row}")

            # 處理案件
            for i, (_, row) in enumerate(df[column][start_row:end_row+1].items()):
                current_case_id = start_case_id + i
                print(f"\n處理案件 {current_case_id}...")
                self.logger.info(f"\n處理案件 {current_case_id}...")
                self.process_case_data(row, current_case_id)

            # 處理法條
            print("\n處理法條...")
            self.logger.info("\n處理法條...")
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
                self.logger.info(f"\n處理案件 {current_case_id} 的法條...")
                self.process_used_laws(current_case_id, row)

        except Exception as e:
            print(f"執行過程中發生錯誤: {str(e)}")
            self.logger.error(f"執行過程中發生錯誤: {str(e)}")
        finally:
            self.close()

if __name__ == "__main__":
    import time
    start_time = time.time()
    
    rag_system = LegalRAGSystem()
    rag_system.main()
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Convert to hours, minutes, seconds
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = int(elapsed_time % 60)
    
    print(f"\nTotal execution time: {hours}h {minutes}m {seconds}s")
    logger = logging.getLogger()
    logger.info(f"\nTotal execution time: {hours}h {minutes}m {seconds}s")