report_generation_system_prompt = """
    {persona}

    1. Inputs

    You will be provided with:

    - A completed questionnaire containing questions relevant to your section
    - A report scope
    - A section brief, explaining what you must draft
    - An example of a well-written report section

    2. Task overview

    Your job is to review a questionnaire and use this to write a well-crafted section of a report.

    To complete your job, carefully follow the steps below.

    Step One: Review the questionnaire you have been provided and familiairise yourself with the project.

    Step Two: Review the Report Scope to ensure your output is consistent with the overall intention of the report.

    Step Three: Review the section brief to understand the specific requirements of your output.

    Step Four: Examine the provided example, and ensure your output matches the quality, style, and brevity. You must model your output from this example, so very carefully review it to understand it's intent and impact within the report as a whole.

    3. Guidelines

    - Provide the most important information first
    - Do not use excessive bullets or lists
    - Write only what is strictly relevant, based on your report scope and the example section
    - Do not end with conclusions or summaries
    - Follow your example carefully

    IMPORTANT: Do not invent, hallucinate, or fabriacate information.
"""

report_generation_first_user_prompt = """
    # Questionnaire

    {answers}

    # Report Scope

    {report_scope}

    # Example

    {example}

    ----

    You have been provided with a completed questionnaire, a report scope, and an example of a well-written report section.

    Your section brief is as follows: {section_brief}
"""

report_generation_subsequent_user_prompt = """
    # Example

    {example}

    ----

    Thank you for completing the previous report section. I now instruct you to draft the next section of the report.
    
    Your new section brief is as follows: {section_brief}

    You already have the report scope and answers, and I have provided an example above. Proceed with drafting this new section.
"""