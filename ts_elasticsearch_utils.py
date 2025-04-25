# ts_elasticsearch_utils.py
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
                    "case_type": {"type": "keyword"},  # Add case_type field
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

    # Add case_type parameter to store_embedding method
    def store_embedding(self, text_type: str, case_id: int, chunk_id: str, text: str, embedding: List[float], case_type: str = ""):
        """Store document embedding in Elasticsearch"""
        try:
            # Create document with embedding
            doc = {
                "case_id": case_id,
                "chunk_id": chunk_id,
                "text_type": text_type,
                "text": text,
                "embedding": embedding,
                "case_type": case_type  # Add case_type field
            }

            # Index the document
            self.es.index(index=self.index_name, id=chunk_id, body=doc)
            print(f"存儲文本嵌入成功：{chunk_id}")

        except Exception as e:
            print(f"存儲嵌入時發生錯誤：{str(e)}")
            raise

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
        """Get the count of chunks for a specific case_id and chunk_type
        with a forced refresh to ensure accuracy"""
        try:
            # Force a refresh to make sure all documents are searchable
            self.es.indices.refresh(index=self.index_name)
            
            # Query with both case_id and text_type filters
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"case_id": case_id}},
                            {"term": {"text_type": chunk_type}}
                        ]
                    }
                }
            }
            
            result = self.es.count(index=self.index_name, body=query)
            return result['count']
        except Exception as e:
            print(f"Error getting chunk count: {str(e)}")
            return 0  # Return 0 on error to be safe