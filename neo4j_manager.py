# neo4j_manager.py
from neo4j import GraphDatabase
from typing import List, Dict
import re

class Neo4jManager:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        if self.driver:
            self.driver.close()

    def create_case_node(self, case_id: int, case_text: str):
        with self.driver.session() as session:
            session.run("""
                MERGE (c:case_node {case_id: $case_id, case_text: $case_text})
                """, case_id=case_id, case_text=case_text)

    def create_chunk_node(self, case_id: int, chunk: str, chunk_type: str):
        with self.driver.session() as session:
            if chunk_type == 'fact':
                session.run("""
                    MERGE (f:fact_text {case_id: $case_id, chunk: $chunk})
                    WITH f
                    MATCH (c:case_node {case_id: $case_id})
                    MERGE (c)-[:fact_text_relation]->(f)
                    """, case_id=case_id, chunk=chunk)
            elif chunk_type == 'law':
                session.run("""
                    MERGE (l:law_text {case_id: $case_id, chunk: $chunk})
                    WITH l
                    MATCH (c:case_node {case_id: $case_id})
                    MERGE (c)-[:law_text_relation]->(l)
                    """, case_id=case_id, chunk=chunk)
            elif chunk_type == 'compensation':
                session.run("""
                    MERGE (comp:compensation_text {case_id: $case_id, chunk: $chunk})
                    WITH comp
                    MATCH (c:case_node {case_id: $case_id})
                    MERGE (c)-[:compensation_text_relation]->(comp)
                    """, case_id=case_id, chunk=chunk)

    def create_law_relationships(self, case_id: int, law_number: str):
        with self.driver.session() as session:
            # 與 case_node 的關係
            session.run("""
                MATCH (c:case_node {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (c)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

            # 與 fact_text 的關係
            session.run("""
                MATCH (f:fact_text {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (f)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

            # 與 law_text 的關係
            session.run("""
                MATCH (lt:law_text {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (lt)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

            # 與 compensation_text 的關係
            session.run("""
                MATCH (comp:compensation_text {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (comp)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

    # 找出當前neo database 最大的case id
    def get_max_case_id(self) -> int:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:case_node)
                RETURN COALESCE(MAX(c.case_id), -1) as max_id
                """)
            max_id = result.single()["max_id"]
            return max_id

    def create_law_nodes(self, law_text: str, law_explanation: str):
        """處理法條和法條說明文本"""
        def extract_laws(text: str) -> List[Dict[str, str]]:
            laws = []
            pattern = r'第(\d+(?:-\d+)?)\s*條[：:]\s*([^第]+)'
            matches = re.finditer(pattern, text)
            for match in matches:
                laws.append({
                    'number': match.group(1),
                    'content': f'第{match.group(1)}條：{match.group(2).strip()}'
                })
            return laws

        with self.driver.session() as session:
            # 創建法條節點
            laws = extract_laws(law_text)
            for law in laws:
                session.run("""
                    MERGE (l:law_node {number: $number})
                    SET l.content = $content
                    """, number=law['number'], content=law['content'])

            # 創建法條說明節點
            explanations = extract_laws(law_explanation)
            for exp in explanations:
                session.run("""
                    MERGE (e:law_explain_node {number: $number})
                    SET e.explanation = $content
                    """, number=exp['number'], content=exp['content'])

            # 建立法條和說明之間的關係
            for law in laws:
                session.run("""
                    MATCH (l:law_node {number: $number})
                    MATCH (e:law_explain_node {number: $number})
                    MERGE (l)-[:law_explain_relation]->(e)
                    """, number=law['number'])