import os
from openai import OpenAI
import tiktoken
import nltk
import unicodedata
import re
import json

# Import text functions
from ..modules.text import *
from ..modules.markdown import *

class AIHandler:
    
    def __init__(self, api_key=None, max_output_tokens=None, max_context_tokens=None):
        # This constructor initializes the AIHandler.

        # Instantiate variables
        if api_key is None:
            self.api_key = os.getenv("OPENAI_API_KEY")

        if max_output_tokens is None:
            self.max_output_tokens = int(os.getenv("max_output_tokens"))

        if max_context_tokens is None:
            self.max_context_tokens = int(os.getenv("max_context_tokens"))

        # Initialize the OpenAI
        self.client = OpenAI()
    
    def request_completion(self, system_prompt="", prompt="", model="gpt-4-turbo", messages = [], temperature=0.2, top_p=None, max_tokens=None, json_output=False):

        # If messages are blank
        if messages == []:
            # Compile messages
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

        settings = {
            "model": model,
        }

        if temperature:
            settings["temperature"] = temperature

        if top_p:
            settings["top_p"] = top_p

        if max_tokens:
            settings["max_tokens"] = max_tokens

        if json_output:
            settings["response_format"] = {"type": "json_object"}

        # Make the request
        response = self.client.chat.completions.create(messages=messages, **settings)
        return sanitise_text(response.choices[0].message.content)

    def smart_transcribe(self, file_path, output_path, system_prompt_path, token_reduction=0.95, temperature=0.13, top_p=None, prompt_header="", prompt_memory_header="", prompt_structure_header=""):
        """
        Transcribes a given text file using the AI model's capabilities.

        Args:
            file_path (str): The path to the input text file.
            output_path (str): The path to save the transcribed output.
            system_prompt_path (str): The path to the system prompt file.
            token_reduction (float, optional): The reduction factor for the maximum output tokens. Defaults to 0.95.
            temperature (float, optional): The temperature parameter for the AI model. Defaults to 0.10.
            top_p (float, optional): The top_p parameter for the AI model. Defaults to None.
            prompt_header (str, optional): The prompt header to be used. Defaults to an empty string.
            prompt_memory_header (str, optional): The prompt memory header to be used. Defaults to an empty string.

        Raises:
            Exception: If the sum of max_output_tokens and exceeds max_context_tokens.
        """

        # Read the file into memory
        with open(file_path, 'r', encoding='utf-8') as file:
            file_contents = file.read()

        if prompt_header == "":
            prompt_header = "Transcribe the above text chunk as directed."

        if prompt_memory_header == "":
            prompt_memory_header = "Provide a complete transcription of the next chunk, provided above, continuing seamlessly from your previous transcription."

        if prompt_structure_header == "":
            prompt_memory_header = False

        else:

            # Right, we've been told structure is important. We need to extract
            # this information from the text FIRST before attempting to transcribe.
            # system_prompt = "Your task is to review the document that your user provides, and return a high level structure of the document in markdown. This structure should include the titles of the document, and the hierarchy of the titles."
            # structure_prompt = ""
            # document_structure = self.request_completion(system_prompt, prompt, temperature=temperature)
            pass


        # Grab chunks of text using 95% of the output token size
        token_limit = int(self.max_output_tokens * token_reduction)

        system_prompt = load_prompt(system_prompt_path)

        # Check if the sum of max_output_tokens and chunk_memory is less than max_context_tokens
        if (self.max_output_tokens * 2) + count_tokens(prompt_header) + count_tokens(prompt_memory_header) + count_tokens(prompt_structure_header) + count_tokens(system_prompt) + 100 >= self.max_context_tokens: # 100 tokens added for generic other content
            raise Exception(f"Total context tokens exceed max available: {self.max_context_tokens}. Please reduce the token count.")

        # Create or overwrite the output file
        with open(output_path, 'w') as f:
            pass  # File is created or cleared

        previous_transcription = ""
        chunk_index = 0
        chunks = list(chunk_large_text(file_contents, token_limit))
        num_chunks = len(chunks)
        title_structure_memory = []

        # Loop through the chunks
        for chunk in chunks:
            if previous_transcription:

                # Create message object to pass to the completion request
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{sanitise_text(previous_chunk)}\n----\n{prompt_header}"},
                    {"role": "assistant", "content": f"{sanitise_text(previous_transcription)}"},
                    {"role": "user", "content": f"{sanitise_text(chunk)}\n----\n{prompt_memory_header}"}
                ]

                # iAdd in the title structure memory if requested
                if prompt_memory_header is not False:
                    messages.insert(3, {"role": "user", "content": f"{title_structure_memory_str}\n----\n{prompt_structure_header}"})

            else:
                messages = []
                prompt = f"{sanitise_text(chunk)}\n----\n{prompt_header}"

            # Get the result from the completion request
            result = self.request_completion(system_prompt, prompt, messages=messages, temperature=temperature, top_p=top_p)

            # Extract titles from the transcribed result
            result_titles = extract_markdown_titles(result)

            # Update the title structure memory
            title_structure_memory.extend(result_titles)
            title_structure_memory_str = "\n".join([f"- {title}" for title in title_structure_memory])

            # Append the result to the output file
            with open(output_path, 'a') as f:
                if chunk_index < num_chunks - 1:
                    if not result.endswith("\n\n"):
                        result += "\n\n"
                f.write(result)

            previous_chunk = chunk
            previous_transcription = result
            chunk_index += 1

        return title_structure_memory
    
    # Take a document exceeding max token limit and recursively summarise it
    def recursive_summary(self, system_prompt, data, temperature=0.2, model="gpt-4-turbo"):

        chunk_size = int(os.getenv("MAX_CONTEXT_TOKENS")) - (int(os.getenv("MAX_OUTPUT_TOKENS")) * 2) # One for output, one for previous summary
        first_iteration = True

        for chunk in chunk_large_text(data, chunk_size):

            # Construct message object
            if first_iteration:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk}
                ]
                first_iteration = False

            else:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"ROLLING SUMMARY\n----\n{output}"},
                    {"role": "user", "content": chunk}
                ]

            output = self.request_completion(messages=messages, temperature=temperature, model=model)

        return output

    def ask_question(self, function, system_prompt="", prompt="", temperature=""):

        messages = [
            {"role": "system", "content": "Respond to the following question."},
            {"role": "user", "content": "What is 7 + 3?"}
        ]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": function.__name__,
                    "description": "Adds two numbers together",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "arg1": {"type": "number", "description": "The first number to add"},
                            "arg2": {"type": "number", "description": "The second number to add"},
                        },
                        "required": ["arg1", "arg2"],
                    },
                },
            }
        ]

        available_functions = {function.__name__: function}

        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        response_message = response.choices[0].message
        return response_message
        