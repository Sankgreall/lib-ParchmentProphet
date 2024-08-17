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
    from .ai_handler import AIHandler
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

    def __init__(self, document_path, document_summary, document_metadata, report_scope, questionnaire, data_schema):

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
        self.global_schema = data_schema['global']
        del data_schema['global']
        self.specialised_schemas = data_schema

        self.graph_entries = []
        self.document_chunks = []

        # Set the chunk token limit
        self.token_limit = 4096
        self.previous_chunk_limit = 1024

        # Intiate the AI handler
        self.ai_handler = AIHandler.load()

    def process(self):

        # Chunk the document
        self._chunk()

        for chunk in self.document_chunks:

            # Populate the global schema first
            graph = self._knowledge_scroll(self.global_schema, chunk, report_scope=self.report_scope)
            chunk['graph']['entities'].extend(graph['entities'])
            chunk['graph']['relationships'].extend(graph['relationships'])

        for category, schema in self.specialised_schemas.items():

            questions = self._get_questions_by_category(category)

            # We want to combine the global schema with the specialised schema
            combined_schema = f"{self.global_schema}\n{schema}"

            previous_chunk = None
            for chunk in self.document_chunks:

                graph = self._knowledge_scroll(combined_schema, chunk, questions, previous_chunk=previous_chunk, report_scope=self.report_scope)
                chunk['graph']['entities'].extend(graph['entities'])
                chunk['graph']['relationships'].extend(graph['relationships'])

                previous_chunk = get_last_n_tokens(chunk['content'], self.previous_chunk_limit)

        return self.document_chunks
           
    def _retrieve_entity_list(self):

        entity_list = []
        
        for chunk in self.document_chunks:
            for entity in chunk['graph']['entities']:
                entity_type = entity.get('type', 'Unknown')
                entity_name = entity.get('name', 'Unnamed')
                entity_list.append(f"- {entity_type}: {entity_name}")
        
        if not entity_list:
            return "No identified entities"
        else:
            return "\n".join(entity_list)


    def _knowledge_scroll(self, schema, chunk, questions=None, previous_chunk=None, report_scope=None):

        output_format = {
            "entities": [
                {"name": "Entity1", "type": "type", "properties": {"property1": "value1"}},
            ],
            "relationships": [
                {"source": "Entity1", "target": "Entity2", "type": "type"},
            ],
        }

        questions_string = ""
        if questions:
            questions_string = f"\n\nIn particular, you must focus your schema on the following questions:\n\n{questions}"

        system_prompt = textwrap.dedent("""
            You are an AI assistant specialized in extracting structured information from text to populate a graph database. Your task is to analyze provided text and identify relevant entities and relationships based on a given schema. Adhere strictly to the schema and instructions provided in the user message.{questions_string}
                                        
            Output your findings in the following JSON format, without any additional commentary or formatting:

            {output_format} 
        """).strip().format(output_format=json.dumps(output_format, indent=4), questions_string=questions_string)

        entities_list = self._retrieve_entity_list()
        user_prompt = self._get_user_prompt(chunk['content'], schema, entities_list, self.report_scope, self.document_summary, previous_chunk=previous_chunk)

        return json.loads(self.ai_handler.request_completion(system_prompt, user_prompt, json_output=True))

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
            chunk["graph"] = {"entities": [], "relationships": []}
            i += 1
            self.document_chunks.append(chunk)

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
    
    def _get_user_prompt(self, chunk, schema, entities_list, report_scope, document_summary, previous_chunk=None):

        header = ""
        if previous_chunk:
            header = f"## Previous Chunk\n\n{previous_chunk}\n\n----\n\n"

            instruction = textwrap.dedent("""
                I have provided you with a chunk of text to review, a previous chunk for added context, a graph schema, and a list of existing entities. Your task is to analyze the chunk of text and identify any entities or relationships within it, in strict accordance with the provided schema.
            """)
        else:
            instruction = textwrap.dedent("""
                I have provided you with a chunk of text to review, a graph schema, and a list of existing entities. Your task is to analyze the chunk of text and respond with a list of entities or relationships, in strict accordance with the provided schema.
            """)

        return textwrap.dedent("""
            {header}                              
            # Chunk to review
                                        
            {chunk}
                                        
            ----

            # Graph Schema

            {schema}

            ----

            # Existing Graph Entities

            {entities_list}

            ----
                               
            # Report Scope
                               
            {report_scope}
                               
            ## Document summary
                               
            {document_summary}
                               
            ----
                                        
            {instruction}

            # Instructions

            - Carefully read and analyze the text within your chunk.
                               
            - Carefully review the report scope and the document summary (from where your chunk was extracted). Ensure that your entities and relationships are aligned with the intended focus of the analysis.
                               
            - Identify entities within the chunk that match the entity schema, and clearly state them even if they are already present within the list of existing graph entities.

            - Determine relationships between the identified entities based on the relationship type schema. Use the list of existing graph entities to help you create relationships even if an entity is not explicitly mentioned in the current chunk.
                               
            - Do not fail to identify entities that are present in the text. Err on the side of caution and include entities if you are unsure.

            If you encounter any ambiguities or uncertainties, note them briefly in a separate "comments" field in the JSON output.

            Now, analyze your chunk and extract all entities and relationships according to the instructions.
        """).strip().format(
                chunk=chunk, 
                schema=schema, 
                entities_list=entities_list, 
                header=header, 
                instruction=instruction, 
                report_scope=report_scope, 
                document_summary=document_summary
            )
    