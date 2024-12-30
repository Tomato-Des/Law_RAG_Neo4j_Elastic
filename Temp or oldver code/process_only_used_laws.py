import os
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv
import re
from typing import List

class LawProcessor:
    def __init__(self):
        load_dotenv()
        
        # Neo4j setup
        self.uri = os.getenv('NEO4J_URI')
        self.user = os.getenv('NEO4J_USER')
        self.password = os.getenv('NEO4J_PASSWORD')
        
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Missing required environment variables. Please check your .env file.")
            
        self.driver = None
        # Fixed case ID range
        self.case_ids = list(range(469, 983))  # 469 to 982 inclusive

    def connect_neo4j(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            print("Successfully connected to Neo4j")
        except Exception as e:
            print(f"Error connecting to Neo4j: {str(e)}")
            raise

    def close(self):
        if self.driver:
            self.driver.close()

    def extract_law_numbers(self, law_text: str) -> List[str]:
        """Extract law numbers from text"""
        law_numbers = []
        for law in law_text.split(','):
            match = re.search(r'第(\d+(?:-\d+)?)\s*條', law.strip())
            if match:
                law_numbers.append(match.group(1))
        return law_numbers

    def process_used_laws(self, case_id: int, used_laws_str: str):
        """Process used laws for a single case"""
        try:
            law_numbers = self.extract_law_numbers(used_laws_str)
            if not law_numbers:
                print(f"警告：案件 {case_id} 沒有有效的法條")
                return

            with self.driver.session() as session:
                # First verify case exists
                result = session.run("""
                    MATCH (c:case_node {case_id: $case_id})
                    RETURN count(c) as count
                    """, case_id=case_id).single()

                if not result or result["count"] == 0:
                    print(f"警告：找不到案件節點 {case_id}")
                    return

                for law_number in law_numbers:
                    # Check if law_node exists
                    result = session.run("""
                        MATCH (l:law_node {number: $law_number})
                        RETURN count(l) as count
                        """, law_number=law_number).single()

                    if result and result["count"] > 0:
                        # Create relationships
                        session.run("""
                            MATCH (c:case_node {case_id: $case_id})
                            MATCH (l:law_node {number: $law_number})
                            MERGE (c)-[:used_law_relation]->(l)
                            """, case_id=case_id, law_number=law_number)

                        # First check how many fact_text nodes exist
                        result = session.run("""
                            MATCH (f:fact_text {case_id: $case_id})
                            RETURN count(f) as count
                            """, case_id=case_id).single()
                        fact_count = result["count"]
                        print(f"Found {fact_count} fact_text nodes for case {case_id}")

                        # Then create the relationships
                        session.run("""
                            MATCH (f:fact_text {case_id: $case_id})
                            MATCH (l:law_node {number: $law_number})
                            MERGE (f)-[:used_law_relation]->(l)
                            """, case_id=case_id, law_number=law_number)

                        session.run("""
                            MATCH (lt:law_text {case_id: $case_id})
                            MATCH (l:law_node {number: $law_number})
                            MERGE (lt)-[:used_law_relation]->(l)
                            """, case_id=case_id, law_number=law_number)

                        session.run("""
                            MATCH (comp:compensation_text {case_id: $case_id})
                            MATCH (l:law_node {number: $law_number})
                            MERGE (comp)-[:used_law_relation]->(l)
                            """, case_id=case_id, law_number=law_number)
                        
                        print(f"成功為案件 {case_id} 建立與法條 {law_number} 的關係")
                    else:
                        print(f"警告：找不到法條節點 {law_number}")

        except Exception as e:
            print(f"處理案件 {case_id} 的法條時發生錯誤: {str(e)}")

    def process_range(self):
        try:
            self.connect_neo4j()

            print("\n處理法條...")
            laws_file = input("Enter filename for used laws (XLSX): ").strip()
            xl = pd.ExcelFile(laws_file)
            print("Available sheets:", xl.sheet_names)
            
            sheet_name = input("Enter sheet name: ").strip()
            laws_df = pd.read_excel(laws_file, sheet_name=sheet_name)
            print("Available columns:", laws_df.columns.tolist())
            
            column = input("Enter column name: ").strip()
            print(f"Available rows: 0 to {len(laws_df)-1}")
            
            start_row = int(input("Enter start row: ").strip())
            end_row = int(input("Enter end row: ").strip())

            if start_row < 0 or end_row >= len(laws_df) or start_row > end_row:
                raise ValueError("Invalid row range")
                
            # Verify we're getting exactly 514 rows
            row_count = end_row - start_row + 1
            if row_count != 514:
                raise ValueError(f"必須選擇514行資料，目前選擇了 {row_count} 行")

            print(f"\n將讀取 Excel 第 {start_row} 到 {end_row} 行")
            print("這些資料將對應到案件 ID 469 到 982")
            
            confirm = input("是否繼續？ (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("操作已取消")
                return

            # Get the selected rows
            selected_data = laws_df[column][start_row:end_row+1]
            
            # Process each row, mapping to fixed case IDs
            for i, (_, law_text) in enumerate(selected_data.items()):
                case_id = self.case_ids[i]
                print(f"\n處理 Excel 第 {start_row + i} 行的法條，對應案件 ID: {case_id}")
                self.process_used_laws(case_id, law_text)

        except Exception as e:
            print(f"執行過程中發生錯誤: {str(e)}")
        finally:
            self.close()

if __name__ == "__main__":
    processor = LawProcessor()
    processor.process_range()