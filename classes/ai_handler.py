import abc

class AIHandler(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def request_completion(self, system_prompt, prompt, model, messages, temperature, top_p, max_tokens, json_output):
        pass

    @abc.abstractmethod
    def smart_transcribe(self, file_path, output_path, system_prompt_path, token_reduction, temperature, top_p, prompt_header, prompt_memory_header, prompt_structure_header):
        pass

    @abc.abstractmethod
    def recursive_summary(self, system_prompt, data, temperature, model):
        pass

    @abc.abstractmethod
    def complete_questionnaire(self, system_prompt, prompt_path, questions, input_files):
        pass

    @abc.abstractmethod
    def vectorise(self, texts, model):
        pass
    
    @abc.abstractmethod
    def fine_tune_model(self, training_file_path, base_model="gpt-4o", suffix=None, hyperparameters=None, timeout=3600):
        pass

    @classmethod
    def load(cls, ai_provider='openai'):
        if ai_provider.lower() == 'openai':
            from .ai.openai import OpenAIHandler
            return OpenAIHandler()
        elif ai_provider.lower() == 'anthropic':
            from .ai.anthropic import AnthropicHandler
            return AnthropicHandler()
        else:
            raise ValueError("Unsupported AI provider")