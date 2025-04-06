# ts_retrieval_system.py
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from typing import List, Dict, Tuple, Optional, Union
import re
import time
import os
from dotenv import load_dotenv
import requests
from models import EmbeddingModel

class RetrievalSystem:
    def __init__(self):
        """Initialize connections to Elasticsearch, Neo4j, and the embedding model"""
        load_dotenv()
        try:
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
            
            # Initialize Neo4j
            self.neo4j_driver = GraphDatabase.driver(
                os.getenv('NEO4J_URI'),
                auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
            )
            
            # Test Neo4j connection
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            
            # Initialize embedding model
            self.embedding_model = EmbeddingModel()
            
            # Initialize LLM API settings
            self.llm_url = "http://localhost:11434/api/generate"
            self.llm_model = "kenneth85/llama-3-taiwan:8b-instruct-dpo"
            
            # Test LLM connection
            response = requests.get("http://localhost:11434/api/version")
            if response.status_code != 200:
                raise ConnectionError("無法連接到 Ollama API")
            
            print("成功連接所有服務")
            
        except Exception as e:
            print(f"初始化錯誤: {str(e)}")
            raise
    
    def close(self):
        """Close connections"""
        if hasattr(self, 'neo4j_driver') and self.neo4j_driver:
            self.neo4j_driver.close()
    
    def search_elasticsearch(self, query_text: str, search_type: str, k: int) -> List[Dict]:
        """
        Search Elasticsearch for similar documents of the specified type
        
        Args:
            query_text: The text to search for
            search_type: Either "full" or "fact"
            k: Number of top results to retrieve
            
        Returns:
            List of dictionaries containing case_id, score, and text
        """
        try:
            # Create the embedding for the query
            query_embedding = self.embedding_model.embed_texts([query_text])[0]
            
            # Search in Elasticsearch
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
        
        except Exception as e:
            print(f"搜索 Elasticsearch 時發生錯誤: {str(e)}")
            raise
    
    def get_laws_from_neo4j(self, case_ids: List[int]) -> List[Dict]:
        """
        Retrieve used laws for the given case ids from Neo4j
        
        Args:
            case_ids: List of case ids
            
        Returns:
            List of dictionaries containing law information
        """
        try:
            with self.neo4j_driver.session() as session:
                # Query to get laws related to these cases
                query = """
                MATCH (c:case_node {case_id: $case_id})-[:used_law_relation]->(l:law_node)
                RETURN l.number AS law_number, l.content AS law_content
                """
                
                laws = []
                for case_id in case_ids:
                    result = session.run(query, case_id=case_id)
                    for record in result:
                        laws.append({
                            "case_id": case_id,
                            "law_number": record["law_number"],
                            "law_content": record["law_content"]
                        })
                
                return laws
        
        except Exception as e:
            print(f"從 Neo4j 獲取法條時發生錯誤: {str(e)}")
            raise
    
    def get_conclusions_from_neo4j(self, case_ids: List[int]) -> List[Dict]:
        """
        Retrieve conclusions for the given case ids from Neo4j
        
        Args:
            case_ids: List of case ids
            
        Returns:
            List of dictionaries containing conclusion information
        """
        try:
            with self.neo4j_driver.session() as session:
                # Query to get conclusions related to these cases
                query = """
                MATCH (c:case_node {case_id: $case_id})-[:conclusion_text_relation]->(conc:conclusion_text)
                RETURN conc.chunk AS conclusion_text
                """
                
                conclusions = []
                for case_id in case_ids:
                    result = session.run(query, case_id=case_id)
                    for record in result:
                        conclusions.append({
                            "case_id": case_id,
                            "conclusion_text": record["conclusion_text"]
                        })
                
                return conclusions
        
        except Exception as e:
            print(f"從 Neo4j 獲取結論時發生錯誤: {str(e)}")
            raise
    
    def count_law_occurrences(self, laws: List[Dict]) -> Dict[str, int]:
        """
        Count law occurrences and return a dictionary with counts
        
        Args:
            laws: List of law dictionaries
            
        Returns:
            Dictionary with law numbers as keys and occurrence counts as values
        """
        law_counts = {}
        for law in laws:
            law_number = law["law_number"]
            if law_number in law_counts:
                law_counts[law_number] += 1
            else:
                law_counts[law_number] = 1
        
        return law_counts
    
    def filter_laws_by_occurrence(self, law_counts: Dict[str, int], threshold: int) -> List[str]:
        """
        Filter laws by occurrence threshold
        
        Args:
            law_counts: Dictionary with law numbers as keys and occurrence counts as values
            threshold: Minimum number of occurrences required
            
        Returns:
            List of law numbers that meet the threshold
        """
        return [law for law, count in law_counts.items() if count >= threshold]
    
    def get_law_contents(self, law_numbers: List[str]) -> List[Dict]:
        """
        Retrieve law contents for the given law numbers from Neo4j
        
        Args:
            law_numbers: List of law numbers
            
        Returns:
            List of dictionaries containing law number and content
        """
        try:
            with self.neo4j_driver.session() as session:
                laws = []
                for number in law_numbers:
                    query = """
                    MATCH (l:law_node {number: $number})
                    RETURN l.number AS number, l.content AS content
                    """
                    result = session.run(query, number=number)
                    for record in result:
                        laws.append({
                            "number": record["number"],
                            "content": record["content"]
                        })
                
                return laws
        
        except Exception as e:
            print(f"從 Neo4j 獲取法條內容時發生錯誤: {str(e)}")
            raise
    
    def extract_compensation_amount(self, text: str) -> Optional[float]:
        """
        Extract compensation amount from conclusion text
        
        Args:
            text: Conclusion text
            
        Returns:
            Compensation amount as float, or None if not found
        """
        # Multiple patterns to catch different formats
        patterns = [
            r'(?:共計|總計|合計|統計)(?:新臺幣)?(?:\s)*(\d{1,3}(?:,\d{3})*|\d+)(?:\.?\d+)?(?:\s)*元',
            r'(?:賠償金額)?(?:合計|共計|總計)(?:\s)*(\d{1,3}(?:,\d{3})*|\d+)(?:\.?\d+)?(?:\s)*元',
            r'賠償(?:金額)?(?:\s)*(\d{1,3}(?:,\d{3})*|\d+)(?:\.?\d+)?(?:\s)*元',
            r'合計(?:\s)*(\d{1,3}(?:,\d{3})*|\d+)(?:\.?\d+)?(?:\s)*元'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        
        return None
    
    def calculate_average_compensation(self, conclusions: List[Dict]) -> float:
        """
        Calculate average compensation amount from conclusion texts
        
        Args:
            conclusions: List of conclusion dictionaries
            
        Returns:
            Average compensation amount
        """
        amounts = []
        for conclusion in conclusions:
            amount = self.extract_compensation_amount(conclusion["conclusion_text"])
            if amount is not None:
                amounts.append(amount)
        
        if amounts:
            return sum(amounts) / len(amounts)
        else:
            return 0.0
    
    def split_user_query(self, query_text: str) -> Dict[str, str]:
        """
        Split user query into sections based on markers with proper spacing
        
        Args:
            query_text: User query text
            
        Returns:
            Dictionary with sections
        """
        try:
            # Trim any leading/trailing whitespace
            query_text = query_text.strip()
            
            # Find positions of section markers
            pos_1 = query_text.find("一、")
            
            # For the second and third markers, we'll use regex to ensure there's whitespace before them
            matches_2 = list(re.finditer(r'(?:\s)二、', query_text))
            matches_3 = list(re.finditer(r'(?:\s)三、', query_text))
            
            # Check if all three markers exist
            if pos_1 == -1 or not matches_2 or not matches_3:
                print("警告: 無法正確識別文本標記。請確保格式為「一、」開頭，然後有「二、」和「三、」，且後兩者前面有空格或換行。")
                return {
                    "accident_facts": "",
                    "injuries": "",
                    "compensation_facts": ""
                }
            
            # Get positions (using the first match if multiple exist)
            pos_2 = matches_2[0].start() + 1  # +1 to point to the actual "二" character
            pos_3 = matches_3[0].start() + 1  # +1 to point to the actual "三" character
            
            # Check if they are in correct order
            if not (pos_1 < pos_2 < pos_3):
                print(f"警告: 標記順序錯誤：一、({pos_1}) 二、({pos_2}) 三、({pos_3})")
                return {
                    "accident_facts": "",
                    "injuries": "",
                    "compensation_facts": ""
                }
            
            # Extract the three parts
            accident_facts = query_text[pos_1:pos_2-1].strip()
            injuries = query_text[pos_2:pos_3-1].strip()
            compensation_facts = query_text[pos_3:].strip()
            
            return {
                "accident_facts": accident_facts,
                "injuries": injuries,
                "compensation_facts": compensation_facts
            }
        
        except Exception as e:
            print(f"分割查詢時發生錯誤: {str(e)}")
            raise
    
    def call_llm(self, prompt: str) -> str:
        """
        Call LLM with the given prompt
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            LLM response text
        """
        try:
            response = requests.post(
                self.llm_url,
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json()["response"].strip()
            else:
                raise Exception(f"LLM API 錯誤: {response.status_code}, {response.text}")
        
        except Exception as e:
            print(f"呼叫 LLM 時發生錯誤: {str(e)}")
            raise