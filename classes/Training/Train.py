import os
import json
import json
from typing import List, Dict, Any
import textwrap
import hashlib
import yaml
from collections import OrderedDict
import tempfile


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

# Index in Elastic where documents are stored
DOCUMENTS_INDEX = "prod-documents"

class Train:

    def __init__(self, provider="openai"):

        self.report_training_index = "prod-report-training"
        self.answer_training_index = "prod-answer-training"
        self.graph_training_index = "prod-graph-training"
        self.claim_training_index = "prod-claim-training"



        self.token_limit = 600
        self.previous_chunk_limit = self.token_limit * 0.5

        self.ai_handler = AIHandler.load(provider)    

    def train(self):
        reports = self.retrieve_report_training_samples()
        print(f"Retrieved {len(reports)} reports for training")
        processed_messages = []
        
        for report in reports:
            processed_messages.append(self.reconstruct_messages(report))

        # Create tempfile to contain json data
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp:

            file_path = temp.name
            
            # For each report, output messages array as jsonline
            for report in processed_messages:
                messages = {"messages": report}
                temp.write(json.dumps(messages) + "\n")

        # With the training file created, we can train
        print(f"Training model with {len(processed_messages)} samples")
        new_model = self.ai_handler.fine_tune_model(file_path, base_model="gpt-4o-2024-08-06")

        # delete the temp file
        os.unlink(temp.name)

        return new_model

    def train_answers(self, base_model="gpt-4o-2024-08-06"):
        samples = self.retrieve_answer_training_samples()
        print(f"Retrieved {len(samples)} samples for training")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp:
            file_path = temp.name
            
            for sample in samples:
                if sample.get("human_answer") != "":
                    messages = []
                    messages.append({"role": "system", "content": sample["system_prompt"]})
                    messages.append({"role": "user", "content": sample.get("user_prompt")})
                    messages.append({"role": "assistant", "content": sample["human_answer"]})
                    temp.write(json.dumps({"messages": messages}) + "\n")

        try:
            new_model = self.ai_handler.fine_tune_model(file_path, base_model=base_model)
            return new_model
        finally:
            os.unlink(file_path)

    def train_entity_extraction(self, base_model="gpt-4o-2024-08-06"):
        samples = self.retrieve_graph_training_samples()
        print(f"Retrieved {len(samples)} samples for training")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp:
            file_path = temp.name
            
            for sample in samples:
                if sample.get("human_response") != "":
                    messages = []
                    messages.append({"role": "system", "content": sample["system_prompt"]})
                    messages.append({"role": "user", "content": sample.get("user_prompt")})
                    messages.append({"role": "assistant", "content": sample["human_response"]})
                    temp.write(json.dumps({"messages": messages}) + "\n")
                    print(json.dumps({"messages": messages}))
                    exit()

        try:
            new_model = self.ai_handler.fine_tune_model(file_path, base_model=base_model)
            return new_model
        finally:
            os.unlink(file_path)

    def train_claims(self, base_model="gpt-4o-2024-08-06"):
        samples = self.retrieve_claim_training_samples()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp:
            file_path = temp.name
            
            for sample in samples:
                if sample.get("human_answer") != "":
                    messages = []
                    messages.append({"role": "system", "content": sample["system_prompt"]})
                    messages.append({"role": "user", "content": sample.get("user_prompt")})
                    messages.append({"role": "assistant", "content": sample["human_answer"]})
                    temp.write(json.dumps({"messages": messages}) + "\n")

        try:
            new_model = self.ai_handler.fine_tune_model(file_path, base_model=base_model)
            return new_model
        finally:
            os.unlink(file_path)

    def retrieve_claim_training_samples(self):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "human_response"}},
                        {
                            "script": {
                                "script": {
                                    "source": "doc['human_response.keyword'].value != ''",
                                    "lang": "painless"
                                }
                            }
                        }
                    ]
                }
            },
            "size": 100  # Adjust this value based on your needs
        }
        
        result = search_es(self.claim_training_index, query)
        
        if result["hits"]["total"]["value"] > 0:
            return [hit["_source"] for hit in result["hits"]["hits"]]
        
        return []


    def retrieve_graph_training_samples(self):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "human_response"}},
                        {
                            "script": {
                                "script": {
                                    "source": "doc['human_response.keyword'].value != ''",
                                    "lang": "painless"
                                }
                            }
                        }
                    ]
                }
            },
            "size": 100  # Adjust this value based on your needs
        }
        
        result = search_es(self.answer_training_index, query)
        
        if result["hits"]["total"]["value"] > 0:
            return [hit["_source"] for hit in result["hits"]["hits"]]
        
        return []

    def retrieve_answer_training_samples(self):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "human_answer"}},
                        {
                            "script": {
                                "script": {
                                    "source": "doc['human_answer.keyword'].value != ''",
                                    "lang": "painless"
                                }
                            }
                        }
                    ]
                }
            },
            "size": 100  # Adjust this value based on your needs
        }
        
        result = search_es(self.answer_training_index, query)
        
        if result["hits"]["total"]["value"] > 0:
            return [hit["_source"] for hit in result["hits"]["hits"]]
        
        return []

    def retrieve_report_training_samples(self, size=100):
        query = {
            "query": {
                "match_all": {}
            },
            "size": size
        }
        
        result = search_es(self.report_training_index, query)
        
        if result["hits"]["total"]["value"] > 0:
            documents = [
                {**hit["_source"], "_id": hit["_id"]}
                for hit in result["hits"]["hits"]
            ]
            return documents
        
        return []

    def reconstruct_messages(self, report):

        messages = []
        
        # Add system prompt
        system_prompt = textwrap.dedent(report['system_prompt_template']).strip().format(persona=report['persona'])
        messages.append({"role": "system", "content": system_prompt})
        
        # Add first user prompt
        first_user_prompt = textwrap.dedent(report['first_user_prompt_template']).strip().format(
            answers=self.format_answers(report['answers']),
            report_scope=report['report_scope'],
            example=report['sections'][0]['example'],
            section_brief=report['sections'][0]['prompt']
        )
        messages.append({"role": "user", "content": first_user_prompt})
        
        # Add assistant's response for the first section
        messages.append({"role": "assistant", "content": report['sections'][0]['human_content']})
        
        # Add subsequent sections
        for section in report['sections'][1:]:
            subsequent_user_prompt = textwrap.dedent(report['subsequent_user_prompt_template']).strip().format(
                example=section['example'],
                section_brief=section['prompt']
            )
            messages.append({"role": "user", "content": subsequent_user_prompt})
            messages.append({"role": "assistant", "content": section['human_content']})
        
        return messages

    @staticmethod
    def format_answers(answers):
        formatted_qa = []
        for item in answers:
            formatted_qa.append(f"Question: {item['question']}\nAnswer: {Train.strip_references(item['answer'])}")
        return "\n\n".join(formatted_qa)

    @staticmethod
    def strip_references(text):
        # Strip references like [1], [2], etc.
        text = re.sub(r'\[\d+\]', '', text)

        # Remove everything after line break
        text = text.split("\n")[0]
        return text
