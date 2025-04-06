#Only retrieve elastic search part
# ts_retrieval_system.py
from elasticsearch import Elasticsearch
from typing import List, Dict, Tuple, Optional, Union
import re
import time
import os
from dotenv import load_dotenv
import requests
from Law_RAG_Neo4j_Elastic.ts_models import EmbeddingModel

class RetrievalSystem:
    def __init__(self):
        """Initialize connections to Elasticsearch and the embedding model"""
        load_dotenv()
        
        # Initialize Elasticsearch
        self.es = Elasticsearch(
            "https://localhost:9200",
            http_auth=(os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASSWORD')),
            verify_certs=False
        )
        self.es_index = 'ts_text_embeddings'
        
        # Test Elasticsearch connection
        if not self.es.ping():
            raise ConnectionError("無法連接到 Elasticsearch")
        
        # Initialize embedding model
        self.embedding_model = EmbeddingModel()
        
        print("成功連接 Elasticsearch 和初始化 Embedding 模型")
    
    def close(self):
        """Close connections - no connections to close in this simplified version"""
        pass
    
    def search_elasticsearch(self, query_text: str, search_type: str, k: int) -> List[Dict]:
        """
        Search Elasticsearch for similar documents of the specified type
        
        Args:
            query_text: The text to search for
            search_type: Either "full", "fact", or "fact+injuries"
            k: Number of top results to retrieve
            
        Returns:
            List of dictionaries containing case_id, score, and text
        """
        # Create the embedding for the query
        query_embedding = self.embedding_model.embed_texts([query_text])[0]
        
        # Build the Elasticsearch query based on search_type
        if search_type == "fact+injuries":
            # For "fact+injuries", search for either "fact" or "injuries" text_type
            script_query = {
                "script_score": {
                    "query": {
                        "bool": {
                            "should": [
                                {"term": {"text_type": "fact"}},
                                {"term": {"text_type": "injuries"}}
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": query_embedding.tolist()}
                    }
                }
            }
        else:
            # For "full" or "fact", search for exact text_type match
            script_query = {
                "script_score": {
                    "query": {"term": {"text_type": search_type}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": query_embedding.tolist()}
                    }
                }
            }
        
        response = self.es.search(
            index=self.es_index,
            body={
                "size": k,
                "query": script_query,
                "_source": ["case_id", "text", "chunk_id", "text_type"]
            }
        )
        
        # Process results
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "case_id": hit["_source"]["case_id"],
                "score": hit["_score"],
                "text": hit["_source"]["text"],
                "chunk_id": hit["_source"]["chunk_id"],
                "text_type": hit["_source"]["text_type"]
            })
        
        return results
            
    def get_full_case_text(self, case_id: str) -> str:
        """
        Retrieve the full case text (lawyer_input) for a given case_id
        
        Args:
            case_id: The case ID to retrieve
            
        Returns:
            Full case text or error message if not found
        """
        # Make sure case_id is a string for the term query
        case_id = str(case_id)
        
        # Search for the full text document with the given case_id
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"case_id": case_id}},
                        {"term": {"text_type": "full"}}
                    ]
                }
            },
            "_source": ["text"]
        }
        
        try:
            response = self.es.search(
                index=self.es_index,
                body=query
            )
            
            # Check if we found a result
            if response["hits"]["total"]["value"] > 0:
                return response["hits"]["hits"][0]["_source"]["text"]
            else:
                return f"無法找到案件 {case_id} 的全文"
        except Exception as e:
            return f"獲取案件 {case_id} 全文時發生錯誤: {str(e)}"