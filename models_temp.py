# models_temp.py
from typing import List
import numpy as np
import requests

class EmbeddingModel:
    def __init__(self):
        self.model_name = "kenneth85/llama-3-taiwan:8b-instruct-dpo-q6_K"
        # Test the connection to Ollama
        try:
            response = requests.get('http://localhost:11434/api/version')
            if response.status_code != 200:
                raise ConnectionError("Cannot connect to Ollama service")
            print("Successfully connected to Ollama service")
        except Exception as e:
            print(f"Error connecting to Ollama: {str(e)}")
            raise

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for a list of texts
        Returns numpy array to maintain compatibility with original code
        """
        try:
            embeddings = []
            for text in texts:
                response = requests.post(
                    'http://localhost:11434/api/embeddings',
                    json={
                        "model": self.model_name,
                        "prompt": text
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"Error from Ollama API: {response.status_code}")
                
                embedding = response.json()['embedding']
                embeddings.append(embedding)
            
            return np.array(embeddings)
            
        except Exception as e:
            print(f"Error getting embeddings: {str(e)}")
            raise