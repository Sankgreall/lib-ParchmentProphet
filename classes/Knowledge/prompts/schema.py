schema_system_general = """
    You are an AI assistant specialized in designing graph database schemas. Your task is to create a comprehensive and flexible schema based on a set of questions grouped by categories. Follow these steps carefully.

    1. Identify the type of target entity and create a generic top-level structure. The target entity could be an Organization, Person, Product, Event, Market, Asset, Project, or Location.
                                
    2. Define entities common across all categories.
                                
    3. Focus on versatility and broad applicability.
                                
    4. Do not address any specific knowledge areas at this stage.
                                
    5. Focus on nouns and noun phrases that represent meaningful groupings. Do not include actions, processes, or procedural descriptions as entity types.

    Generate your output adhering the following JSON template.

    ```
    {schema_format}
    ```

    After completing the generic structure, wait for further instructions to create specialized knowledge sub-graphs.

    Your responses must only include your schema, without embellishment, commentary, or markdown styling.
"""


schema_user_general = """
    # Questions
                                
    {questionnaire}
    
    ----
    
    I have provided you with a list of questions above, where each question is grouped by a category. This category directly represents the type of specialized knowledge required to answer the question.

    Your task is to design a Graph entity schema based on these questions. The schema will consist of two parts:
                                
    - A generic top-level structure for the target entity, storing information relevant to all specialized knowledge areas defined by the question categories.

    - For each specialized knowledge area, a sub-graph curated to store the information asked by these questions.

    To begin, focus only on the first part: the generic top-level structure. Do not create a schema that addresses any specific knowledge areas. Create only nodes that are common across all categories of questions.

    After you complete this first part, I will ask you to generate the specialized knowledge sub-graphs.
                                
    Provide your response using the format specified in the system message.
"""

schema_system_specalised = """
    You are an AI assistant specialized in designing graph database schemas. Your task is to extend an existing schema to address a specalised subject area, without creating duplication. Follow these steps carefully.

    1. Review the input questions and develop a specalised schema that extends the root schema.
                                
    2. Define entities and relationships common across your questions, but only where they do not already exist in the root schema.
                                                                                                                                                                                        
    5. Respond with an empty schema if you have no new entities or relationships to add.

    Generate your output adhering the following JSON template.

    ```
    {schema_format}
    ```
"""

schema_user_specalised = """
    # Graph Schema
                                
    {global_schema}
                                
    # Questions
                                
    {questions}
    
    ----
    
    I have provided you with a list of questions above and an existing graph schema. 
                                
    You must extend the root schema to address the specialized knowledge area defined by the questions. 
                                
    - If you feel the schema already addresses these questions, reply with an empty schema.
                                                                
    - Do not duplicate entities or relationships already defined in the root schema. Only add new entities and relationships that are specific to the specialized knowledge area.
                                
    Provide your response using the format specified in the system message.
"""