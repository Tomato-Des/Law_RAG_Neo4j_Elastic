# ts_neo4j_manager.py
from neo4j import GraphDatabase
from typing import List, Dict
import re

class Neo4jManager:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        if self.driver:
            self.driver.close()

    def create_case_node(self, case_id: int, case_text: str, case_type: str):
        """Create a case node for indictment only"""
        if case_type != "indictment":
            return  # Only process indictment cases
            
        with self.driver.session() as session:
            session.run("""
                MERGE (c:case_node {case_id: $case_id, case_type: $case_type, case_text: $case_text})
                """, case_id=case_id, case_type=case_type, case_text=case_text)

    def create_indictment_nodes(self, case_id: int, indictment_text: str):
        """Split indictment into fact, law, compensation, conclusion and create nodes"""
        import sys
        
        with self.driver.session() as session:
            # Initialize section variables
            fact_text, law_text, compensation_text, conclusion_text = "", "", "", ""
            
            try:
                # Trim any leading/trailing whitespace
                indictment_text = indictment_text.strip()
                
                # Find positions of required markers
                pos_1 = indictment_text.find("一、")
                
                # For the second marker and "（一）"/"(一)", use regex to ensure there's whitespace before them
                matches_2 = list(re.finditer(r'(?:\s)二、', indictment_text))
                matches_section_1 = list(re.finditer(r'(?:\s)[（(]一[）)]', indictment_text))
                
                # For the conclusion, find either "綜上所陳" or "綜上所述"
                pos_conclusion_1 = indictment_text.find("綜上所陳")
                pos_conclusion_2 = indictment_text.find("綜上所述")
                
                # Use the one that appears in the text (prefer "綜上所陳" if both appear)
                if pos_conclusion_1 != -1:
                    pos_conclusion = pos_conclusion_1
                    conclusion_marker = "綜上所陳"
                elif pos_conclusion_2 != -1:
                    pos_conclusion = pos_conclusion_2
                    conclusion_marker = "綜上所述"
                else:
                    pos_conclusion = -1
                    conclusion_marker = "綜上所陳/綜上所述"
                
                # Check if all required markers exist
                if pos_1 == -1:
                    print(f"錯誤: 起訴狀中缺少「一、」標記 (case_id: {case_id})")
                    sys.exit(1)
                    
                if not matches_2:
                    print(f"錯誤: 起訴狀中缺少「二、」標記或其前面沒有空格/換行 (case_id: {case_id})")
                    sys.exit(1)
                    
                if not matches_section_1:
                    print(f"錯誤: 起訴狀中缺少「（一）」或「(一)」標記或其前面沒有空格/換行 (case_id: {case_id})")
                    sys.exit(1)
                    
                if pos_conclusion == -1:
                    print(f"錯誤: 起訴狀中缺少「綜上所陳」或「綜上所述」標記 (case_id: {case_id})")
                    sys.exit(1)
                
                pos_2 = matches_2[0].start() + 1  # +1 to point to the actual "二" character
                pos_section_1 = matches_section_1[0].start() + 1  # +1 to point to the actual "（" or "(" character
                
                # Check if they are in correct order
                if not (pos_1 < pos_2 < pos_section_1 < pos_conclusion):
                    section_marker = indictment_text[pos_section_1:pos_section_1+3]
                    print(f"錯誤: 起訴狀標記順序錯誤: 一、({pos_1}) 二、({pos_2}) {section_marker}({pos_section_1}) {conclusion_marker}({pos_conclusion}) (case_id: {case_id})")
                    sys.exit(1)
                
                # Extract the content of the different parts
                fact_text = indictment_text[pos_1:pos_2-1].strip()
                law_text = indictment_text[pos_2:pos_section_1-1].strip()
                compensation_text = indictment_text[pos_section_1:pos_conclusion].strip()
                conclusion_text = indictment_text[pos_conclusion:].strip()
                
                # Check if any section is empty
                if not fact_text:
                    print(f"錯誤: 起訴狀「一、」部分內容為空 (case_id: {case_id})")
                    sys.exit(1)
                if not law_text:
                    print(f"錯誤: 起訴狀「二、」部分內容為空 (case_id: {case_id})")
                    sys.exit(1)
                if not compensation_text:
                    section_marker = indictment_text[pos_section_1:pos_section_1+3]
                    print(f"錯誤: 起訴狀「{section_marker}」部分內容為空 (case_id: {case_id})")
                    sys.exit(1)
                if not conclusion_text:
                    print(f"錯誤: 起訴狀「{conclusion_marker}」部分內容為空 (case_id: {case_id})")
                    sys.exit(1)
                    
            except Exception as e:
                print(f"錯誤: 分割起訴狀文本時發生錯誤 (case_id: {case_id}): {str(e)}")
                sys.exit(1)
    
            # Create nodes for each section without subnodes for compensation
            session.run("""
                MERGE (f:fact_text {case_id: $case_id, chunk: $chunk})
                WITH f
                MATCH (c:case_node {case_id: $case_id})
                MERGE (c)-[:fact_text_relation]->(f)
                """, case_id=case_id, chunk=fact_text)
    
            session.run("""
                MERGE (l:law_text {case_id: $case_id, chunk: $chunk})
                WITH l
                MATCH (c:case_node {case_id: $case_id})
                MERGE (c)-[:law_text_relation]->(l)
                """, case_id=case_id, chunk=law_text)
    
            session.run("""
                MERGE (comp:compensation_text {case_id: $case_id, chunk: $chunk})
                WITH comp
                MATCH (c:case_node {case_id: $case_id})
                MERGE (c)-[:compensation_text_relation]->(comp)
                """, case_id=case_id, chunk=compensation_text)
    
            session.run("""
                MERGE (conc:conclusion_text {case_id: $case_id, chunk: $chunk})
                WITH conc
                MATCH (c:case_node {case_id: $case_id})
                MERGE (c)-[:conclusion_text_relation]->(conc)
                """, case_id=case_id, chunk=conclusion_text)

    def create_law_relationships(self, case_id: int, law_number: str):
        with self.driver.session() as session:
            # Relationship with case_node
            session.run("""
                MATCH (c:case_node {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (c)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

            # Relationship with fact_text
            session.run("""
                MATCH (f:fact_text {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (f)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

            # Relationship with law_text
            session.run("""
                MATCH (lt:law_text {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (lt)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

            # Relationship with compensation_text
            session.run("""
                MATCH (comp:compensation_text {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (comp)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

            # Relationship with conclusion_text (if exists)
            session.run("""
                MATCH (conc:conclusion_text {case_id: $case_id})
                MATCH (l:law_node {number: $law_number})
                MERGE (conc)-[:used_law_relation]->(l)
                """, case_id=case_id, law_number=law_number)

    def get_max_case_id(self) -> int:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:case_node)
                RETURN COALESCE(MAX(c.case_id), -1) as max_id
                """)
            max_id = result.single()["max_id"]
            return max_id

    def create_law_nodes(self, law_text: str, law_explanation: str):
        """Process law and law explanation texts"""
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
            # Create law nodes
            laws = extract_laws(law_text)
            for law in laws:
                session.run("""
                    MERGE (l:law_node {number: $number})
                    SET l.content = $content
                    """, number=law['number'], content=law['content'])

            # Create law explanation nodes
            explanations = extract_laws(law_explanation)
            for exp in explanations:
                session.run("""
                    MERGE (e:law_explain_node {number: $number})
                    SET e.explanation = $content
                    """, number=exp['number'], content=exp['content'])

            # Create relationships between law and explanation
            for law in laws:
                session.run("""
                    MATCH (l:law_node {number: $number})
                    MATCH (e:law_explain_node {number: $number})
                    MERGE (l)-[:law_explain_relation]->(e)
                    """, number=law['number'])