import os
import json
import json
from typing import List, Dict, Any
import textwrap

# Import text functions
try:
    # Try relative imports for deployment
    from ..modules.text import *
    from ..modules.markdown import *
except ImportError:
    try:
        # Fallback to absolute imports with project name for structured imports
        from ParchmentProphet.modules.text import *
        from ParchmentProphet.modules.markdown import *
    except ImportError:
        # Fallback to simple absolute imports for local testing
        from modules.text import *
        from modules.markdown import *

class QuestionnaireCompletion:

    def __init__(self, ai_handler, max_context_tokens: int, max_output_tokens: int):
        """
        Initialize the QuestionnaireCompletion class.

        Args:
            ai_handler (AIHandler): An instance of a class implementing the AIHandler interface.
            max_context_tokens (int): Maximum number of context tokens allowed.
            max_output_tokens (int): Maximum number of output tokens allowed.
        """
        self.ai_handler = ai_handler
        self.max_context_tokens = ai_handler.get_max_context_tokens()
        self.max_output_tokens = ai_handler.get_max_output_tokens()

    def complete_questionnaire(self, system_prompt: str, prompt_path: str, questionnaire: Dict[str, Any], input_files: List[str]) -> Dict[str, Any]:
        """
        Complete a questionnaire by analyzing input files and generating answers using AI.

        Args:
            system_prompt (str): The system prompt for the AI model.
            prompt_path (str): Path to the prompt template file.
            questionnaire (Dict[str, Any]): The questionnaire object containing questions and metadata.
            input_files (List[str]): List of input file paths to analyze.

        Returns:
            Dict[str, Any]: The completed questionnaire with answers and input data.
        """
        for question in questionnaire["questionnaire"]:
            question["answer"], question["input"] = self._process_question(
                system_prompt, prompt_path, question, questionnaire["questionnaire"], input_files
            )

        return questionnaire

    def _process_question(self, system_prompt: str, prompt_path: str, question: Dict[str, Any], 
                          all_questions: List[Dict[str, Any]], input_files: List[str]) -> tuple[Any, str]:
        """
        Process a single question by analyzing input files and generating an answer.

        Args:
            system_prompt (str): The system prompt for the AI model.
            prompt_path (str): Path to the prompt template file.
            question (Dict[str, Any]): The current question being processed.
            all_questions (List[Dict[str, Any]]): All questions in the questionnaire.
            input_files (List[str]): List of input file paths to analyze.

        Returns:
            tuple[Any, str]: A tuple containing the answer object and the composite input document.
        """
        similar_answers = self._get_similar_answers(question, all_questions)
        composite_document = self._create_composite_document(question, input_files)
        
        # Prepare the final prompt with the composite document and similar answers
        final_prompt = load_prompt(prompt_path, {
            "question": question["question"],
            "response_format": json.dumps(question["response_format"]),
            "similar_answers": json.dumps(similar_answers),
            "composite_document": composite_document
        })

        # Generate the final answer using the AI handler
        response = self.ai_handler.request_completion(
            system_prompt=system_prompt,
            prompt=final_prompt,
            max_tokens=self.max_output_tokens,
        )
        answer = json.loads(response)

        return answer, composite_document

    def _get_similar_answers(self, current_question: Dict[str, Any], all_questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Retrieve answers from questions with matching categories.

        Args:
            current_question (Dict[str, Any]): The current question being processed.
            all_questions (List[Dict[str, Any]]): All questions in the questionnaire.

        Returns:
            List[Dict[str, Any]]: A list of similar questions with their answers.
        """
        return [
            {"question": q["question"], "answer": q["answer"]}
            for q in all_questions
            if q["category"] == current_question["category"] and q["answer"]
        ]

    def _create_composite_document(self, question: Dict[str, Any], input_files: List[str]) -> str:
        """
        Create a composite document containing all relevant strings for answering the question.

        Args:
            question (Dict[str, Any]): The current question being processed.
            input_files (List[str]): List of input file paths to analyze.

        Returns:
            str: A composite document containing relevant information for answering the question.
        """
        composite_document = ""

        for input_file in input_files:
            with open(input_file, 'r', encoding='utf-8') as file:
                data = file.read()

            # Check if data exceeds token limit and chunk if necessary
            if self._exceeds_token_limit(data):
                for chunk in self._chunk_data(data):
                    relevant_content = self._extract_relevant_content(question, chunk)
                    composite_document += f"\n{relevant_content}"
            else:
                relevant_content = self._extract_relevant_content(question, data)
                composite_document += relevant_content

        return composite_document

    def _exceeds_token_limit(self, data: str) -> bool:
        """
        Check if the data exceeds the token limit.

        Args:
            data (str): The input data to check.

        Returns:
            bool: True if the data exceeds the token limit, False otherwise.
        """
        return count_tokens(data) > self.max_context_tokens

    def _chunk_data(self, data: str) -> List[str]:
        """
        Chunk the input data into smaller pieces.

        Args:
            data (str): The input data to chunk.

        Returns:
            List[str]: A list of data chunks.
        """
        return chunk_large_text(data, self.max_context_tokens - self.max_output_tokens)

    def _extract_relevant_content(self, question: Dict[str, Any], data: str) -> str:
        """
        Extract relevant content from the data for answering the question.

        Args:
            question (Dict[str, Any]): The current question being processed.
            data (str): The input data to analyze.

        Returns:
            str: Relevant content extracted from the input data.
        """

        json_schema = json.dumps({"quotes": ["example_quote"]}, indent=4)
        system_prompt = textwrap.dedent(f"""
            You are a research assistant assigned a specific question to investigate and tasked with reviewing input data. You must extract strings of text from this input that are likely relevant to answering your question.
                                        
            The document you compile will be reviewed by your supervisor, who will then attempt to answer the question based on the information you transcribed.
                                        
            The question you are tasked with answering is: {question}

            To complete your job, carefully follow the steps below.

            Step One: Meticulously and diligently read the document and identify any sections, sentences, or quotes that may be relevant to your question.

            Step Two: Consider if you have have missed any sections, sentences, or quotes that may contain neccessary context or nuance. 

            Step Three: Carefully transcribe the quotes you have identified and output the result in the following JSON schema:

            {json_schema}

            You must not modify, change, or correct any content from your source document. Do not reply with any other content except your transcription.
        """)

        prompt = data

        # Implement logic to extract relevant content
        prompt = f"Extract relevant information for the following question: {question['question']}\n\nData: {data}"
        response = self.ai_handler.request_completion(
            system_prompt=system_prompt,
            prompt=prompt,
            max_tokens=self.max_output_tokens,
            json_output=True
        )

        return response

# Example usage
if __name__ == "__main__":

    from classes.ai_handler import AIHandler
    from classes.QuestionnaireCompletion import QuestionnaireCompletion

    ai_handler = AIHandler.load('openai')
    questionnaire_completion = QuestionnaireCompletion(
        ai_handler=ai_handler,
        max_context_tokens=4000,
        max_output_tokens=1000
    )

    system_prompt = "You are an AI assistant helping to complete a questionnaire."
    prompt_path = "path/to/prompt/template.txt"
    questionnaire = {
        "title": "Demo",
        "created_at": "2024-08-15T15:06:40.797773",
        "questionnaire": [
            {
                "response_format": {"type": "object", "properties": {"name": {"type": "string"}}},
                "question": "What is the company name of the end client?",
                "answer": "",
                "category": "Company Information",
                "example": ""
            },
            {
                "response_format": {"type": "object", "properties": {"products": {"type": "array"}}},
                "question": "What specific commercially-available technology products are mentioned?",
                "answer": "",
                "category": "Technology",
                "example": ""
            }
        ]
    }
    input_files = ["C:\\Users\\admin\\Downloads\\proposal_notes.txt"]

    completed_questionnaire = questionnaire_completion.complete_questionnaire(
        system_prompt, prompt_path, questionnaire, input_files
    )
    print(json.dumps(completed_questionnaire, indent=2))