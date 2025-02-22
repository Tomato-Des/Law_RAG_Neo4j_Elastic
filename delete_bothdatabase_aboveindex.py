#Given an index, delete all data equal or larger than the index from both database
#Change treshold index below

from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

class CleanupManager:
    def __init__(self, elasticsearch_host, neo4j_uri):
        # Load environment variables
        load_dotenv()

        # Initialize Elasticsearch
        self.es = Elasticsearch(
            elasticsearch_host,
            http_auth=(os.getenv('ELASTIC_USER'), os.getenv('ELASTIC_PASSWORD')),
            verify_certs=False
        )
        self.es_index_name = 'text_embeddings'

        # Initialize Neo4j
        self.neo4j_driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )

    def delete_from_elasticsearch(self, case_id_threshold):
        # Delete documents with case_id >= threshold in Elasticsearch
        query = {
            "query": {
                "range": {
                    "case_id": {
                        "gte": case_id_threshold
                    }
                }
            }
        }
        try:
            result = self.es.delete_by_query(index=self.es_index_name, body=query)
            print(f"Deleted {result['deleted']} documents from Elasticsearch.")
        except Exception as e:
            print(f"Error deleting from Elasticsearch: {e}")

    def delete_from_neo4j(self, case_id_threshold):
        # Delete nodes and relationships with case_id >= threshold in Neo4j
        with self.neo4j_driver.session() as session:
            try:
                # Delete relationships first
                session.run("""
                    MATCH (c:case_node)-[r]-()
                    WHERE c.case_id >= $case_id_threshold
                    DELETE r
                """, case_id_threshold=case_id_threshold)

                # Delete case nodes
                session.run("""
                    MATCH (c:case_node)
                    WHERE c.case_id >= $case_id_threshold
                    DETACH DELETE c
                """, case_id_threshold=case_id_threshold)

                # Delete associated chunk nodes
                session.run("""
                    MATCH (n)
                    WHERE n.case_id >= $case_id_threshold AND
                          (n:fact_text OR n:law_text OR n:compensation_text)
                    DETACH DELETE n
                """, case_id_threshold=case_id_threshold)

                print(f"Deleted cases with ID >= {case_id_threshold} from Neo4j.")
            except Exception as e:
                print(f"Error deleting from Neo4j: {e}")

    def cleanup(self, case_id_threshold):
        print(f"Starting cleanup for case_id >= {case_id_threshold}...")
        self.delete_from_elasticsearch(case_id_threshold)
        self.delete_from_neo4j(case_id_threshold)
        print("Cleanup complete.")

    def close(self):
        if self.neo4j_driver:
            self.neo4j_driver.close()


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Get database connection info from .env
    ELASTIC_HOST = os.getenv('ELASTIC_HOST', 'https://localhost:9200')
    NEO4J_URI = os.getenv('NEO4J_URI', 'neo4j+s://localhost:7687')



#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    case_id_threshold = 929
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!



    manager = CleanupManager(
        elasticsearch_host=ELASTIC_HOST,
        neo4j_uri=NEO4J_URI
    )

    manager.cleanup(case_id_threshold)
    manager.close()
