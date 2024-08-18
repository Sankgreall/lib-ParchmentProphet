import os
import json
import json
from typing import List, Dict, Any
import textwrap
import hashlib
import yaml
from collections import OrderedDict


# Import text functions
try:
    # Try relative imports for deployment
    from ....modules.text import *
    from ....modules.markdown import *
    from ....ai_handler import AIHandler
except ImportError:
    try:
        # Fallback to absolute imports with project name for structured imports
        from ParchmentProphet.modules.text import *
        from ParchmentProphet.modules.markdown import *
        from ParchmentProphet.classes.ai_handler import AIHandler
    except ImportError:
        # Fallback to simple absolute imports for local testing
        from modules.text import *
        from modules.markdown import *
        from classes.ai_handler import AIHandler

from .prompts.schema import schema_system_general, schema_user_general, schema_user_specalised, schema_system_specalised 

class KnowledgeSchema:

    def __init__(self, questionnaire):

        # Load the questionnaire
        self.questionnaire = questionnaire
        self.formatted_questionnaire = self._create_string_questionnaire().strip()

        # Create variables to hold Graph schemas
        self.global_schema = {}
        self.specialised_schemas = {}

        self.graph_entries = []
        self.document_chunks = []

        # Set the chunk token limit
        self.token_limit = 4096

        # Intiate the AI handler
        self.ai_handler = AIHandler.load()

    def process(self):
        self._create_entity_graph_schema()

        unique_categories = {item["category"] for item in self.questionnaire["questionnaire"]}
        for category in unique_categories:
            self._create_specalised_graph_schema(category)

        all_schemas = {
            "global": self.global_schema,
            **{category: schema for category, schema in self.specialised_schemas.items()}
        }

        return all_schemas
           
    def _create_entity_graph_schema(self):

        system_prompt = textwrap.dedent(schema_system_general).strip().format(schema_format=self._get_graph_schema_format())

        user_prompt = textwrap.dedent(schema_user_general).strip().format(questionnaire=self.formatted_questionnaire)

        self.global_schema = json.loads(self.ai_handler.request_completion(system_prompt, user_prompt, json_output=True))
    
    def _create_specalised_graph_schema(self, category):

        system_prompt = textwrap.dedent(schema_system_specalised).strip().format(schema_format=self._get_graph_schema_format())

        user_prompt = textwrap.dedent(schema_user_specalised).strip().format(global_schema=self.global_schema, questions=self._get_questions_by_category(category))

        self.specialised_schemas[category] = json.loads(self.ai_handler.request_completion(system_prompt, user_prompt, json_output=True))


    def _get_graph_schema_format(self):

        # Define the output format for the entity graph schema using a regular dictionary
        graph_format = {
            "entities": [
                {
                    "type": "EntityType",
                    "description": "Brief description of what the entity represents",
                }
            ]
        }
        
        # Convert the OrderedDict to a YAML string with proper indentation
        return json.dumps(graph_format, indent=2)
    
    def _create_string_questionnaire(self):

        # Create a dictionary to hold categories and their questions
        category_dict = {}

        # Populate the dictionary with categories and associated questions
        for item in self.questionnaire["questionnaire"]:
            category = item["category"]
            question = item["question"]
            if category not in category_dict:
                category_dict[category] = []
            category_dict[category].append(question)

        # Create the formatted string
        formatted_string = ""
        for category, questions in category_dict.items():
            formatted_string += f"## Category: {category}\n\n"
            for question in questions:
                formatted_string += f"- {question}\n"
            formatted_string += "\n"

        return formatted_string
    
    def _get_questions_by_category(self, target_category):
        # Filter questions based on the category
        questions = [
            item["question"]
            for item in self.questionnaire["questionnaire"]
            if item["category"] == target_category
        ]
        
        # Format the questions as a bullet list
        bullet_list = "\n".join(f"- {question}" for question in questions)
        
        return bullet_list