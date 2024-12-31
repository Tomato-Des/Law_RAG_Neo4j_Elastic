# retrieval_system.py
from typing import List, Dict, Tuple
import re
import requests
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
import numpy as np
from collections import Counter

class LegalRetrievalSystem:
    def __init__(self, elasticsearch_manager, neo4j_manager, embedding_model):
        self.es_manager = elasticsearch_manager
        self.neo4j_manager = neo4j_manager
        self.embedding_model = embedding_model
        
    def split_input(self, text: str) -> Dict[str, str]:
        """將輸入文本分割成不同部分"""
        parts = {}
        current_section = None
        current_content = []

        # 先打印每一行的起始字符，用於調試
        #print("\n=== 調試信息：每行首字符 ===")
        for i, line in enumerate(text.split('\n')):
            #print(f"行 {i + 1}:", repr(line[:10]))  # repr() 會顯示隱藏字符

            # 去除每行開頭的空白字符
            line = line.strip()

            if line.startswith('一、') or line.startswith('二、') or line.startswith('三、'):
                if current_section is not None:
                    parts[current_section] = '\n'.join(current_content).strip()

                if line.startswith('一、'):
                    current_section = 'facts'
                elif line.startswith('二、'):
                    current_section = 'injuries'
                elif line.startswith('三、'):
                    current_section = 'claims'

                current_content = [line]
            elif line and current_section is not None:  # 不為空行且已有section
                current_content.append(line)

        # 處理最後一個部分
        if current_section is not None:
            parts[current_section] = '\n'.join(current_content).strip()

        # 打印分割結果
        print("\n=== 文本分割結果 ===")
        print("\n[案件事實]")
        print(parts.get('facts', '未找到案件事實'))
        print("\n[傷害情況]")
        print(parts.get('injuries', '未找到傷害情況'))
        print("\n[請求賠償]")
        print(parts.get('claims', '未找到請求賠償'))
        print("\n=== 分割結果結束 ===\n")

        return parts
        
    def search_similar_cases(self, fact_text: str, top_k: int = 10) -> List[Dict]:
        """搜尋相似案件"""
        # 生成 embedding
        query_embedding = self.embedding_model.embed_texts([fact_text])[0]
        
        # 構建搜尋查詢
        query = {
            "size": top_k,
            "query": {
                "script_score": {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"text_type": "fact"}}
                            ]
                        }
                    },
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": query_embedding.tolist()}
                    }
                }
            }
        }
        
        # 執行搜尋
        results = self.es_manager.es.search(index=self.es_manager.index_name, body=query)
        
        # 提取結果並打印
        print("=== 相似案件搜尋結果 ===")
        found_cases = []
        for hit in results['hits']['hits']:
            case_id = hit['_source']['case_id']
            score = hit['_score']
            found_cases.append((case_id, score))
            print(f"案件ID: {case_id}, 相似度分數: {score:.4f}")
        print("=== 搜尋結果結束 ===\n")
        
        return found_cases
        
    def get_relevant_laws(self, case_ids: List[int], threshold: int = 4) -> List[str]:
        """獲取相關法條"""
        with self.neo4j_manager.driver.session() as session:
            # 獲取所有案件的法條使用情況
            result = session.run("""
                MATCH (c:case_node)-[:used_law_relation]->(l:law_node)
                WHERE c.case_id IN $case_ids
                RETURN c.case_id AS case_id, l.number AS law_number
                ORDER BY c.case_id, l.number
            """, case_ids=case_ids)
            
            # 收集每個案件使用的法條
            case_laws = {}
            law_counts = Counter()
            
            for record in result:
                case_id = record["case_id"]
                law_number = record["law_number"]
                
                if case_id not in case_laws:
                    case_laws[case_id] = set()
                case_laws[case_id].add(law_number)
                law_counts[law_number] += 1
            
            # 打印每個案件使用的法條
            print("=== 法條統計過程 ===")
            for case_id in sorted(case_laws.keys()):
                print(f"\n案件 {case_id} 使用的法條：")
                print(", ".join(sorted(case_laws[case_id])))
            
            # 打印法條使用總次數
            print("\n法條使用總次數：")
            for law_number, count in law_counts.most_common():
                print(f"第 {law_number} 條：出現 {count} 次")
            
            # 篩選出現次數超過閾值的法條
            relevant_laws = [law for law, count in law_counts.items() if count > threshold]
            
            print(f"\n出現次數超過 {threshold} 次的法條：")
            print(", ".join(sorted(relevant_laws)))
            print("=== 法條統計結束 ===\n")
            
            return sorted(relevant_laws)
            
    def get_law_content(self, law_numbers: List[str]) -> List[str]:
        """獲取法條內容"""
        with self.neo4j_manager.driver.session() as session:
            result = session.run("""
                MATCH (l:law_node)
                WHERE l.number IN $law_numbers
                RETURN l.number AS number, l.content AS content
            """, law_numbers=law_numbers)
            
            print("=== 相關法條內容 ===")
            law_contents = []
            for record in result:
                content = record["content"]
                print(f"\n第 {record['number']} 條：")
                print(content)
                law_contents.append(content)
            print("=== 法條內容結束 ===\n")
            
            return law_contents
            
    def generate_response(self, input_text: str, law_contents: List[str]) -> str:
        """生成最終回應"""
        # 準備 prompt
        prompt = f"""你是一位台灣的專業的法律助理，請根據以下案件資訊和相關法條，生成一份完整的起訴書。
        
案件資訊：
{input_text}

相關法條：
{' '.join(law_contents)}

請嚴格按照以下格式生成回應：
1. 以"一、"開頭，說明案件事實，可直接使用原始案件描述。
2. 以"二、"開頭，列舉相關法條依據，並解釋其適用性。格式為："按「法條內容」...民法第X條..."
3. 接下來使用（一）（二）等分點列出各項賠償要求，每項都需要：
   - 列出具體金額
   - 提供詳細說明
   - 確保與原始案件中的賠償項目一致
4. 最後做一個總結，包含：
   - 所有賠償項目的總和

注意事項：
1. 回應必須完全基於提供的案件資訊
2. 保持客觀、專業的語氣
3. 確保金額計算準確
4. 各分項要有明確的層級關係
5. 保持格式的一致性
6. 不要生成格式以外的任何東西
7. 不要簡化案件事實，不需要分段
8. 求償金額需和輸入吻合！案件事實也需和輸入吻合！
請生成回應："""

        print("=== 生成回應中 ===")
        
        # 使用 Ollama API 生成回應
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": "kenneth85/llama-3-taiwan:8b-instruct-dpo-q6_K",
                "prompt": prompt,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            result = response.json()['response']
            print("\n=== 生成完成 ===\n")
            return result
        else:
            raise Exception("無法生成回應")
            
    def process_case(self, input_text: str) -> str:
        """處理整個案件流程"""
        # 1. 分割輸入文本
        parts = self.split_input(input_text)
        
        # 2. 搜尋相似案件
        similar_cases = self.search_similar_cases(parts['facts'])
        case_ids = [case_id for case_id, _ in similar_cases]
        
        # 3. 獲取相關法條
        relevant_law_numbers = self.get_relevant_laws(case_ids)
        
        # 4. 獲取法條內容
        law_contents = self.get_law_content(relevant_law_numbers)
        
        # 5. 生成最終回應
        response = self.generate_response(input_text, law_contents)
        
        return response