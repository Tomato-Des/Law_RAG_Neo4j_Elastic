from elasticsearch import Elasticsearch
import os
from dotenv import load_dotenv

load_dotenv()
username=os.getenv('ELASTIC_USER')
password=os.getenv('ELASTIC_PASSWORD')
print(f"USER={username}, PASS={password}")

# Initialize Elasticsearch client with authentication
es = Elasticsearch(
    "https://localhost:9201",  # Use HTTPS if your server is configured for secure communication
    basic_auth=(username, password),  # Replace with your username and password
    verify_certs=False  # Disable SSL certificate verification if necessary
)

# Check if Elasticsearch is reachable
if not es.ping():
    raise ValueError("Elasticsearch server is not reachable. Please check the server status.")
else: print("Ping Reached ElasticSearch Sever")
