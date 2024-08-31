import os
from openai import OpenAI
import tiktoken
import json
from json.decoder import JSONDecodeError
from pdf2image import convert_from_path
from PIL import Image
import io
import base64
from io import BytesIO
import time


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

        self.supported_for_training = [
            "gpt-3.5-turbo", 
            "gpt-4o", 
            "gpt-4o-mini",
            "gpt-4o-2024-08-06"
        ]

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
        content = sanitise_text(response.choices[0].message.content)

        if json_output:
            try:
                json.loads(content)  # Attempt to parse the response as JSON
                return content
            except JSONDecodeError:
                # If the first attempt fails, try one more time
                response = self.client.chat.completions.create(messages=messages, **settings)
                content = sanitise_text(response.choices[0].message.content)
                
                try:
                    json.loads(content)  # Attempt to parse the second response as JSON
                    return content
                except JSONDecodeError:
                    # If the second attempt also fails, raise an error with the details
                    raise ValueError(f"Failed to get a valid JSON response after two attempts. Last response:\n\n {content}")
        
        return content
    
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
            
    def fine_tune_model(self, training_file_path, base_model="gpt-4o", suffix=None, hyperparameters=None, timeout=3600):
        """
        Fine-tunes a model using the provided training file.

        Args:
            training_file_path (str): Path to the training file (should be a JSONL file).
            base_model (str): The base model to fine-tune. Defaults to "gpt-4o".
            suffix (str, optional): A string of up to 40 characters that will be added to your fine-tuned model name.
            hyperparameters (dict, optional): Hyperparameters for fine-tuning.
            timeout (int): Maximum time in seconds to wait for fine-tuning to complete. Defaults to 3600 (1 hour).

        Returns:
            dict: A dictionary containing the status of the fine-tuning job and additional information.

        Raises:
            ValueError: If the base model is not supported for fine-tuning.
        """
        
        if base_model not in self.supported_for_training:
            raise ValueError(f"Base model {base_model} is not supported for fine-tuning.")
        
        # Count the number of lines in the file
        num_lines = sum(1 for line in open(training_file_path))
        if num_lines < 10:
            raise ValueError("Insufficient training data. At least 10 samples are required for fine-tuning.")
        
        result = {
            "status": "unknown",
            "model": None,
            "error": None,
            "details": {}
        }

        # Upload the training file
        try:
            with open(training_file_path, "rb") as file:



                file_upload = self.client.files.create(file=file, purpose="fine-tune")
            print(f"Training file uploaded with ID: {file_upload.id}")
            result["details"]["file_id"] = file_upload.id
        except Exception as e:
            result["status"] = "failed"
            result["error"] = f"File upload failed: {str(e)}"
            return result

        try:
            # Create fine-tuning job
            job_params = {
                "training_file": file_upload.id,
                "model": base_model
            }
            if suffix:
                job_params["suffix"] = suffix
            if hyperparameters:
                job_params["hyperparameters"] = hyperparameters

            fine_tuning_job = self.client.fine_tuning.jobs.create(**job_params)
            result["details"]["job_id"] = fine_tuning_job.id
            print(f"Fine-tuning job created with ID: {fine_tuning_job.id}")

            # Wait for the fine-tuning job to complete or timeout
            start_time = time.time()
            while True:
                job_status = self.client.fine_tuning.jobs.retrieve(fine_tuning_job.id)
                print(f"Fine-tuning status: {job_status.status}")
                result["status"] = job_status.status
                
                if job_status.status == "succeeded":
                    print("Fine-tuning completed successfully!")
                    result["model"] = job_status.fine_tuned_model
                    return result
                elif job_status.status == "failed":
                    result["error"] = "Fine-tuning failed. Check job details for more information."
                    result["details"]["job_details"] = job_status
                    return result
                
                if time.time() - start_time > timeout:
                    result["status"] = "timeout"
                    result["error"] = f"Fine-tuning timed out after {timeout} seconds."
                    return result
                
                time.sleep(60)  # Wait for 60 seconds before checking again

        except Exception as e:
            result["status"] = "error"
            result["error"] = f"An unexpected error occurred: {str(e)}"
            print(result)
            return False
        finally:
            # Delete the training file
            try:
                self.client.files.delete(file_upload.id)
                print(f"Training file with ID {file_upload.id} has been deleted.")
            except Exception as delete_error:
                print(f"Failed to delete training file: {str(delete_error)}")

        return result