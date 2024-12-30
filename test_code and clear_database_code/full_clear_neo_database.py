import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

def check_and_clear_database():
    try:
        # Load environment variables
        load_dotenv()
        
        # Get Neo4j connection details
        uri = os.getenv('NEO4J_URI')
        user = os.getenv('NEO4J_USER')
        password = os.getenv('NEO4J_PASSWORD')
        
        if not all([uri, user, password]):
            raise ValueError("Missing required environment variables. Please check your .env file.")
            
        # Connect to Neo4j
        driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Connected to Neo4j successfully")
        
        with driver.session() as session:
            # Check if database is empty
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]-() RETURN count(r) as count").single()["count"]
            
            if node_count == 0 and rel_count == 0:
                print("Database is already empty. No clearing needed.")
                return
                
            print(f"Found {node_count} nodes and {rel_count} relationships")
            # 在清除前增加以下程式碼
            confirm = input("Are you sure you want to clear the entire database? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Operation cancelled")
                return
            # Clear all nodes and relationships
            print("Starting database clearing...")
            
            # Delete all relationships first
            result_rel = session.run("MATCH ()-[r]-() DELETE r")
            print("All relationships deleted")
            
            # Then delete all nodes
            result_node = session.run("MATCH (n) DELETE n")
            print("All nodes deleted")
            
            # Verify database is empty
            final_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            if final_count == 0:
                print("Database cleared successfully")
            else:
                print(f"Warning: {final_count} nodes still remain")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()
            print("Database connection closed")

if __name__ == "__main__":
    check_and_clear_database()