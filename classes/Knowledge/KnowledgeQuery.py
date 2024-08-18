import torch
import torch.nn as nn
from transformers import BertTokenizer, BertModel
import random
import numpy as np

import warnings
import transformers

# Suppress FutureWarning from transformers
warnings.filterwarnings("ignore", category=FutureWarning)

# Suppress UserWarning (which includes the beta/gamma warnings)
warnings.filterwarnings("ignore", category=UserWarning)

# Disable tokenizer parallelism warning
transformers.utils.logging.set_verbosity_error()

# Import the Neo4j functions from your existing document
from modules.neo4j import *

class KnowledgeQuery:

    def __init__(self, seed=42):
        self.set_seed(seed)
        self.driver = get_neo4j()
        
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        self.model = BertModel.from_pretrained('bert-base-uncased')
        
        self.projection = nn.Linear(768, 64)
        self.init_projection()

    def set_seed(self, seed):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    def init_projection(self):
        torch.nn.init.xavier_uniform_(self.projection.weight, gain=1.0)
        torch.nn.init.zeros_(self.projection.bias)
        
    def get_bert_embedding(self, text):
        inputs = self.tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs)
        embedding = outputs.last_hidden_state[:, 0, :].squeeze()
        projected_embedding = self.projection(embedding)
        return projected_embedding.tolist()

    def search(self, query_text, top_k=5, entity_types=None, include_entities=None, exclude_entities=None):
        query_embedding = self.get_bert_embedding(query_text)
        results = similarity_search_neo4j(
            query_embedding, 
            query_text, 
            top_k=top_k, 
            entity_types=entity_types, 
            include_entities=include_entities, 
            exclude_entities=exclude_entities
        )
        return results