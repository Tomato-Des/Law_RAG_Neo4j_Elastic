# models.py
from typing import List, Dict, Any
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel

class EmbeddingModel:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained('TencentBAC/Conan-embedding-v1')
        self.model = AutoModel.from_pretrained('TencentBAC/Conan-embedding-v1')
        self.max_length = 512  # 設定最大長度

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        # 加入長度限制
        inputs = self.tokenizer(
            texts, 
            padding=True, 
            truncation=True, 
            max_length=self.max_length,
            return_tensors='pt'
        )
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].numpy()