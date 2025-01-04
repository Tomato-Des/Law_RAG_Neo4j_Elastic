# elasticsearch_utils.py
from elasticsearch import Elasticsearch
from typing import List

class ElasticsearchManager:
    def __init__(self, host: str, username: str, password: str, logger=None):
        self.es = Elasticsearch(
            host,
            http_auth=(username, password),
            verify_certs=False
        )
        self.index_name = 'text_embeddings'
        #self.logger = logger or logging.getLogger()

    def setup_indices(self, dims: int):
        """設置單一索引，包含類型標記和chunk ID"""
        mapping = {
            "mappings": {
                "properties": {
                    "case_id": {"type": "integer"},
                    "chunk_id": {"type": "keyword"},  # New field for chunk ID
                    "text": {"type": "text"},
                    "text_type": {"type": "keyword"},  # fact, law, or compensation
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

        # 如果索引存在就刪除
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
                # 檢查現有索引的維度是否匹配
                current_mapping = self.es.indices.get_mapping(index=self.index_name)
                current_dims = current_mapping[self.index_name]['mappings']['properties']['embedding']['dims']
                if current_dims != dims:
                    raise ValueError(f"現有索引的維度 ({current_dims}) 與當前模型的維度 ({dims}) 不匹配")
        else:
            print(f"創建新索引 {self.index_name}")
            self.es.indices.create(index=self.index_name, body=mapping)

    def store_embedding(self, text_type: str, case_id: int, chunk_id: str, text: str, embedding: List[float]):
        """存儲文本和 embedding，並標記類型和chunk ID"""
        doc = {
            'case_id': case_id,
            'chunk_id': chunk_id,  # Add chunk ID to document
            'text': text,
            'text_type': text_type,
            'embedding': embedding
        }
        
        result = self.es.index(index=self.index_name, body=doc)
        print(f"成功將 {text_type} embedding 存儲到 Elasticsearch，文檔 ID: {result['_id']}")
        #self.logger.info(f"成功將 {text_type} embedding 存儲到 Elasticsearch，文檔 ID: {result['_id']}")

        
    #搜尋相似文本，可以指定類型
    """def search_similar_texts(self, query_embedding: List[float], text_type: str = None, top_k: int = 5):
        query = {
            "size": top_k,
            "query": {
                "script_score": {
                    "query": {
                        "bool": {
                            "must": [{"match_all": {}}]
                        }
                    },
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": query_embedding}
                    }
                }
            }
        }

        # 如果指定了類型，添加類型過濾
        if text_type:
            query["query"]["script_score"]["query"]["bool"]["must"].append(
                {"term": {"text_type": text_type}}
            )

        response = self.es.search(index=self.index_name, body=query)
        return response['hits']['hits']"""