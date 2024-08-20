import os
from openai import OpenAI
import tiktoken
import json
from pdf2image import convert_from_path
from PIL import Image
import io
import base64
from io import BytesIO


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

class OpenAIHandler:
    
    def __init__(self, api_key=None, max_output_tokens=None, max_context_tokens=None, default_model=None):
        # This constructor initializes the AIHandler.

        # Instantiate variables
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.max_output_tokens = max_output_tokens or int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", 4096))
        self.max_context_tokens = max_context_tokens or int(os.getenv("OPENAI_MAX_CONTEXT_TOKENS", 126000))
        self.default_model = default_model or os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o")

        # Initialize the OpenAI
        self.client = OpenAI(api_key=self.api_key)

    def get_max_output_tokens(self):
        return self.max_output_tokens
    
    def get_max_context_tokens(self):
        return self.max_context_tokens

    
    def request_completion(self, system_prompt="", prompt="", model=None, messages = [], temperature=0.2, top_p=None, max_tokens=None, json_output=False, image=None):

        def get_image_dimensions(image_base64):
            image_data = base64.b64decode(image_base64)
            image = Image.open(BytesIO(image_data))
            return image.width, image.height

        ####################################################################
        # Construct the messages object
        ####################################################################

        # If messages are blank
        if messages == [] and image == None:
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
        
        if messages == [] and image != None:
            # Compile messages
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}}
                    ]
                },
            ]

        # Else, messages are passed directly in

        ####################################################################
        # Calculate the total number of tokens in all messages
        ####################################################################

        # Load the tokenizer for the specified model
        enc = tiktoken.encoding_for_model(model if model else self.default_model)
        
        def count_tokens(message_content):
            if isinstance(message_content, list):
                return sum(len(enc.encode(part["text"])) if part["type"] == "text" else 0 for part in message_content)
            else:
                return len(enc.encode(message_content))

        # Calculate the total number of tokens in all messages
        total_tokens = sum(count_tokens(message["content"]) for message in messages)

        # Add the tokens for the image if present
        if image is not None:
            image_width, image_height = get_image_dimensions(image)

            if image_width <= 512 and image_height <= 512:
                total_tokens += 85
            else:
                # Calculate number of 512x512 tiles
                tiles_x = (image_width + 511) // 512  # ceiling division
                tiles_y = (image_height + 511) // 512  # ceiling division
                total_tiles = tiles_x * tiles_y
                total_tokens += 85 + (170 * total_tiles)

        # Check if the total tokens exceed the allowed context tokens minus max output tokens
        if total_tokens > (self.max_context_tokens - self.max_output_tokens):
            raise ValueError(f"The total token count of all messages ({total_tokens}) exceeds the allowed limit ({self.max_context_tokens}). This takes into account the maximum output token count: {self.max_output_tokens}.")
        
        ####################################################################
        # Define settings for the request
        ####################################################################

        settings = {
            "model": model if model else self.default_model,
            "max_tokens": max_tokens if max_tokens else self.max_output_tokens,
            "temperature": temperature,
        }

        if top_p:
            settings["top_p"] = top_p

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
    def recursive_summary(self, system_prompt, data, temperature=0.2, model=None, json_output=False):

        chunk_size = self.max_context_tokens - (self.max_output_tokens * 2) # One for output, one for previous summary
        first_iteration = True

        for chunk in chunk_large_text(data, chunk_size):

            # Construct message object
            if first_iteration:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk['content']}
                ]
                first_iteration = False

            else:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Document summary so far\n----\n{output}"},
                    {"role": "user", "content": f"Next document chunk\n----\n{chunk['content']}"}
                ]

            output = self.request_completion(messages=messages, temperature=temperature, model=model if model else self.default_model, json_output=True)

        return output

    def complete_questionnaire(self, system_prompt, prompt_path, questions, input_files):


        # Check questions variable is an array of dictionary objects contains keys
        # - question
        # - answer
        # - category
        # - example_answer
        for question in questions:
            if "question" not in question or "answer" not in question or "category" not in question or "example_answer" not in question:
                raise ValueError("Questions array must contain question, answer, category, and example_answer keys.")
        
        # For each question
        for question in questions:

            # Keep track of the answer we construct over time
            partial_answer = ""
            final_answer = ""

            # Answer the question, looking across all input files
            for input_file in input_files:

                # Read the input file (must be markdown or text)
                with open(input_file, 'r', encoding='utf-8') as file:
                    data = file.read()

                # Check if data exceeds token limit
                if count_tokens(data) > self.max_context_tokens + self.max_output_tokens:

                    # Chunk it up
                    for chunk in chunk_large_text(data, (self.max_context_tokens - self.max_output_tokens)):

                        # If partial answer is not empty, we need to add it to the prompt
                        if partial_answer:
                            partial_answer_prompt = f"# PARTIAL ANSWER\n\nThere is a partial answer to the question below. You must accept this partial answer as truthful and seek to expand, enrich, or further complete it.\n\nPartial answer:{partial_answer}\n\n----\n\n"
                            prompt = load_prompt(prompt_path, {"data": chunk, "partial_answer": partial_answer_prompt, "question": question["question"], "example_answer": question["example_answer"]})
                        else:
                            prompt = load_prompt(prompt_path, {"data": chunk, "partial_answer": "", "question": question["question"], "example_answer": question["example_answer"]})
                        
                        response = self.request_completion(system_prompt, prompt, json_output=True)
                        response = json.loads(response)

                        # If we recieved a response, set it as the partial answer
                        if response["answer"]:
                            partial_answer = response["answer"]
                    
                # Else, we can just use the data as is
                else:
                    # If partial answer is not empty, we need to add it to the prompt
                    if partial_answer:
                        partial_answer_prompt = f"# PARTIAL ANSWER\n\nThere is a partial answer to the question below. You must accept this partial answer as truthful and seek to expand, enrich, or further complete it.\n\nPartial answer:{partial_answer}\n\n----\n\n"
                        prompt = load_prompt(prompt_path, {"data": data, "partial_answer": partial_answer_prompt, "question": question["question"], "example_answer": question["example_answer"]})
                    else:
                        prompt = load_prompt(prompt_path, {"data": data, "partial_answer": "", "question": question["question"], "example_answer": question["example_answer"]})

                    response = self.request_completion(system_prompt, prompt, json_output=True)
                    response = json.loads(response)

                    # If we recieved a response, set it as the partial answer
                    if response["answer"]:
                        partial_answer = response["answer"]

            # Once we have the final answer, add it to the question object
            final_answer = partial_answer
            question["answer"] = final_answer

        return questions
    
    def vectorise(self, texts, model="text-embedding-3-small"):
        """
        Converts a given text string or an array of text strings into their corresponding embedding vectors using the OpenAI embeddings API.

        Args:
            texts (str or list): The input text(s) to be converted into embedding vector(s).
            model (str): The embedding model to be used. Defaults to "text-embedding-3-small".

        Returns:
            list: A list of embedding vectors corresponding to the input text(s).
        """
        if isinstance(texts, str):
            texts = [texts]

        texts = [text.replace("\n", " ") for text in texts]
        response = self.client.embeddings.create(input=texts, model=model)
        return [data.embedding for data in response.data]
    
