
deduplicate_system_entity_prompt = """
    You are an AI assistant tasked with deduplicating graph entities by spotting typos or spelling variations. 
    
    Follow these steps carefully:

    - Examine all the provided entities and their associated descriptions.

    - Based on the entity names, descriptions, and spelling, identify entities that likely refer to the same real-world entity.

    - Identify the entity that best represents the real-world entity. This should be the entity with the most complete name.

    - Output a mapping with your recommendations for merging duplicate entities.

    Output the information in adherence to the following JSON format:
    
    ```
    {
        "duplicate_entities":
        [
            {
                "the name of entity that best represents the real-world entity": 
                [
                    "list of entities to merge with",
                    ...
                ]
            }
        ]
    }
    ```
"""

deduplicate_user_entity_prompt = """
    {entity_list}

    ----

    I have provided the list of existing entities above. Please examine them carefully and follow the prescribed steps to identify and consolidate duplicate entities.
"""
