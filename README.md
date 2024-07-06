# ParchmentProphet

ParchmentProphet is a utility library designed to assist with parsing unstructured file data, constructing prompts for LLMs, and deriving insights from your AI generated content. 

A rudimentry UI showcasing ParchmentProphet's ability to model the effectiveness of your AI generated content is available here:

- Demo site: https://parchmentprophet-ca.bravesea-a3cf7791.uksouth.azurecontainerapps.io/

- Repo: https://github.com/Sankgreall/ParchmentProphet-ui

# Functionality

ParchmentProphet offers a range of powerful functionalities:

- Document Handling: Extract text from various file formats (PDF, DOCX, XLSX, TXT) and convert them into a universal markdown format that can be used to prompt LLMs.

- Text Evaluation: Analyse text for readability, lexical diversity, syntactic complexity, and other linguistic features. Use this to compare human-generated and AI-generated text samples to identify similarities and differences.

- Elasticsearch Integration: Store and retrieve processed documents efficiently using Elasticsearch.

## Usage Examples

### Document Summarisation

```python 
from ParchmentProphet.classes.document_handler import DocumentHandler
from ParchmentProphet.classes.ai_handler import AIHandler

# Load a PDF document
doc_handler = DocumentHandler.load("path/to/document.pdf")
# Transcribe the PDF into markdown
transcribed_text = doc_handler.transcribe()

# Load the AIHandler (defaults to OpenAI)
ai_handler = AIHandler.load()

# recursive_summary will work even when the PDF contents exceeds the max_tokens
# available in your LLM. It does this by dynamically chunking the content and 
# summarisation chunks in increments.
summary = ai_handler.recursive_summary(system_prompt, transcribed_text)

print(summary)
```

### Compare Human and AI-Generated Text

```python
from ParchmentProphet.modules.evaluate import compare_samples_nd

samples = [
    {
        "human_generated": "Human-written text here...",
        "ai_generated": "AI-generated text here..."
    },
    # Add more sample pairs as needed
]

linguistic_scores, linguistic_distance = compare_samples_nd(samples)
print("Linguistic Distance:", linguistic_distance)
```

## Installation

To install ParchmentProphet, you can use pip:
```
pip install git+https://github.com/your-username/ParchmentProphet.git
```

Make sure to set up the required environment variables as specified in the env.sample file.

## Roadmap

Our vision for ParchmentProphet includes several exciting enhancements and new features. Here's what we're planning for future releases:

- [ ] Integrate support for Anthropic and Gemini APIs 
- [ ] Incorporate AI vision for documents that contain embedded images
- [ ] Implement batch processing for large document sets
- [ ] Create full library documentation