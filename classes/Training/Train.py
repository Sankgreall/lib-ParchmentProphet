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

    def train_report_generation(self, base_model="gpt-4o-2024-08-06"):
        reports = self.retrieve_report_training_samples()
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
        new_model = self.ai_handler.fine_tune_model(file_path, base_model)

        # delete the temp file
        os.unlink(temp.name)

        return new_model

    def train_answer_generation(self, base_model="gpt-4o-2024-08-06"):
        samples = self.retrieve_training_samples(self.answer_training_index)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp:
            file_path = temp.name
            
            for sample in samples:
                if sample.get("human_response") != "":
                    messages = []
                    messages.append({"role": "system", "content": sample["system_prompt"]})
                    messages.append({"role": "user", "content": sample.get("user_prompt")})
                    messages.append({"role": "assistant", "content": sample["human_response"]})
                    temp.write(json.dumps({"messages": messages}) + "\n")

        try:
            new_model = self.ai_handler.fine_tune_model(file_path, base_model=base_model)
            return new_model
        finally:
            os.unlink(file_path)

    def train_graph_extraction(self, base_model="gpt-4o-2024-08-06"):
        samples = self.retrieve_training_samples(self.graph_training_index)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp:
            file_path = temp.name
            
            for sample in samples:
                if sample.get("human_response") != "":
                    messages = []
                    messages.append({"role": "system", "content": sample["system_prompt"]})
                    messages.append({"role": "user", "content": sample.get("user_prompt")})
                    messages.append({"role": "assistant", "content": sample["human_response"]})
                    temp.write(json.dumps({"messages": messages}) + "\n")

        try:
            new_model = self.ai_handler.fine_tune_model(file_path, base_model=base_model)
            return new_model
        finally:
            os.unlink(file_path)

    def train_claim_extraction(self, base_model="gpt-4o-2024-08-06"):
        samples = self.retrieve_training_samples(self.claim_training_index)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp:
            file_path = temp.name
            
            for sample in samples:
                if sample.get("human_response") != "":
                    messages = []
                    messages.append({"role": "system", "content": sample["system_prompt"]})
                    messages.append({"role": "user", "content": sample.get("user_prompt")})
                    messages.append({"role": "assistant", "content": sample["human_response"]})
                    temp.write(json.dumps({"messages": messages}) + "\n")

        try:
            new_model = self.ai_handler.fine_tune_model(file_path, base_model=base_model)
            return new_model
        finally:
            os.unlink(file_path)

    def retrieve_training_samples(self, index):
        query = {
            "query": {
                "exists": {
                    "field": "human_response"
                }
            },
            "size": 100  
        }
        
        result = search_es(index, query)
        
        if result["hits"]["total"]["value"] > 0:
            return [hit["_source"] for hit in result["hits"]["hits"]]
        
        return []
    
    def retrieve_report_training_samples(self, size=100):
        query = {
            "size": size,
            "runtime_mappings": {
                "all_sections_have_human_response": {
                    "type": "boolean",
                    "script": {
                        "source": """
                            def sections = params._source.sections;
                            if (sections == null || sections.empty) {
                                emit(false);
                            } else {
                                for (def section : sections) {
                                    if (section.human_response == null || section.human_response.empty) {
                                        emit(false);
                                        return;
                                    }
                                }
                                emit(true);
                            }
                        """
                    }
                }
            },
            "query": {
                "term": {
                    "all_sections_have_human_response": {
                        "value": True
                    }
                }
            },
            "_source": True  # This ensures we get the full source of each document
        }

        result = search_es("prod-report-training", query)
        
        # Extract and return the source of each matching document
        matching_documents = [hit['_source'] for hit in result['hits']['hits']]
        
        return matching_documents

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
        messages.append({"role": "assistant", "content": report['sections'][0]['human_response']})
        
        # Add subsequent sections
        for section in report['sections'][1:]:
            subsequent_user_prompt = textwrap.dedent(report['subsequent_user_prompt_template']).strip().format(
                example=section['example'],
                section_brief=section['prompt']
            )
            messages.append({"role": "user", "content": subsequent_user_prompt})
            messages.append({"role": "assistant", "content": section['human_response']})
        
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
