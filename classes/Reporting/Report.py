import os
import json
import json
from typing import List, Dict, Any
import hashlib
import yaml
from collections import OrderedDict
import re
import textwrap
from datetime import datetime, timezone

# Import text functions
try:
    # Try relative imports for deployment
    from ....modules.text import *
    from ....modules.markdown import *
    from ....ai_handler import AIHandler
    from ....modules.elastic import *
    from ....modules.neo4j import *
    from ..Knowledge.KnowledgeQuery import KnowledgeQuery
except ImportError:
    try:
        # Fallback to absolute imports with project name for structured imports
        from ParchmentProphet.modules.text import *
        from ParchmentProphet.modules.markdown import *
        from ParchmentProphet.classes.ai_handler import AIHandler
        from ParchmentProphet.modules.elastic import *
        from ParchmentProphet.modules.neo4j import *
        from ParchmentProphet.classes.Knowledge.KnowledgeQuery import KnowledgeQuery
    except ImportError:
        # Fallback to simple absolute imports for local testing
        from modules.text import *
        from modules.markdown import *
        from classes.ai_handler import AIHandler
        from modules.neo4j import *
        from modules.elastic import *
        from classes.Knowledge.KnowledgeQuery import KnowledgeQuery

from .prompts.report_generation import report_generation_system_prompt, report_generation_first_user_prompt, report_generation_subsequent_user_prompt

