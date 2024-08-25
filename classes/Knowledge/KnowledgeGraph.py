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

from .prompts.graph import graph_system_prompt, graph_user_prompt
from .prompts.document_summary import document_summary_system_prompt
from .prompts.merge_descriptions import merge_descriptions_entity_system_prompt, merge_descriptions_entity_user_prompt, merge_descriptions_relationship_system_prompt, merge_descriptions_relationship_user_prompt
from .prompts.deduplicate import deduplicate_system_entity_prompt, deduplicate_user_entity_prompt
from .prompts.claim import claim_system_prompt, claim_user_prompt

# Index in Elastic where documents are stored
DOCUMENTS_INDEX = "prod-documents"

class KnowledgeGraph:

    def __init__(self, project_id, documents, report_scope, questionnaire, persona):
        self.project_id = project_id
        self.documents = documents
        self.report_scope = report_scope
        self.questionnaire = questionnaire
        self.persona = persona

        self.token_limit = 600
        self.previous_chunk_limit = self.token_limit * 0.5

        self.ai_handler = AIHandler.load()

        # Initialize global_graph from existing project data
        self.global_graph = self._fetch_existing_graph()
        self.graph_modified = False
        self.global_claims = []

        self.entities_string = self.get_entity_list()

        self.graph_training_index = "prod-graph-training"
        self.claim_training_index = "prod-claim-training"

    def process(self):
        # Preprocess documents
        self._preprocess_documents()

        # Process each document
        for document in self.documents:
            if not self._document_exists(document['document_id']):
                self._process_single_document(document)

        # Deduplicate entities
        self._deduplicate_entities()

        # Merge entity and relationship descriptions
        self._merge_descriptions()

        # Return chunked documents
        return True
    
    def process_claims(self):

        # Process each document
        for document in self.documents:
            if not self._document_exists(document['document_id']):
                self._process_single_document_claims(document)

        return self.global_claims
    
    def return_unique_documents(self):
        unique_documents = []
        for document in self.documents:
            if not self._document_exists(document['document_id']):
                unique_documents.append(document)
        return unique_documents

    def chunk_document(self, document):

        if 'project_id' not in document:
            document['project_id'] = self.project_id

        if 'document_id' not in document:
            document['document_id'] = self._md5_hash(document['markdown_path'])

        if 'document_summary' not in document:
            document['document_summary'] = self._generate_document_summary(document)

        if 'chunks' not in document:
            document['chunks'] = self._chunk_document(document)

        if 'document_metadata' not in document:
            document['document_metadata'] = {"title": "UNKNOWN"}

        return document

    def _document_exists(self,document_id, index_name=DOCUMENTS_INDEX):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"document_id.keyword": document_id}},
                        {"term": {"project_id.keyword": self.project_id}}
                    ]
                }
            },
            "size": 0  # We don't need to retrieve the document, just check if it exists
        }
        
        result = search_es(index_name, query)
        
        # If the total number of hits is greater than 0, the document exists
        return result['hits']['total']['value'] > 0

    def _process_single_document_claims(self, document):

        # Get question categories
        unique_categories = {item["category"] for item in self.questionnaire["questionnaire"]}

        # For each category
        for category in unique_categories:

            # Get questions for category
            questions = self._get_questions_by_category(category)

            # Scroll through each chunk
            for chunk in document['chunks']:
                claims = self._claim_scroll(chunk, self.entities_string, questions, document['document_summary'])

                # Add claims to global claims
                for claim in claims["claims"]:
                    claim['project_id'] = self.project_id
                    claim['category'] = category
                    claim["document_id"] = document['document_id']
                    claim["chunk_id"] = chunk["chunk_id"]
                    claim["document_metadata"] = document['document_metadata']
                    claim["document_summary"] = document['document_summary']
                    self.global_claims.append(claim)
    
    def _fetch_existing_graph(self):
        # Fetch existing graph data from Neo4j for the current project_id
        neo4j_result = fetch_project_graph(self.project_id)
        
        entities = {}
        relationships = []

        for record in neo4j_result:
            source = record['e']
            if source['name'] not in entities:
                entities[source['name']] = {
                    "name": source['name'],
                    "type": source['type'],
                    "description": source['description'],
                    "references": source['references']
                }

            if record['r'] is not None and record['target'] is not None:
                relationships.append({
                    "source": source['name'],
                    "target": record['target']['name'],
                    "description": record['r']['description'],
                    "references": record['r']['references']
                })

        return {
            "entities": list(entities.values()),
            "relationships": relationships
        }
    
    def submit_to_neo4j(self):
        if self.graph_modified:
            add_to_neo4j(self.global_graph, self.project_id)

        # Otherwise, there's nothing to update

    def process_embeddings(self):
        compute_embeddings(graph_name=self.project_id)
    
    def _preprocess_documents(self):

        for document in self.documents:
            if 'project_id' not in document:
                document['project_id'] = self.project_id

            if 'document_id' not in document:
                document['document_id'] = self._md5_hash(document['markdown_path'])

            if 'document_summary' not in document:
                document['document_summary'] = self._generate_document_summary(document)

            if 'chunks' not in document:
                document['chunks'] = self._chunk_document(document)

            if 'document_metadata' not in document:
                document['document_metadata'] = {"title": "UNKNOWN"}

    def _process_single_document(self, document):

        previous_chunk = None

        for chunk in document['chunks']:
            existing_entities = self.get_entity_list()
            local_graph = self._knowledge_scroll(chunk, existing_entities, self.persona, document['document_summary'], previous_chunk)
            self.update_global_graph(local_graph.copy(), chunk['chunk_id'])

            # Get last tokens from previous chunk
            previous_chunk = get_last_n_tokens(chunk['content'], self.previous_chunk_limit)

    def _deduplicate_entities(self):

        # Schema response format
        # """
        # {
        #     "duplicate_entities":
        #     [
        #         {
        #             "the name of entity that best represents the real-world entity": 
        #             [
        #                 "list of entities to merge with",
        #                 ...
        #             ]
        #         }
        #     ]
        # }
        # """

        # Create a copy of the global graph entities
        entities = self.global_graph['entities'].copy()
        relationships = self.global_graph['relationships'].copy()

        # Order the entities in alphabetical order by name key
        entities = sorted(entities, key=lambda x: x['name'])

        # Create a string to inject into the prompt
        entities_string = ""
        for entity in entities:
            entities_string += f"- {entity['name']}: {entity['type']}\n"
            entities_string += f"  {entity['description']}\n\n"

        # Load the system prompt for entity deduplication
        system_prompt = textwrap.dedent(deduplicate_system_entity_prompt).strip()

        # Load the user prompt for entity deduplication
        user_prompt = textwrap.dedent(deduplicate_user_entity_prompt).strip().format(entity_list=entities_string)

        # Submit to AI
        deduplication_mapping = json.loads(self.ai_handler.request_completion(system_prompt, user_prompt, json_output=True))

        # For each entity in the deduplication mapping, rename the entities to the best entity name
        for mapping in deduplication_mapping['duplicate_entities']:
            best_entity_name = list(mapping.keys())[0]
            entities_to_merge = mapping[best_entity_name]

            # Find the best entity in the copied entities
            best_entity = next((e for e in entities if e['name'] == best_entity_name), None)

            # If the best entity is not found, skip
            if not best_entity:
                continue

            # Find the entities to merge in the copied entities
            entities_to_merge = [e for e in entities if e['name'] in entities_to_merge]

            # If the entities to merge are not found, skip
            if not entities_to_merge:
                continue

            # Merge the entities
            for entity in entities_to_merge:
                # Update the references, ensuring no duplicates
                best_entity['references'].extend(entity['references'])
                best_entity['references'] = list(set(best_entity['references']))
                # Update the descriptions array, ensuring no duplicates
                # If the description is a string, convert it to a list
                if isinstance(best_entity['description'], str):
                    best_entity['description'] = [best_entity['description']]
                best_entity['description'].extend(entity['description'])
                best_entity['description'] = list(set(best_entity['description']))

                # Now we must update all the relationships that reference the entity to merge
                for relationship in relationships:
                    if relationship['source'] == entity['name']:
                        relationship['source'] = best_entity_name
                    if relationship['target'] == entity['name']:
                        relationship['target'] = best_entity_name

                # Remove the old entity from the copied entities
                entities.remove(entity)

        # Merge duplicate relationships
        merged_relationships = []
        relationship_dict = {}
        for relationship in relationships:
            key = (relationship['source'], relationship['target'])
            if key in relationship_dict:
                # Merge descriptions if duplicate relationship found
                # If the description is a string, convert it to a list
                if isinstance(relationship_dict[key]['description'], str):
                    relationship_dict[key]['description'] = [relationship_dict[key]['description']]
                relationship_dict[key]['description'].extend(relationship['description'])
                relationship_dict[key]['description'] = list(set(relationship_dict[key]['description']))
            else:
                relationship_dict[key] = relationship

        merged_relationships = list(relationship_dict.values())

        # Replace the global graph entities with the deduplicated entities and relationships
        self.global_graph['entities'] = entities
        self.global_graph['relationships'] = merged_relationships

    def _merge_descriptions(self):

        # Create a copy of the global graph
        graph = self.global_graph.copy()

        # Load the system prompts for entity and relationship merging
        entity_system_prompt = textwrap.dedent(merge_descriptions_entity_system_prompt).strip()
        relationship_system_prompt = textwrap.dedent(merge_descriptions_relationship_system_prompt).strip()

        # Merge entity descriptions
        for entity in graph["entities"]:

            # If there is only one description, set it as the description string
            if len(entity["description"]) == 1:
                entity["description"] = entity["description"][0]
                continue

            else:
                # This is a candidate for AI to merge descriptions
                tmp_entity = {}
                tmp_entity["name"] = entity["name"]
                tmp_entity["type"] = entity["type"]
                tmp_entity["description"] = entity["description"]
                # Load the user prompt
                prompt = textwrap.dedent(merge_descriptions_entity_user_prompt).strip().format(entity=json.dumps(tmp_entity, indent=4))
                # Submit to AI
                new_entity = json.loads(self.ai_handler.request_completion(entity_system_prompt, prompt, json_output=True))
                # Update the entity with the new description
                entity["description"] = new_entity["description"]

        # Merge relationship descriptions
        for relationship in graph["relationships"]:

            # If there is only one description, set it as the description string
            if len(relationship["description"]) == 1:
                relationship["description"] = relationship["description"][0]
                continue

            else:
                # This is a candidate for AI to merge descriptions
                tmp_relationship = {}
                tmp_relationship["source"] = relationship["source"]
                tmp_relationship["target"] = relationship["target"]
                tmp_relationship["description"] = relationship["description"]
                # Load the user prompt
                prompt = textwrap.dedent(merge_descriptions_relationship_user_prompt).strip().format(relationship=json.dumps(tmp_relationship, indent=4))
                # Submit to AI
                new_relationship = json.loads(self.ai_handler.request_completion(relationship_system_prompt, prompt, json_output=True))
                # Update the relationship with the new description
                relationship["description"] = new_relationship["description"]

        # Update the global graph with the merged descriptions
        self.global_graph = graph


    def _generate_document_summary(self, document):
        
        # In UTF
        with open(document['markdown_path'], "r", encoding="utf-8") as file:
            document_text = file.read()

        system_prompt = textwrap.dedent(document_summary_system_prompt).strip().replace("{metadata}", json.dumps(document['document_metadata'], indent=4)).replace("{scope}", self.report_scope)

        summary = json.loads(self.ai_handler.recursive_summary(system_prompt, document_text, json_output=True))
        return summary

    def _chunk_document(self, document):
        chunks = []
        with open(document['markdown_path'], "r", encoding="utf-8") as file:
            document_text = file.read()

        for i, chunk in enumerate(chunk_large_text(document_text, self.token_limit)):
            chunk_id = hashlib.md5(chunk["content"].encode()).hexdigest()
            chunks.append({
                "project_id": self.project_id,
                "chunk_id": chunk_id,
                "document_id": document['document_id'],
                "document_summary": document['document_summary'],
                "document_metadata": document['document_metadata'],
                "chunk_index": i,
                "content": chunk["content"],
            })

        return chunks
    
    def update_global_graph(self, new_graph: Dict[str, List], chunk_id: str):

        # Update entities
        for new_entity in new_graph["entities"]:
            existing_entity = next((e for e in self.global_graph["entities"] if e["name"] == new_entity["name"] and e["type"] == new_entity["type"]), None)
            if existing_entity:
                if isinstance(existing_entity["description"], str):
                    existing_entity["description"] = [existing_entity["description"]]
                existing_entity["description"].append(new_entity["description"])
                existing_entity.setdefault("references", []).append(chunk_id)
            else:
                new_entity["description"] = [new_entity["description"]]
                new_entity["references"] = [chunk_id]
                self.global_graph["entities"].append(new_entity)
                if self.graph_modified is False:
                    self.graph_modified = True  # Set flag when new relationship is added

        # Update relationships
        for new_rel in new_graph["relationships"]:
            existing_rel = next((r for r in self.global_graph["relationships"] if r["source"] == new_rel["source"] and r["target"] == new_rel["target"]), None)
            if existing_rel:
                if isinstance(existing_rel["description"], str):
                    existing_rel["description"] = [existing_rel["description"]]
                existing_rel["description"].append(new_rel["description"])
                existing_rel.setdefault("references", []).append(chunk_id)
            else:
                new_rel["description"] = [new_rel["description"]]
                new_rel["references"] = [chunk_id]
                self.global_graph["relationships"].append(new_rel)
                if self.graph_modified is False:
                    self.graph_modified = True  # Set flag when new relationship is added

    def get_entity_list(self):
        entities = self.global_graph.get("entities", [])
        
        if not entities:
            return "No identified entities yet."
        
        entity_list = []
        for entity in entities:
            entity_list.append(f"* {entity['name']}: {entity['type']}")
        
        return "\n".join(entity_list)


    def _knowledge_scroll(self, chunk, existing_entities=None, persona=None, document_summary=None, previous_chunk=None):
        output_format = {
            "entities": [
                {"name": "EntityName", "type": "EntityType", "description": "Comprehensive description of the entity's attributes and activities"},
            ],
            "relationships": [
                {"source": "name of the source entity", "target": "name of the target entity", "description": "Explanation as to why you think the source entity and the target entity are related to each other"},
            ],
        }

        system_prompt = textwrap.dedent(graph_system_prompt).strip().format(output_format=json.dumps(output_format, indent=4))

        user_prompt = self._get_user_prompt(
            chunk['content'], 
            existing_entities, 
            persona, 
            json.dumps(document_summary, indent=4), 
            previous_chunk=previous_chunk
        )

        entities = self.ai_handler.request_completion(system_prompt, user_prompt, json_output=True)

        # Store data for training
        training_data = {
            "project_id": self.project_id,
            "chunk_id": chunk['chunk_id'],
            "document_id": chunk['document_id'],
            "chunk_index": chunk['chunk_index'],
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "generated_response": entities,
        }

        add_to_es(self.graph_training_index, training_data)

        return json.loads(entities)
    
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
    
    def _claim_scroll(self, chunk, entities, questions, document_summary=None):

        system_prompt = textwrap.dedent(claim_system_prompt).strip()

        user_prompt = textwrap.dedent(claim_user_prompt).strip().format(
            metadata=json.dumps(document_summary, indent=4),
            questions=questions,
            entities=entities,
            text=chunk['content']
        )

        try:
            claims = self.ai_handler.request_completion(system_prompt, user_prompt, json_output=True)

            # Store data for training
            training_data = {
                "project_id": self.project_id,
                "chunk_id": chunk['chunk_id'],
                "document_id": chunk['document_id'],
                "chunk_index": chunk['chunk_index'],
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "generated_response": claims,
            }

            add_to_es(self.claim_training_index, training_data)          

            return json.loads(claims)
        except json.decoder.JSONDecodeError:
            return {"claims": []}
    
    def _md5_hash(self, file_path):
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    def _get_user_prompt(self, chunk, entities_list, persona, document_summary, previous_chunk=None):

        header = ""
        if previous_chunk:
            header = f"## Previous Chunk\n\n{previous_chunk}\n\n----\n\n"

            instruction = textwrap.dedent("""
                I have provided you with a chunk of text to review, a previous chunk for added context, and a list of existing entities. Your task is to analyze the chunk of text and identify any entities or relationships within it.
            """)
        else:
            instruction = textwrap.dedent("""
                I have provided you with a chunk of text to review, and a list of existing entities. Your task is to analyze the chunk of text and respond with a list of entities or relationships.
            """)

        return textwrap.dedent(graph_user_prompt).strip().format(
                chunk=chunk, 
                entities_list=entities_list, 
                header=header, 
                instruction=instruction, 
                persona=persona, 
                document_summary=document_summary
            )
    
