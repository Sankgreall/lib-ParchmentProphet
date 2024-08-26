import os
import anthropic
from PIL import Image
import base64
from io import BytesIO
from tenacity import retry, stop_after_attempt, wait_exponential

class AnthropicAPIError(Exception):
    """Custom exception class for handling Anthropic API errors."""
    pass

class TooManyImagesError(Exception):
    """Custom exception for when too many images are provided."""
    pass

class InvalidImageInputError(Exception):
    """Custom exception for invalid image input."""
    pass

class AnthropicHandler:
    """Handler class for interacting with the Anthropic API with retry logic and token counting."""

    DEFAULT_VALUES = {
        "ANTHROPIC_MAX_OUTPUT_TOKENS": 4096,
        "ANTHROPIC_MAX_CONTEXT_TOKENS": 200000,
        "ANTHROPIC_DEFAULT_MODEL": "claude-3-5-sonnet-20240620",
        "ANTHROPIC_RETRY_ATTEMPTS": 3,
        "ANTHROPIC_RETRY_WAIT_MULTIPLIER": 1,
        "ANTHROPIC_RETRY_WAIT_MIN": 4,
        "ANTHROPIC_RETRY_WAIT_MAX": 10,
        "ANTHROPIC_TIMEOUT": 240,
        "ANTHROPIC_MAX_IMAGES": 5
    }

    @staticmethod
    def get_env_or_default(key, default):
        """Retrieve environment variable or return a default value."""
        return os.getenv(key) or default

    def __init__(self, api_key=None, max_output_tokens=None, max_context_tokens=None, default_model=None,
                 retry_attempts=None, retry_wait_multiplier=None, retry_wait_min=None, retry_wait_max=None, timeout=None):
        """
        Initialize the AnthropicHandler with optional custom configurations.
        
        Parameters:
        api_key (str): API key for Anthropic.
        max_output_tokens (int): Maximum tokens for output.
        max_context_tokens (int): Maximum tokens for context.
        default_model (str): Default model to use.
        retry_attempts (int): Number of retry attempts.
        retry_wait_multiplier (int): Multiplier for exponential wait.
        retry_wait_min (int): Minimum wait time for retries.
        retry_wait_max (int): Maximum wait time for retries.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        # Raise error if no API key is provided
        if not self.api_key:
            raise ValueError("No API key provided for Anthropic")

        self.max_output_tokens = max_output_tokens or int(self.get_env_or_default("ANTHROPIC_MAX_OUTPUT_TOKENS", self.DEFAULT_VALUES["ANTHROPIC_MAX_OUTPUT_TOKENS"]))
        self.max_context_tokens = max_context_tokens or int(self.get_env_or_default("ANTHROPIC_MAX_CONTEXT_TOKENS", self.DEFAULT_VALUES["ANTHROPIC_MAX_CONTEXT_TOKENS"]))
        self.default_model = default_model or self.get_env_or_default("ANTHROPIC_DEFAULT_MODEL", self.DEFAULT_VALUES["ANTHROPIC_DEFAULT_MODEL"])

        # Retry settings
        self.retry_attempts = retry_attempts or int(self.get_env_or_default("ANTHROPIC_RETRY_ATTEMPTS", self.DEFAULT_VALUES["ANTHROPIC_RETRY_ATTEMPTS"]))
        self.retry_wait_multiplier = retry_wait_multiplier or int(self.get_env_or_default("ANTHROPIC_RETRY_WAIT_MULTIPLIER", self.DEFAULT_VALUES["ANTHROPIC_RETRY_WAIT_MULTIPLIER"]))
        self.retry_wait_min = retry_wait_min or int(self.get_env_or_default("ANTHROPIC_RETRY_WAIT_MIN", self.DEFAULT_VALUES["ANTHROPIC_RETRY_WAIT_MIN"]))
        self.retry_wait_max = retry_wait_max or int(self.get_env_or_default("ANTHROPIC_RETRY_WAIT_MAX", self.DEFAULT_VALUES["ANTHROPIC_RETRY_WAIT_MAX"]))
        self.timeout = timeout or int(self.get_env_or_default("ANTHROPIC_TIMEOUT", self.DEFAULT_VALUES["ANTHROPIC_TIMEOUT"]))

        # Image settings
        self.max_images = int(self.get_env_or_default("ANTHROPIC_MAX_IMAGES", self.DEFAULT_VALUES["ANTHROPIC_MAX_IMAGES"]))

        # Initialize the Anthropic client
        self.client = anthropic.Anthropic(api_key=self.api_key, timeout=timeout)

    def retry_decorator(self):
        """
        Define the retry decorator with exponential backoff.
        
        Returns:
        function: A tenacity retry decorator.
        """
        return retry(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=self.retry_wait_multiplier, min=self.retry_wait_min, max=self.retry_wait_max)
        )

    def submit(self, messages, system_prompt="", model=None, temperature=0.2, top_p=None, max_tokens=None):
        """
        Submit a request to the Anthropic API with retry logic.
        
        Parameters:
        messages (list): List of messages to send.
        system_prompt (str): Optional system prompt.
        model (str): Model to use for the request.
        temperature (float): Sampling temperature for the model.
        top_p (float): Nucleus sampling parameter.
        max_tokens (int): Maximum tokens for the response.

        Returns:
        str: The response text from the API.
        """

        @self.retry_decorator()
        def _submit():
            # Input validation
            if temperature < 0 or temperature > 1:
                raise ValueError("Temperature must be between 0 and 1")
            if top_p is not None and (top_p < 0 or top_p > 1):
                raise ValueError("Top_p must be between 0 and 1")
            if max_tokens is not None and max_tokens <= 0:
                raise ValueError("Max_tokens must be positive")

            # Calculate the total number of tokens
            total_tokens = self.count_tokens(messages)

            if total_tokens > (self.max_context_tokens - self.max_output_tokens):
                raise ValueError(f"The total token count ({total_tokens}) exceeds the allowed limit ({self.max_context_tokens}). This takes into account the maximum output token count: {self.max_output_tokens}.")

            # Define settings for the request
            settings = {
                "model": model if model else self.default_model,
                "max_tokens": max_tokens if max_tokens else self.max_output_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": messages
            }

            if top_p is not None:
                settings["top_p"] = top_p

            # Make the request
            try:
                response = self.client.messages.create(**settings)
                return response.content[0].text
            except anthropic.APITimeoutError:
                raise AnthropicAPIError("Request timed out")
            except anthropic.APIError as e:
                raise AnthropicAPIError(f"API Error: {str(e)}")
            except Exception as e:
                raise AnthropicAPIError(f"Unexpected error: {str(e)}")

        return _submit()

    def count_tokens(self, messages):
        """
        Count the total number of tokens in multiple messages, considering both text and images.
        
        Parameters:
        messages (list): A list of message dictionaries to count tokens for.

        Returns:
        int: The total token count across all messages.
        """

        def calculate_image_tokens(width, height):
            """Calculate token equivalent for image dimensions."""
            pixels = width * height
            return int(pixels / 750)  # Approximate token count for images

        def count_content_tokens(content):
            """Count tokens in the content of a single message."""
            if not content:
                return 0

            total = 0
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        total += self.client.count_tokens(part["text"])
                    elif part.get("type") == "image":
                        image_data = base64.b64decode(part["source"]["data"])
                        img = Image.open(BytesIO(image_data))
                        total += calculate_image_tokens(img.width, img.height)
            elif isinstance(content, str):
                total += self.client.count_tokens(content)
            else:
                raise ValueError("Unexpected content type in message")

            return total

        total_tokens = 0
        for message in messages:
            # Count tokens for the role
            total_tokens += self.client.count_tokens(message.get("role", ""))
            
            # Count tokens for the content
            content = message.get("content", [])
            total_tokens += count_content_tokens(content)

        return total_tokens

    def construct_message(self, prompt, base64_images=None):
        """
        Construct a message with optional text and multiple images.

        Parameters:
        prompt (str): The text prompt to include in the message.
        base64_images (list): A list of base64-encoded image data strings.

        Returns:
        list: A list containing the constructed message.

        Raises:
        TooManyImagesError: If more than max_images are provided.
        InvalidImageInputError: If base64_images is provided but is not a list.
        """
        content = []

        # Add text prompt if provided
        if prompt:
            content.append({
                "type": "text",
                "text": prompt
            })

        # Validate base64_images input
        if base64_images is not None:
            if not isinstance(base64_images, list):
                raise InvalidImageInputError("base64_images must be a list of strings.")
            
            if len(base64_images) > self.max_images:
                raise TooManyImagesError(f"Too many images provided. Maximum allowed is {self.max_images}.")

            # Add images
            for base64_image in base64_images:
                if not isinstance(base64_image, str):
                    raise InvalidImageInputError("Each image in base64_images must be a string.")
                
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_image
                    }
                })

        # Construct the message object
        messages = [{
            "role": "user",
            "content": content
        }]

        return messages