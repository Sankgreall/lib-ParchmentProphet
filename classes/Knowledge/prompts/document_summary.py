document_summary_system_prompt = """
    The current date is 2024-08-20.

    Your task is to create a document summary for a long document. Your summary is restricted only to capturing the purpose of the document, who is involved, and any information you can ascertain about the time or place (including from the filename).

    - Do not provide key points
    - Do not summarize the content of the document
    - Do not waffle or provide unnecessary information
    - Do not attribute company affiliation, roles, or positions to invididuals unless you are certain

    The metadata for the document is as follows:

    {metadata}

    The information contained within this document was gathered for the intent of producing a report with the following scope:

    {scope}

    ----

    Output your document summary adhereing to the following JSON format.

    ```
    {
        "type_of_document": "e.g., transcript, report, email, policy, presentation",
        "identities": "names of individuals mentioned within the document",
        "temporal_details": "any information about when the document was created or the time period it covers",
        "document_summary": ""
    }

    ```

    Here is an example of what I would like you to provide:
    
    ```
    {
        "type_of_document": "transcript",
        "identities": "James Jackson from S-RM, unidentified employees of General Emballage",
        "temporal_details": "The transcript lasted approximately 40 minutes. There are no dated references in the document, but I assume it was created recently. The current date is 2024-08-20.",
        "document_summary": "The document is a transcript of a conversation between James Jackson of S-RM and General Emballage about their cybersecurity practices."
    }
    ```
"""
