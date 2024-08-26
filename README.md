# ParchmentProphet

ParchmentProphet is a Proof-of-Concept application designed to demonstrate report generation capabilities. This repository is the core library backing the full application.

# Features

There are four key features of this library.

- **Graph Extraction**. Although ParchmentProphet has not implemented full GraphRAG (for reasons that make it unsuitable for report generation), it is capable of performing full entity and relationship extraction.

- **Research Questions**. ParchmentProphet builds upon the concept of Claims (discussed here) to focus them more on assessing bias and then condensing them to answer specific research questions that must be posed in advance of indexing. In this way, we can retrieve a high-fidelity answer with low-knowledge loss that RAG approaches would struggle to match.

- **Fine-Tuning**. Four AI models are currently used by the project. Although they default to gpt-4o, each model can be fine-tuned to develop their specialisms. For example, the Graph and Claim extraction models can be fine-tuned on top of a gpt-4o-mini base model.

- **Templated Output**. ParchmentProphet divides reports into sections and generates them incrementally. This means you can exceed the output token limits and receive structured outputs that can be recombined into a single document.

# Installation

1. Clone the repository

```
git clone https://github.com/your-username/ParchmentProphet
cd ParchmentProphet
```

2. Create and activate a virtual environmnets (recommended)

```
python -m venv venv
source venv/bin/activate
```

Or for Windows:

```
python -m venv venv
.\venv\Scripts\activate
```

3. Install dependencies

```
pip install .
```

4. Copy .env.sample and populate your .env

# Prerequisites

In addition to the required packages, you will also require:

- A Neo4j instance
- An Elastic instance
- An OpenAI API key
- Pandoc

# License

ParchmentProphet is released under the MIT License.