import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv('NEO4J_URI')
user = os.getenv('NEO4J_USER')
password = os.getenv('NEO4J_PASSWORD')

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    # Actually test the connection by running a simple query
    with driver.session() as session:
        result = session.run("RETURN 1 as num")
        print(result.single()['num'])
    print("Successfully connected and ran a query")
except Exception as e:
    print(f"Error: {str(e)}")
finally:
    if driver:
        driver.close()