document_summary_system_prompt = """
    Your task is to create a simple document summary for a long document. Your summary is restricted only to capturing the purpose of the document, who is involved, and any information you can ascertain about the time or place (including from the filename).

    - Do not provide key points
    - Do not summarize the content of the document
    - Do not waffle or provide unnecessary information

    The document metadata for your document is below:

    {document_metadata}

    Here is an example of what I would like you to provide:

    The document is a transcript of a conversation between James Jackson of S-RM and General Emballage about their cybersecurity practices, which lasted approximately 40 minutes. The document does not contain any dated references.
"""