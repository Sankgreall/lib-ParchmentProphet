import os
from anthropic import Anthropic
import tiktoken
import json

# Import text functions
try:
    # Try relative imports for deployment
    from ....modules.text import *
    from ....modules.markdown import *
except ImportError:
    # Fallback to absolute imports for local testing
    from modules.text import *
    from modules.markdown import *

class AnthropicHandler:
    
    def __init__(self, api_key=None, max_output_tokens=None, max_context_tokens=None, default_model=None):
        # This constructor initializes the AnthropicHandler.

        # Instantiate variables
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.max_output_tokens = max_output_tokens or int(os.getenv("ANTHROPIC_MAX_OUTPUT_TOKENS", 4096))
        self.max_context_tokens = max_context_tokens or int(os.getenv("ANTHROPIC_MAX_CONTEXT_TOKENS", 126000))
        self.default_model = default_model or os.getenv("ANTHROPIC_DEFAULT_MODEL", "claude-3-5-sonnet-20240620")

        # Initialize the Anthropic client
        self.client = Anthropic(api_key=self.api_key)

    def request_completion(self, system_prompt="", prompt="", model=None, messages=[], temperature=0.2, top_p=None, max_tokens=None, json_output=False):

        ####################################################################
        # Construct the messages object
        ####################################################################

        # If messages are blank
        if messages == []:
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]

        # Else, messages are passed directly in

        ####################################################################
        # Calculate the total number of tokens in all messages
        ####################################################################

        # Load the tokenizer for the specified model
        enc = tiktoken.encoding_for_model(model if model else self.default_model)
        
        # Calculate the total number of tokens in all messages
        total_tokens = sum([len(enc.encode(message["content"])) for message in messages])
        total_tokens += len(enc.encode(system_prompt) if system_prompt else 0)

        # Check if the total tokens exceed the allowed context tokens minus max output tokens
        if total_tokens > (self.max_context_tokens - self.max_output_tokens):
            raise ValueError(f"The total token count of all messages ({total_tokens}) exceeds the allowed limit ({self.max_context_tokens}). This takes into account the maximum output token count: {self.max_output_tokens}.")
        
        ####################################################################
        # Define settings for the request
        ####################################################################

        settings = {
            "model": model if model else self.default_model,
            "system": system_prompt,
            "max_tokens": max_tokens if max_tokens else self.max_output_tokens,
            "temperature": temperature,
            "messages": messages
        }

        if top_p is not None:
            settings["top_p"] = top_p

        # Make the request
        response = self.client.messages.create(**settings)
        return sanitise_text(response.content)
    
    
    def smart_transcribe(self):
        raise NotImplementedError("The smart_transcribe method is not implemented for the Anthropic API.")

    def recursive_summary(self):
        raise NotImplementedError("The recursive_summary method is not implemented for the Anthropic API.") 
    
    def complete_questionnaire(self):
        raise NotImplementedError("The complete_questionnaire method is not implemented for the Anthropic API.")
    
    def vectorise(self):
        raise NotImplementedError("The vectorise method is not implemented for the Anthropic API.")
