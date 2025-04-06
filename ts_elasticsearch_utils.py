# elasticsearch_utils.py
from elasticsearch import Elasticsearch
from typing import List

class ElasticsearchManager:
    def __init__(self, host: str, username: str, password: str):
        self.es = Elasticsearch(
            host,
            http_auth=(username, password),
            verify_certs=False
        )
        self.index_name = 'ts_text_embeddings'

    def setup_indices(self, dims: int):
        """Set up a single index with type tagging and chunk ID"""
        mapping = {
            "mappings": {
                "properties": {
                    "case_id": {"type": "integer"},
                    "chunk_id": {"type": "keyword"},
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
                current_mapping = self.es.indices.get_mapping(index=self.index_name)
                current_dims = current_mapping[self.index_name]['mappings']['properties']['embedding']['dims']
                if current_dims != dims:
                    raise ValueError(f"現有索引的維度 ({current_dims}) 與當前模型的維度 ({dims}) 不匹配")
        else:
            print(f"創建新索引 {self.index_name}")
            self.es.indices.create(index=self.index_name, body=mapping)

    def store_embedding(self, text_type: str, case_id: int, chunk_id: str, text: str, embedding: List[float]):
        """Store text and embedding with type and chunk ID"""
        doc = {
            'case_id': case_id,
            'chunk_id': chunk_id,
            'text': text,
            'text_type': text_type,
            'embedding': embedding
        }
        
        result = self.es.index(index=self.index_name, body=doc)
        print(f"成功將 {text_type} embedding 存儲到 Elasticsearch，文檔 ID: {result['_id']}")

    def get_max_case_id(self) -> int:
        """Retrieve the maximum case_id from Elasticsearch"""
        try:
            response = self.es.search(
                index=self.index_name,
                body={
                    "query": {"match_all": {}},
                    "aggs": {
                        "max_case_id": {
                            "max": {
                                "field": "case_id"
                            }
                        }
                    },
                    "size": 0
                }
            )
            max_id = response['aggregations']['max_case_id']['value']
            return int(max_id) if max_id is not None else -1
        except Exception as e:
            print(f"Error retrieving max case_id from Elasticsearch: {str(e)}")
            return -1

    def get_chunk_count(self, case_id: int, chunk_type: str) -> int:
        """Count chunks of a specific type for a case_id to generate sequence"""
        try:
            response = self.es.count(
                index=self.index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"case_id": case_id}},
                                {"prefix": {"chunk_id": f"{case_id}-{chunk_type}"}},
                            ]
                        }
                    }
                }
            )
            return response['count']
        except Exception as e:
            print(f"Error counting chunks in Elasticsearch: {str(e)}")
            return 0