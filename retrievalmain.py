# main_retrieval.py
import os
from dotenv import load_dotenv
from retrieval_manualadd import LegalRetrievalSystem
from elasticsearch_utils import ElasticsearchManager
from neo4j_manager import Neo4jManager
from models import EmbeddingModel

def main():
    # 載入環境變數
    load_dotenv()
    
    # 初始化各個組件
    es_manager = ElasticsearchManager(
        host="https://localhost:9200",
        username=os.getenv('ELASTIC_USER'),
        password=os.getenv('ELASTIC_PASSWORD')
    )
    
    neo4j_manager = Neo4jManager(
        uri=os.getenv('NEO4J_URI'),
        user=os.getenv('NEO4J_USER'),
        password=os.getenv('NEO4J_PASSWORD')
    )
    
    embedding_model = EmbeddingModel()
    
    # 初始化檢索系統
    retrieval_system = LegalRetrievalSystem(
        elasticsearch_manager=es_manager,
        neo4j_manager=neo4j_manager,
        embedding_model=embedding_model
    )
    
    # 讀取輸入
    print("請輸入案件內容（輸入完成後請輸入 'END' 並按 Enter）：")
    lines = []
    while True:
        line = input()
        if line.strip() == 'END':
            break
        lines.append(line)
    
    input_text = '\n'.join(lines)
    
    try:
        # 處理案件
        response = retrieval_system.process_case(input_text)
        
        print("\n系統回應：")
        print(response)
        
    except Exception as e:
        print(f"處理過程中發生錯誤：{str(e)}")
    finally:
        neo4j_manager.close()

if __name__ == "__main__":
    main()