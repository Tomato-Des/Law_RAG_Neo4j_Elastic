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
            text = hit['_source']['text']   #這裏是top k fact text的打印的部分
            found_cases.append((case_id, score))
            print(f"案件ID: {case_id}, 相似度分數: {score:.4f}")
            print(f"案件内容：{text}\n")
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
            
    def generate_first_part(self, facts: str, law_contents: List[str], injuries: str) -> str:
        """生成第一部分回應（案件事實和法律依據）"""
        print("\n=== 生成第一部分回應 ===")
        print("提供以下資訊:")
        print("\n[案件事實]")
        print(facts)
        print("\n[法條資訊]")
        print(' '.join(law_contents))
        print("=== 第一部分輸入結束 ===\n")

        # Extract law content and numbers
        law_info = []
        for content in law_contents:
            match = re.match(r'第(\d+(?:-\d+)?)\s*條[：:]\s*(.+)', content)
            if match:
                number = match.group(1)
                content = match.group(2).strip()
                law_info.append({
                    'number': number,
                    'content': content
                })

        # Format law citations
        law_citations = []
        law_numbers = []
        for law in law_info:
            number = law['number']
            content = law['content']
            
            # Format the law number reference
            if '-' in number:
                base, sub = number.split('-')
                number_ref = f"第{base}條之{sub}"
            else:
                number_ref = f"第{number}條"
            
            # Build the citations
            law_citations.append(f'「{content}」')
            if number in ['184', '191-2', '193', '195']:  # Cases that need "前段"
                law_numbers.append(f'民法{number_ref}前段')
            else:
                law_numbers.append(f'民法{number_ref}')

        prompt = f"""你是一個台灣原告律師，你現在要幫忙完成車禍起訴狀裏的案件事實陳述的部分，你只需要根據下列格式進行輸出，並確保每個段落內容完整,禁止輸出格式以外的任何東西：
一、事實概述：完整描述事故經過，案件過程盡量越詳細越好，要使用"緣被告"做開頭，並且在這段中都要以"原告""被告"作人物代稱，如果我給你的案件事實中沒有出現原告或被告的姓名，則請直接使用"原告""被告"作為代稱，請絕對不要自己憑空杜撰被告的姓名
備註:請記得在"事實概述"前面加上"一、", 禁止捏造故事 。禁止輸出格式以外的任何東西
  

案件事實： 
{facts}

"""
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": "deepseek-r1:32b",  #"kenneth85/llama-3-taiwan:8b-instruct-dpo",
                "prompt": prompt,
                "stream": False
            }
        )
        
        if response.status_code != 200:
            raise Exception("無法生成案件事實描述")
            
        fact_description = response.json()['response']
        #print(f'Fact Description Result: {fact_description}\n')

        # Combine fact description with manually formatted legal section
        legal_section = f"二、按{', '.join(law_citations)};{', '.join(law_numbers)}分別定有明文。查被告因上開侵權行為，致原告受有下列損害，依前揭規定，被告應負損害賠償責任："
        
        final_text = f"{fact_description}\n\n{legal_section}"
        
        return final_text

    def generate_second_part(self, injuries: str, claims: str) -> str:
        print("\n=== 生成第二部分回應 ===")
        print("提供以下資訊:")
        print("\n[受傷情形]")
        print(injuries)
        print("\n[賠償請求]")
        print(claims)
        print("=== 第二部分輸入結束 ===\n")

        prompt = f"""你是一個台灣原告律師，請根據下列資訊整理賠償資訊。請依據受傷情形和賠償請求，詳細列出各項損害項目、相應的金額、以及損害原因：
    請嚴格按照以下格式輸出，禁止輸出MarnDown格式：
    三、損害項目：依次列出：[賠償項目的類型]:[金額]元(金額需準確，不可模糊，可參考輸入)，若無明確金額請再檢查輸入從中查找相關金額、隨後輸出換行符號"\n"然後輸出此賠償請求的原因；若涉及多名原告或多名被告（例如「數名原告」、「數名被告」、「原被告皆數名」或「單純原被告各一」），請分別列出各自的賠償項目及原因。
    四、總賠償金額：以"綜上所陳"開頭，仔細計算總賠償金額，若有不同人則分開計算。
    備註:總賠償金額要做二次檢查，不要輸出任何格式以外的東西，禁止輸出MarnDown格式或以下任何字符[*/()##@$%]

    受傷情形：
    {injuries}

    賠償請求：
    {claims}"""

        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": "deepseek-r1:32b",
                "prompt": prompt,
                "stream": False
            }
        )

        if response.status_code == 200:
            print(f'Second Result: {response.json()["response"]}\n')
            return response.json()['response']
        else:
            raise Exception("無法生成第二部分回應")
        
    def remove_think_content(self, text: str) -> str:
        import re
        # This pattern matches any text between <think> and </think> (including newlines)
        pattern = r'<think>.*?</think>'
        cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)
        return cleaned_text

            
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
        
        # 5. 生成第一部分回應（案件事實和法律依據）
        first_part = self.generate_first_part(parts['facts'], law_contents,parts.get('injuries', ''))
        
        # 6. 生成第二部分回應（賠償項目）
        second_part = self.generate_second_part(parts.get('injuries', ''), parts.get('claims', ''))
        
        # 7. 合併兩部分回應
        final_response = f"{first_part}{second_part}"

         # 8. 移除所有 <think> ... </think> 區塊
        final_response = self.remove_think_content(final_response)
        
        return final_response