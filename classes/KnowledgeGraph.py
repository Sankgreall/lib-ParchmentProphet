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
    from ..modules.text import *
    from ..modules.markdown import *
    from ..classes.ai_handler import AIHandler
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

class KnowledgeGraph:

    def __init__(self, document_path, document_summary, document_metadata, report_scope, questionnaire):

        # Set the document path, ID, summary, and metadata
        self.document_path = document_path
        self.document_id = self._md5_hash()
        self.document_summary = document_summary
        self.document_metadata = document_metadata

        # Add summary to metadata
        self.document_metadata["document_summary"] = self.document_summary
        
        # Load the report scope and questionnaire
        self.report_scope = report_scope
        self.questionnaire = questionnaire
        self.formatted_questionnaire = self._create_string_questionnaire().strip()

        # Create variables to hold Graph schemas
        self.global_schema = ""
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

        all_schemas = {}
        all_schemas["global"] = self.global_schema
        all_schemas.update(self.specialised_schemas)
        
        return all_schemas
           
    def _retrieve_graph(self):

        # Initialize sets to store unique entities and relationships
        unique_entities = set()
        unique_relationships = set()

        # Loop through each item in the data array
        for item in self.graph_entries:
            for entity in item["entities"]:
                unique_entities.add((entity["name"], entity["type"]))
            for relationship in item["relationships"]:
                unique_relationships.add((relationship["source"], relationship["target"], relationship["type"]))

        # Convert sets back to lists of dictionaries
        merged_data = {
            "entities": [{"name": name, "type": entity_type} for name, entity_type in unique_entities],
            "relationships": [{"source": source, "target": target, "type": relationship_type} for source, target, relationship_type in unique_relationships]
        }

        return merged_data

    def _create_entity_graph_schema(self):

        system_prompt = textwrap.dedent("""
            You are an AI assistant specialized in designing graph database schemas. Your task is to create a comprehensive and flexible schema based on a set of questions grouped by categories. Follow these steps carefully.

            1. Identify the type of target entity and create a generic top-level structure. The target entity should be an Organization, Person, Product, Event, Market, Asset, Project, or Location.
                                        
            2. Define entities and relationships common across all categories.
                                        
            3. Focus on versatility and broad applicability.
                                        
            4. Do not address any specific knowledge areas at this stage.
                                        
            5. Avoid entity types that contain Personally Identifiable Information ('PII')

            Use the following format for your schema:

            ```
            {schema_format}
            ```

            After completing the generic structure, wait for further instructions to create specialized knowledge sub-graphs.

            Your responses must only include your schema, without embellishment, commentary, or markdown styling.
        """).strip().format(schema_format=self._get_graph_schema_format())


        user_prompt = textwrap.dedent("""
            # Questions
                                      
            {questionnaire}
            
            ----
            
            I have provided you with a list of questions above, where each question is grouped by a category. This category directly represents the type of specialized knowledge required to answer the question.

            Your task is to design a Graph schema based on these questions. The schema will consist of two parts:
                                      
            - A generic top-level structure for the target entity, storing information relevant to all specialized knowledge areas defined by the question categories.

            - For each specialized knowledge area, a sub-graph curated to store the information asked by these questions.

            To begin, focus only on the first part: the generic top-level structure. Do not create a schema that addresses any specific knowledge areas. Create only nodes that are common across all categories of questions.

            After you complete this first part, I will ask you to generate the specialized knowledge sub-graphs.
                                      
            Provide your response using the format specified in the system message. Prefer entities and relationships over excessive properties.
        """).strip().format(questionnaire=self.formatted_questionnaire)

        self.global_schema = self.ai_handler.request_completion(system_prompt, user_prompt)
    
    def _create_specalised_graph_schema(self, category):

        system_prompt = textwrap.dedent("""
            You are an AI assistant specialized in designing graph database schemas. Your task is to create a specalised schema designed to answer a niche area, whilst ensuring it remains connected to a pre-defined global schema. Follow these steps carefully.

            1. Review the input questions and develop a specalised schema.
                                        
            2. Define entities and relationships common across your questions.
                                        
            3. Ensure, where applicable, that the specalised schema is related back to the global schema.
                                        
            4. Do not re-define entities or relationships that are already defined in the global schema. Only add new types.
                                                                                
            5. Avoid entity types that contain Personally Identifiable Information ('PII')

            Use the following format for your schema:

            ```
            {schema_format}
            ```

            Your responses must only include your schema, without embellishment, commentary, or markdown styling.
        """).strip().format(schema_format=self._get_graph_schema_format())

        user_prompt = textwrap.dedent("""
            # Global Schema
                                      
            {global_schema}
                                      
            # Questions
                                      
            {questions}
            
            ----
            
            I have provided you with a list of questions above, where each question is grouped by a category. This category directly represents the type of specialized knowledge required to answer the question.

            Your task is to design a Graph schema based on these questions. The schema will consist of two parts:
                                      
            - A generic top-level structure for the target entity, storing information relevant to all specialized knowledge areas defined by the question categories.
            - For each specialized knowledge area, a sub-graph curated to store the information asked by these questions.

            To begin, focus only on the first part: the generic top-level structure. Do not create a schema that addresses any specific knowledge areas. Create only nodes that are common across all categories of questions.

            After you complete this first part, I will ask you to generate the specialized knowledge sub-graphs.
                                      
            Provide your response using the format specified in the system message. Prefer entities and relationships over excessive properties.
        """).strip().format(global_schema=self.global_schema, questions=self._get_questions_by_category(category))

        self.specialised_schemas[category] = self.ai_handler.request_completion(system_prompt, user_prompt)


    def _get_graph_schema_format(self):

        # Define the output format for the entity graph schema using a regular dictionary
        graph_format = {
            "entities": [
                {
                    "type": "EntityName",
                    "description": "Brief description of the entity",
                    "properties": [
                        {
                            "name": "property_name",
                            "type": "data_type",
                            "required": "true/false"
                        }
                    ]
                }
            ],
            "relationships": [
                {
                    "type": "relationship_name",
                    "description": "Brief description of the relationship",
                    "from": "SourceEntityName",
                    "to": "TargetEntityName"
                }
            ]
        }
        
        # Convert the OrderedDict to a YAML string with proper indentation
        return yaml.dump(graph_format, default_flow_style=False, sort_keys=False, indent=4)

    def _knowledge_scroll(self, schema, chunk, global_context=None):

        output_format = {
            "entities": [
                {"name": "Entity1", "type": "type", "properties": {"property1": "value1"}},
            ],
            "relationships": [
                {"source": "Entity1", "target": "Entity2", "type": "type"},
            ],
        }

        system_prompt = textwrap.dedent("""
            You are an AI assistant specialized in extracting structured information from text to populate a graph database. Your task is to analyze provided text and identify relevant entities and relationships based on a given schema. Adhere strictly to the schema and instructions provided in the user message.
                                        
            Output your findings in the following JSON format, without any additional commentary or formatting:

            {output_format} 
        """).strip().format(output_format=json.dumps(output_format, indent=4))

        global_context_string = ""
        if global_context:
            global_context_string = f"# Global context\n\n{json.dumps(global_context, indent=4)}\n\n----\n\n"

        user_prompt = textwrap.dedent("""{global_context}                                     
            # Chunk to review
                                      
            {chunk}
                                      
            ----
                                      
            I have provided you with a chunk of text (above) and a schema for entities and relationships (below). Analyze the text and extract information according to this schema to help populate a graph database.

            # Schema

            {schema}

            # Instructions

            - Carefully read and analyze the provided text.
            - Identify entities that fall into the specified types.
            - Determine relationships between the identified entities based on the given relationship types.
            - Include only entities and relationships that are explicitly mentioned or strongly implied in the text.
            - If a global context is provided, ensure that you do not duplicate information. Connect new entities and relationships to the existing context.
            - For longer texts, prioritize the most significant and clearly defined entities and relationships.

            If you encounter any ambiguities or uncertainties, note them briefly in a separate "comments" field in the JSON output.

            Now, analyze the following text and extract entities and relationships according to the schema and instructions.
        """).strip().format(chunk=chunk['content'], schema=schema, global_context=global_context_string)

        self.graph_entries.append(json.loads(self.ai_handler.request_completion(system_prompt, user_prompt, json_output=True)))

    def _chunk(self):

        # Load file
        with open(self.document_path, "r") as file:
            document_text = file.read()

        # Chunk the document into sections
        i = 0
        for chunk in chunk_large_text(document_text, self.token_limit):

            # hash the chunk
            chunk_id = hashlib.md5(chunk["content"].encode()).hexdigest()

            # Add additional data to the chunk
            chunk["chunk_id"] = chunk_id
            chunk["document_id"] = self.document_id
            chunk["chunk_index"] = i
            chunk["metadata"] = self.document_metadata
            i += 1
            self.document_chunks.append(chunk)



    def _summarise_document(self):
        pass

    def _md5_hash(self):
        # Create an MD5 hash object
        md5_hash = hashlib.md5()
        
        # Open the file in binary mode and read in chunks
        with open(self.document_path, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                md5_hash.update(chunk)
        
        # Return the hexadecimal representation of the hash
        return md5_hash.hexdigest()
    
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