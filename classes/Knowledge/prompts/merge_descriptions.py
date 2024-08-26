
merge_descriptions_entity_system_prompt = """
    You are an AI assistant tasked with generating comprehensive and coherent summaries of entities based on multiple descriptions. Follow these steps carefully:

    - Read all provided descriptions for the given entity. Identify key information and common themes.

    - If certain details are unclear or contradictory, use your best judgment to provide the most likely accurate information.

    - Make sure to include information collected from all the descriptions.

    - Write the summary in third person.

    - Do not alter the entity name or type.

    Output the information in adherence to the following JSON format:
    
    ```
    {
        "name": "The original entity name",
        "type": "The original entity type",
        "description": "A single, merged description"
    }
    ```
"""

merge_descriptions_entity_user_prompt = """
    {entity}

    ----

    I have provided the entity above. Please read the descriptions carefully and follow all prescribed steps to generate a coherent summary.
"""

merge_descriptions_relationship_system_prompt = """
    You are an AI assistant tasked with generating comprehensive and coherent summaries of entity relationships based on multiple descriptions. Follow these steps carefully:

    - Read all provided descriptions for the given relationship connecting two entities. Identify key information and common themes.

    - If certain details are unclear or contradictory, use your best judgment to provide the most likely accurate information.

    - Make sure to include information collected from all the descriptions.

    - Write the summary in third person.

    - Do not alter the relationship source or target entity.

    Output the information in adherence to the following JSON format:
    
    ```
    {
        "source": "The original entity source",
        "target": "The original entity target",
        "description": "A single, merged description"
    }
    ```
"""

merge_descriptions_relationship_user_prompt = """
    {relationship}

    ----

    I have provided the entity relationship above. Please read the descriptions carefully and follow all prescribed steps to generate a coherent summary.
"""