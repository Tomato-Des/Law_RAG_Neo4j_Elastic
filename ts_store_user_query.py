# store_user_queries.py
# THERE IS A DELETE FUNCTION IN THE END OF THIS FILE
import os
import sys
import time
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

class Neo4jUserQueryManager:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        if self.driver:
            self.driver.close()

    def get_max_query_id(self) -> int:
        """Retrieve the maximum query_id from Neo4j"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (q:user_query)
                RETURN COALESCE(MAX(q.query_id), -1) as max_id
                """)
            max_id = result.single()["max_id"]
            return max_id

    def store_user_query(self, query_id: int, query_text: str):
        """Store a user query in Neo4j"""
        with self.driver.session() as session:
            session.run("""
                CREATE (q:user_query {
                    query_id: $query_id, 
                    query_text: $query_text
                })
                """, query_id=query_id, query_text=query_text)
            print(f"Stored user query {query_id}")

def main():
    try:
        # Load environment variables from .env file
        load_dotenv()
        
        # Get Neo4j connection details from environment variables
        neo4j_uri = os.getenv('NEO4J_URI')
        neo4j_user = os.getenv('NEO4J_USER')
        neo4j_password = os.getenv('NEO4J_PASSWORD')
        
        if not all([neo4j_uri, neo4j_user, neo4j_password]):
            print("Error: Neo4j connection details missing from environment variables.")
            print("Make sure NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are set in your .env file.")
            sys.exit(1)
        
        # Initialize Neo4j manager
        neo4j_manager = Neo4jUserQueryManager(neo4j_uri, neo4j_user, neo4j_password)
        
        # Get maximum query_id
        max_query_id = neo4j_manager.get_max_query_id()
        start_query_id = max_query_id + 1
        print(f"\nCurrent maximum query_id in Neo4j: {max_query_id}")
        print(f"Will start storing from query_id: {start_query_id}")
        
        # Prompt for Excel file
        excel_file = input("Enter filename for user queries (XLSX): ").strip()
        
        # Load Excel file
        xl = pd.ExcelFile(excel_file)
        print("Available sheets:", xl.sheet_names)
        
        sheet_name = input("Enter sheet name: ").strip()
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        print("Available columns:", df.columns.tolist())
        
        column = input("Enter column name containing user queries: ").strip()
        
        # Check if column exists
        if column not in df.columns:
            print(f"Error: Column '{column}' not found in the Excel sheet.")
            sys.exit(1)
            
        # Get number of rows in the file
        total_rows = len(df)
        print(f"Total rows in file: {total_rows}")
        
        # Prompt for row range
        start_row = int(input(f"Enter start row (0-{total_rows-1}): ").strip())
        max_end_row = min(start_row + 49, total_rows - 1)  # Limit to 50 records
        end_row = int(input(f"Enter end row (max {max_end_row}): ").strip())
        
        # Validate row range
        if start_row < 0 or end_row >= total_rows or start_row > end_row:
            print("Error: Invalid row range.")
            sys.exit(1)
            
        # Confirm with user
        num_queries = end_row - start_row + 1
        proceed = input(f"About to store {num_queries} user queries. Proceed? (yes/no): ").strip().lower()
        if proceed != 'yes':
            print("Operation cancelled.")
            sys.exit(0)
            
        # Process rows
        for i, (idx, row) in enumerate(df[column][start_row:end_row+1].items()):
            current_query_id = start_query_id + i
            print(f"\nProcessing user query {current_query_id}...")
            
            # Store query in Neo4j
            neo4j_manager.store_user_query(current_query_id, row)
            
        print(f"\nSuccessfully stored {num_queries} user queries in Neo4j.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if 'neo4j_manager' in locals():
            neo4j_manager.close()

if __name__ == "__main__":
    start_time = time.time()
    
    main()
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = int(elapsed_time % 60)
    
    print(f"\nTotal execution time: {hours}h {minutes}m {seconds}s")


## remove_user_queries.py
#import os
#import sys
#import time
#from dotenv import load_dotenv
#from neo4j import GraphDatabase
#
#class Neo4jUserQueryManager:
#    def __init__(self, uri, user, password):
#        self.driver = GraphDatabase.driver(uri, auth=(user, password))
#
#    def close(self):
#        if self.driver:
#            self.driver.close()
#
#    def get_max_query_id(self) -> int:
#        """Retrieve the maximum query_id from Neo4j"""
#        with self.driver.session() as session:
#            result = session.run("""
#                MATCH (q:user_query)
#                RETURN COALESCE(MAX(q.query_id), -1) as max_id
#                """)
#            max_id = result.single()["max_id"]
#            return max_id
#
#    def count_queries_to_remove(self, threshold_id: int) -> int:
#        """Count how many queries would be removed given the threshold"""
#        with self.driver.session() as session:
#            result = session.run("""
#                MATCH (q:user_query)
#                WHERE q.query_id >= $threshold_id
#                RETURN COUNT(q) as count
#                """, threshold_id=threshold_id)
#            return result.single()["count"]
#
#    def remove_queries(self, threshold_id: int) -> int:
#        """Remove all user queries with query_id >= threshold_id"""
#        with self.driver.session() as session:
#            result = session.run("""
#                MATCH (q:user_query)
#                WHERE q.query_id >= $threshold_id
#                WITH COUNT(q) as count
#                MATCH (q:user_query)
#                WHERE q.query_id >= $threshold_id
#                DELETE q
#                RETURN count
#                """, threshold_id=threshold_id)
#            return result.single()["count"]
#
#def main():
#    try:
#        # Load environment variables from .env file
#        load_dotenv()
#        
#        # Get Neo4j connection details from environment variables
#        neo4j_uri = os.getenv('NEO4J_URI')
#        neo4j_user = os.getenv('NEO4J_USER')
#        neo4j_password = os.getenv('NEO4J_PASSWORD')
#        
#        if not all([neo4j_uri, neo4j_user, neo4j_password]):
#            print("Error: Neo4j connection details missing from environment variables.")
#            print("Make sure NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are set in your .env file.")
#            sys.exit(1)
#        
#        # Initialize Neo4j manager
#        neo4j_manager = Neo4jUserQueryManager(neo4j_uri, neo4j_user, neo4j_password)
#        
#        # Get maximum query_id
#        max_query_id = neo4j_manager.get_max_query_id()
#        if max_query_id == -1:
#            print("No user queries found in the database.")
#            sys.exit(0)
#            
#        print(f"\nCurrent maximum query_id in Neo4j: {max_query_id}")
#        
#        # Get threshold ID from user
#        while True:
#            try:
#                threshold_id = int(input(f"Enter the threshold query ID (queries with ID >= this value will be removed): ").strip())
#                break
#            except ValueError:
#                print("Error: Please enter a valid integer.")
#        
#        # Count queries that would be removed
#        count = neo4j_manager.count_queries_to_remove(threshold_id)
#        
#        if count == 0:
#            print(f"\nNo queries found with ID >= {threshold_id}.")
#            sys.exit(0)
#            
#        # Confirm with user
#        proceed = input(f"\nAbout to remove {count} user queries with ID >= {threshold_id}. Proceed? (yes/no): ").strip().lower()
#        if proceed != 'yes':
#            print("Operation cancelled.")
#            sys.exit(0)
#            
#        # Remove queries
#        removed = neo4j_manager.remove_queries(threshold_id)
#        print(f"\nSuccessfully removed {removed} user queries with ID >= {threshold_id}.")
#        
#    except Exception as e:
#        print(f"Error: {str(e)}")
#    finally:
#        if 'neo4j_manager' in locals():
#            neo4j_manager.close()
#
#if __name__ == "__main__":
#    start_time = time.time()
#    
#    main()
#    
#    end_time = time.time()
#    elapsed_time = end_time - start_time
#    
#    hours = int(elapsed_time // 3600)
#    minutes = int((elapsed_time % 3600) // 60)
#    seconds = int(elapsed_time % 60)
#    
#    print(f"\nTotal execution time: {hours}h {minutes}m {seconds}s")