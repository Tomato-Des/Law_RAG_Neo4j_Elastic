import os
from neo4j import GraphDatabase
from elasticsearch import Elasticsearch
import requests
from dotenv import load_dotenv
import numpy as np
from typing import List, Dict, Any
import json
import warnings
import urllib3
urllib3.disable_warnings()
warnings.filterwarnings("ignore")

class EmbeddingMigration:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Neo4j setup
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        
        # Elasticsearch setup
        self.es_host = "https://localhost:9200"
        self.es_user = os.getenv('ELASTIC_USER')
        self.es_password = os.getenv('ELASTIC_PASSWORD')
        
        self.index_name = 'text_embeddings'
        
        # Initialize connections
        self.neo4j_driver = None
        self.es = None
        
    def connect_databases(self):
        """Connect to both Neo4j and Elasticsearch"""
        try:
            # Connect to Neo4j
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            print("Successfully connected to Neo4j")
            
            # Connect to Elasticsearch
            self.es = Elasticsearch(
                self.es_host,
                basic_auth=(self.es_user, self.es_password),
                verify_certs=False
            )
            print("Successfully connected to Elasticsearch")
            
        except Exception as e:
            print(f"Error connecting to databases: {str(e)}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding from Ollama API"""
        try:
            response = requests.post(
                'http://localhost:11434/api/embeddings',
                json={
                    "model": "kenneth85/llama-3-taiwan:8b-instruct-dpo-q6_K",
                    "prompt": text
                }
            )
            
            if response.status_code == 200:
                return response.json()['embedding']
            else:
                raise Exception(f"Error from Ollama API: {response.status_code}")
                
        except Exception as e:
            print(f"Error getting embedding: {str(e)}")
            raise

    def setup_elasticsearch_index(self, dims: int):
        """Setup Elasticsearch index with given dimensions"""
        mapping = {
            "mappings": {
                "properties": {
                    "case_id": {"type": "integer"},
                    "text": {"type": "text"},
                    "text_type": {"type": "keyword"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": dims
                    }
                }
            },
            "settings": {
                "refresh_interval": "1s"
            }
        }

        # Check if index exists
        if self.es.indices.exists(index=self.index_name):
            print(f"\n發現現有索引 {self.index_name}")
            choice = input("是否要刪除現有索引？(yes/no): ").strip().lower()
            
            if choice == 'yes':
                print(f"刪除現有索引 {self.index_name}")
                self.es.indices.delete(index=self.index_name)
                print(f"創建新索引 {self.index_name}")
                self.es.indices.create(index=self.index_name, body=mapping)
            else:
                print("保留現有索引")
                # Check dimension match
                current_mapping = self.es.indices.get_mapping(index=self.index_name)
                current_dims = current_mapping[self.index_name]['mappings']['properties']['embedding']['dims']
                if current_dims != dims:
                    raise ValueError(f"現有索引的維度 ({current_dims}) 與當前模型的維度 ({dims}) 不匹配")
        else:
            print(f"創建新索引 {self.index_name}")
            self.es.indices.create(index=self.index_name, body=mapping)

    def get_chunks_from_neo4j(self):
        """Get all chunks from Neo4j"""
        with self.neo4j_driver.session() as session:
            # Query for fact_text nodes
            fact_chunks = session.run("""
                MATCH (n:fact_text)
                RETURN n.case_id as case_id, n.chunk as chunk, 'fact' as type
            """)
            
            # Query for law_text nodes
            law_chunks = session.run("""
                MATCH (n:law_text)
                RETURN n.case_id as case_id, n.chunk as chunk, 'law' as type
            """)
            
            # Query for compensation_text nodes
            comp_chunks = session.run("""
                MATCH (n:compensation_text)
                RETURN n.case_id as case_id, n.chunk as chunk, 'compensation' as type
            """)
            
            # Combine all results
            chunks = []
            for record in fact_chunks:
                chunks.append(dict(record))
            for record in law_chunks:
                chunks.append(dict(record))
            for record in comp_chunks:
                chunks.append(dict(record))
                
            return chunks

    def store_embedding(self, case_id: int, text: str, text_type: str, embedding: List[float]):
        """Store embedding in Elasticsearch"""
        doc = {
            'case_id': case_id,
            'text': text,
            'text_type': text_type,
            'embedding': embedding
        }
        
        result = self.es.index(index=self.index_name, body=doc)
        print(f"成功將 case_id: {case_id} 的 {text_type} embedding 存儲到 Elasticsearch，文檔 ID: {result['_id']}")

    def process_all_chunks(self):
        """Main process to handle all chunks"""
        try:
            # Connect to databases
            self.connect_databases()
            
            # Get a sample chunk and its embedding to determine dimensions
            chunks = self.get_chunks_from_neo4j()
            if not chunks:
                print("No chunks found in Neo4j")
                return
                
            print(f"Found {len(chunks)} chunks in Neo4j")
            
            # Get sample embedding to determine dimensions
            sample_embedding = self.get_embedding(chunks[0]['chunk'])
            dims = len(sample_embedding)
            print(f"Embedding dimension: {dims}")
            
            # Setup Elasticsearch index
            self.setup_elasticsearch_index(dims)
            
            # Process all chunks
            for chunk in chunks:
                try:
                    print(f"\nProcessing chunk for case_id {chunk['case_id']}, type: {chunk['type']}")
                    embedding = self.get_embedding(chunk['chunk'])
                    self.store_embedding(
                        chunk['case_id'],
                        chunk['chunk'],
                        chunk['type'],
                        embedding
                    )
                except Exception as e:
                    print(f"Error processing chunk for case_id {chunk['case_id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error in main process: {str(e)}")
        finally:
            if self.neo4j_driver:
                self.neo4j_driver.close()

if __name__ == "__main__":
    import time
    start_time = time.time()
    
    migration = EmbeddingMigration()
    migration.process_all_chunks()
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Convert to hours, minutes, and seconds
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = int(elapsed_time % 60)
    
    print(f"\n總共耗時: {hours}小時 {minutes}分鐘 {seconds}秒")