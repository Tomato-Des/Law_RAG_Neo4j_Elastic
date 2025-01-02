import os
from dotenv import load_dotenv
import pandas as pd
from neo4j import GraphDatabase
import re
from datetime import datetime
# a debug use code, compare the input .xlsx file's law with the fact_text_node->used_law_relation->law_nodes's number
# to check if the main.py properly create the relationship since the used_law is very important in RAG's result!
class LawComparison:
    def __init__(self):
        load_dotenv()
        self.neo4j_driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = f"law_comparison_{timestamp}.txt"
        
    def log_message(self, message: str, print_to_console: bool = True):
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(message + '\n')
        if print_to_console:
            print(message)

    def extract_law_numbers(self, text: str) -> list:
        if pd.isna(text):
            return []
            
        numbers = []
        matches = re.finditer(r'第(\d+(?:-\d+)?)\s*條', text)
        for match in matches:
            numbers.append(match.group(1))
        return sorted(numbers)

    def get_laws_from_neo4j(self, case_id: int) -> dict:
        """Get law numbers for each fact_text node of a specific case from Neo4j"""
        with self.neo4j_driver.session() as session:
            result = session.run("""
                MATCH (f:fact_text {case_id: $case_id})
                OPTIONAL MATCH (f)-[:used_law_relation]->(l:law_node)
                RETURN f.chunk_id as chunk_id, 
                       COLLECT(DISTINCT l.number) as laws
                ORDER BY f.chunk_id
                """, case_id=case_id)
            
            fact_nodes = {}
            for record in result:
                fact_nodes[record["chunk_id"]] = sorted(record["laws"]) if record["laws"][0] is not None else []
            return fact_nodes

    def compare_laws(self):
        # Get Excel file details from user
        self.log_message("\n=== Law Comparison Tool ===")
        case_file = input("Enter filename for used laws (XLSX): ").strip()
        xl = pd.ExcelFile(case_file)
        self.log_message("Available sheets:" + str(xl.sheet_names))
        
        sheet_name = input("Enter sheet name: ").strip()
        df = pd.read_excel(case_file, sheet_name=sheet_name)
        self.log_message("Available columns:" + str(df.columns.tolist()))
        
        column = input("Enter column name for used laws: ").strip()
        self.log_message(f"Available rows: 0 to {len(df)-1}")
        
        start_row = int(input("Enter start row: ").strip())
        end_row = int(input("Enter end row: ").strip())

        # Log input parameters
        self.log_message("\n=== Input Parameters ===")
        self.log_message(f"File: {case_file}")
        self.log_message(f"Sheet: {sheet_name}")
        self.log_message(f"Column: {column}")
        self.log_message(f"Rows: {start_row} to {end_row}")

        self.log_message("\n=== Starting Comparison ===")
        unmatched_count = 0
        total_fact_nodes = 0
        unmatched_fact_nodes = 0
        
        # Process each row
        for i, (_, row) in enumerate(df[column][start_row:end_row+1].items(), start=start_row):
            case_id = i
            excel_laws = self.extract_law_numbers(row)
            fact_nodes = self.get_laws_from_neo4j(case_id)
            
            self.log_message(f"\n=== Case {case_id} ===")
            self.log_message(f"Excel laws: {excel_laws}")
            
            if not fact_nodes:
                self.log_message(f"WARNING: No fact_text nodes found for case_id {case_id}")
                unmatched_count += 1
                continue

            case_has_mismatch = False
            for chunk_id, neo4j_laws in fact_nodes.items():
                total_fact_nodes += 1
                
                # Compare the laws
                is_match = (sorted(excel_laws) == sorted(neo4j_laws))
                if not is_match:
                    case_has_mismatch = True
                    unmatched_fact_nodes += 1
                    self.log_message(f"\nMismatch in {chunk_id}:")
                    self.log_message(f"Neo4j laws: {neo4j_laws}")
                    self.log_message(f"Only in Excel: {set(excel_laws) - set(neo4j_laws)}")
                    self.log_message(f"Only in Neo4j: {set(neo4j_laws) - set(excel_laws)}")
                else:
                    self.log_message(f"\n{chunk_id}: Match ✓")

            if case_has_mismatch:
                unmatched_count += 1

        # Print and log summary
        total_cases = end_row - start_row + 1
        case_match_rate = ((total_cases - unmatched_count) / total_cases) * 100
        fact_match_rate = ((total_fact_nodes - unmatched_fact_nodes) / total_fact_nodes) * 100

        summary = f"""
=== Comparison Summary ===
Total cases checked: {total_cases}
Total fact_text nodes checked: {total_fact_nodes}
Cases with mismatches: {unmatched_count}
Fact nodes with mismatches: {unmatched_fact_nodes}
Case match rate: {case_match_rate:.2f}%
Fact node match rate: {fact_match_rate:.2f}%
"""
        self.log_message(summary)
        self.log_message(f"\nResults have been saved to: {self.output_file}")

    def close(self):
        if self.neo4j_driver:
            self.neo4j_driver.close()

def main():
    comparison = LawComparison()
    try:
        comparison.compare_laws()
    finally:
        comparison.close()

if __name__ == "__main__":
    main()