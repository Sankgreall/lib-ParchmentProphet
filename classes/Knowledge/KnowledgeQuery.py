import torch
import torch.nn as nn
from transformers import BertTokenizer, BertModel
import random
import numpy as np
import textwrap
import warnings
import transformers
import json

# Import text functions
try:
    # Try relative imports for deployment
    from ....modules.elastic import *
    from ....modules.neo4j import *
except ImportError:
    try:
        # Fallback to absolute imports with project name for structured imports
        from ParchmentProphet.modules.elastic import *
        from ParchmentProphet.modules.neo4j import *
    except ImportError:
        # Fallback to simple absolute imports for local testing
        from modules.neo4j import *
        from modules.elastic import *

# Suppress FutureWarning from transformers
warnings.filterwarnings("ignore", category=FutureWarning)

# Suppress UserWarning (which includes the beta/gamma warnings)
warnings.filterwarnings("ignore", category=UserWarning)

# Disable tokenizer parallelism warning
transformers.utils.logging.set_verbosity_error()

# Import text functions
try:
    # Try relative imports for deployment
    from ....modules.text import *
    from ....modules.markdown import *
    from ....ai_handler import AIHandler
    from ....modules.elastic import *
    from ....modules.neo4j import *
except ImportError:
    try:
        # Fallback to absolute imports with project name for structured imports
        from ParchmentProphet.modules.text import *
        from ParchmentProphet.modules.markdown import *
        from ParchmentProphet.classes.ai_handler import AIHandler
        from ParchmentProphet.modules.elastic import *
        from ParchmentProphet.modules.neo4j import *
    except ImportError:
        # Fallback to simple absolute imports for local testing
        from modules.text import *
        from modules.markdown import *
        from classes.ai_handler import AIHandler
        from modules.neo4j import *
        from modules.elastic import *


from .prompts.claim import answer_claim_system_prompt, answer_claim_user_prompt

class KnowledgeQuery:

    def __init__(self, seed=42):
        self.set_seed(seed)
        self.driver = get_neo4j()
        
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        self.model = BertModel.from_pretrained('bert-base-uncased')
        
        self.projection = nn.Linear(768, 64)
        self.init_projection()

        self.completed_questionnaire = {}
        self.ai_handler = AIHandler.load()

        # MODELS
        self.latest_models = self.get_latest_models()
        self.report_gen_model = self.latest_models.get("report_gen_model","gpt-4o-2024-08-06")
        self.claim_answer_model = self.latest_models.get("claim_answer_model","gpt-4o-2024-08-06")
        self.graph_model = self.latest_models.get("graph_model","gpt-4o-2024-08-06")
        self.claim_model = self.latest_models.get("claim_model","gpt-4o-2024-08-06")

        self.claim_training =[]
        self.training_index = "prod-answer-training"

    def get_latest_models(self):
        try:
            query = {
                "sort": [
                    {"created": {"order": "desc"}}
                ],
                "size": 1
            }
            result = search_es(self.MODELS_INDEX, query)
            
            if result["hits"]["total"]["value"] > 0:
                results = result["hits"]["hits"][0]["_source"]
                return results
            else:
                # return default
                return {
                    "report_gen_model": "gpt-4o-2024-08-06",
                    "claim_answer_model": "gpt-4o-2024-08-06",
                    "graph_model": "gpt-4o-2024-08-06",
                    "claim_model": "gpt-4o-2024-08-06",
                }
        except Exception:
            # return default
            return {
                "report_gen_model": "gpt-4o-2024-08-06",
                "claim_answer_model": "gpt-4o-2024-08-06",
                "graph_model": "gpt-4o-2024-08-06",
                "claim_model": "gpt-4o-2024-08-06",
            }

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
            
    def answer_questions_from_claims(self, questionnaire, claims):
        for question in questionnaire['questionnaire']:
            claims_by_document_id = {}

            # Retrieve all claims that match the category
            for claim in claims:
                if claim['category'] == question['category']:
                    document_id = claim['document_id']
                    if document_id not in claims_by_document_id:
                        claims_by_document_id[document_id] = []
                    claims_by_document_id[document_id].append(claim)

            # Now we construct the overall string to inject into prompt
            claims_string = ""
            for doc_id, category_claims in claims_by_document_id.items():
                # Sort claims by relevance (convert to float to handle both int and string cases)
                sorted_claims = sorted(category_claims, key=lambda x: float(x['relevance']), reverse=True)

                # Extract document metadata from first claim in the list
                first_claim = sorted_claims[0]
                claims_string += f"\n## {first_claim['document_metadata']['title']}\n"
                claims_string += f"Document ID: {doc_id}\n"
                claims_string += f"Type of document: {first_claim['document_summary']['type_of_document']}\n"
                claims_string += f"Temporal information: {first_claim['document_summary']['temporal_details']}\n"
                claims_string += f"Summary: {first_claim['document_summary']['document_summary']}\n\n"

                claims_string += "### Claims\n"

                # Iterate through all claims for this document (now sorted)
                for claim in sorted_claims:
                    claims_string += f"\nClaim: {claim['claim']}\n"
                    claims_string += f"Source: {claim['source']}\n"
                    claims_string += "Supporting Quotes:\n"
                    for quote in claim['quotes']:
                        claims_string += f"   \"{quote}\"\n"
                    # claims_string += f"Relevance: {claim['relevance']}\n"
                    # claims_string += f"Relevance Explanation: {claim['relevance_explanation']}\n"
                    claims_string += "\n"  # Add a blank line between claims

            system_prompt = textwrap.dedent(answer_claim_system_prompt).strip()
            user_prompt = textwrap.dedent(answer_claim_user_prompt).strip().format(question=question['question'], documents=claims_string)

            # Request completion from the AI
            answer = self.ai_handler.request_completion(system_prompt, user_prompt, model=self.claim_answer_model)
            self.completed_questionnaire[question['question']] = answer

            # Add to training data
            self.claim_training.append({
                "project_id": claim['project_id'],
                "question": question['question'],
                "category": claim['category'],
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "generated_answer": answer,
            })

        # Submit training data to Elasticsearch
        self.submit_training_data()

        return self.completed_questionnaire
    
    def submit_training_data(self):

        for training_data in self.claim_training:
            # ID should be base64(project_id + category + question)
            id = base64.b64encode(f"{training_data['project_id']}_{training_data['category']}_{training_data['question']}".encode()).decode()
            add_to_es(self.training_index, training_data, id)

    