class Report:

    PROJECT_INDEX = "prod-projects"
    QUESTIONNAIRE_INDEX = "prod-questionnaires"
    REPORT_TEMPLATE_INDEX = "prod-report-templates"
    CLAIMS_INDEX = "prod-claims"
    ANSWER_INDEX = "prod-answers"

    def __init__(self, project_id):
        self.project_id = project_id
        self.ai = AIHandler.load()
        self.project = self.get_project()
        self.questionnaire = self.get_questionnaire()
        self.report_template = self.get_report_template()
        self.claims = self.get_claims()
        self.answers = self.get_answers()
        
    def generate_report(self):
        if not self.questionnaire:
            raise ValueError(f"No questionnaire found for questionnaire ID: {self.project.get('questionnaire_id')}")

        if not self.report_template:
            raise ValueError(f"No report template found for report ID: {self.project.get('report_id')}")

        if not self.claims:
            raise ValueError(f"No claims found for project ID: {self.project_id}")

        report_scope = self.report_template.get("report_scope")
        report_persona = self.report_template.get("report_persona")

        if not self.check_if_answers_exist():
            self.generate_answers()

        system_prompt = textwrap.dedent(report_generation_system_prompt).strip().format(persona=report_persona)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        drafted_sections = []
        delayed_section = None
        delayed_section_index = None

        # Find the first non-delayed section
        first_section_index = next((i for i, section in enumerate(self.report_template["sections"]) 
                                    if not section.get("generate_last", False)), None)

        if first_section_index is None:
            raise ValueError("All sections are marked as generate_last. At least one section must not be delayed.")

        # Add the first user prompt for the first non-delayed section
        first_section = self.report_template["sections"][first_section_index]
        messages.append({
            "role": "user", 
            "content": textwrap.dedent(report_generation_first_user_prompt).strip().format(
                answers=self.format_answers(self.answers),
                report_scope=report_scope,
                example=first_section["example"],
                section_brief=first_section["prompt"]
            )
        })

        for i, section in enumerate(self.report_template["sections"]):
            if section.get("generate_last", False):
                delayed_section = section
                delayed_section_index = i
                continue

            if i != first_section_index:
                # Add the subsequent user prompt for non-first sections
                messages.append({
                    "role": "user", 
                    "content": textwrap.dedent(report_generation_subsequent_user_prompt).strip().format(
                        example=section["example"],
                        section_brief=section["prompt"]
                    )
                })

            # Generate the section
            response = self.ai.request_completion(messages=messages)
            
            # Add the generated section to drafted_sections
            drafted_sections.append({
                "title": section["title"],
                "content": response
            })

            # Add the AI's response to the messages
            messages.append({"role": "assistant", "content": response})

        # Generate the delayed section (if any)
        if delayed_section:
            messages.append({
                "role": "user",
                "content": textwrap.dedent(report_generation_subsequent_user_prompt).strip().format(
                    example=delayed_section["example"],
                    section_brief=delayed_section["prompt"]
                )
            })
            response = self.ai.request_completion(messages=messages)
            
            # Insert the delayed section at its original position
            drafted_sections.insert(delayed_section_index, {
                "title": delayed_section["title"],
                "content": response
            })

        return drafted_sections
    
    def get_project(self):
        query = {
            "query": {
                "match": {
                    "project_id": self.project_id
                }
            }
        }
        result = search_es(self.PROJECT_INDEX, query)
        if result["hits"]["total"]["value"] > 0:
            project = result["hits"]["hits"][0]["_source"]
            project["_id"] = result["hits"]["hits"][0]["_id"]
            return project
        return None

    def get_questionnaire(self):
        questionnaire_id = self.project.get("questionnaire_id")
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"_id": questionnaire_id}}
                    ]
                }
            }
        }
        results = search_es(self.QUESTIONNAIRE_INDEX, query)
        if results["hits"]["total"]["value"] > 0:
            return results["hits"]["hits"][0]["_source"]
        else:
            return None

    def get_report_template(self):
        report_id = self.project.get("report_id")
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"_id": report_id}}
                    ]
                }
            }
        }
        results = search_es(self.REPORT_TEMPLATE_INDEX, query)
        if results["hits"]["total"]["value"] > 0:
            return results["hits"]["hits"][0]["_source"]
        else:
            return None

    def get_claims(self):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"project_id": self.project_id}}
                    ]
                }
            },
            "size": 10000
        }
        results = search_es(self.CLAIMS_INDEX, query)
        return [hit["_source"] for hit in results["hits"]["hits"]]

    def get_answers(self):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"project_id": self.project_id}}
                    ]
                }
            }
        }
        results = search_es(self.ANSWER_INDEX, query)
        return [hit["_source"] for hit in results["hits"]["hits"]]

    @staticmethod
    def format_answers(answers):
        formatted_qa = []
        for item in answers:
            formatted_qa.append(f"Question: {item['question']}\nAnswer: {Report.strip_references(item['answer'])}")
        return "\n\n".join(formatted_qa)

    @staticmethod
    def strip_references(text):
        text = re.sub(r'\[\d+\]', '', text)
        text = re.sub(r'\n\n\[\d+\].*', '', text, flags=re.DOTALL)
        text = ' '.join(text.split())
        return text.strip()

    def report_section(self, section, persona, scope):
        system_prompt = textwrap.dedent(report_generation_system_prompt).strip().format(persona=persona)
        user_prompt = textwrap.dedent(report_generation_first_user_prompt).strip().format(
            answers=self.format_answers(self.answers), 
            report_scope=scope, 
            example=section["example"], 
            section_brief=section["prompt"]
        )

        response = self.ai.request_completion(system_prompt, user_prompt)
        return f"# {section['title']}\n{response}\n\n"

    def check_if_answers_exist(self):
        query = {
            "query": {
                "term": {
                    "project_id.keyword": self.project_id
                }
            },
            "size": 1 
        }
        result = search_es(self.ANSWER_INDEX, query)
        return result["hits"]["total"]["value"] > 0

    def generate_answers(self):
        query_engine = KnowledgeQuery()
        answers = query_engine.answer_questions_from_claims(self.questionnaire, self.claims)

        formatted_answers = []
        for question, answer in answers.items():
            doc = {
                "created": datetime.now(timezone.utc),
                "last_modified": datetime.now(timezone.utc),
                "project_id": self.project_id,
                "question": question,
                "answer": answer
            }
            formatted_answers.append(doc)
            add_to_es(self.ANSWER_INDEX, doc)

        self.answers = formatted_answers


