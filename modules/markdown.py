import re
import json
from bs4 import BeautifulSoup
from modules.text import sanitise_text


def extract_markdown_titles(markdown_text):
    """
    Extracts all titles from a string of markdown text.

    Args:
        markdown_text (str): The markdown text to search for titles.

    Returns:
        list: An ordered list of titles with their string values (e.g., ['# Title 1', '## Subtitle 1', '## Subtitle 2', '# Title 2']).
    """
    titles = []
    pattern = r'^(#{1,6})\s*(.+)$'
    for line in markdown_text.splitlines():
        match = re.match(pattern, line)
        if match:
            title_level = len(match.group(1))
            title_text = match.group(2)
            title_string = f"{match.group(1)} {title_text}"
            titles.append(title_string)

    return titles

# return markdown as a dictionary, in the format of {# major heading -> content, ...}
def parse_markdown(markdown):

    # Replace UTF punctuation with ASCII equivalents in memory
    markdown = sanitise_text(markdown)

    # Split the text at the first major heading
    parts = re.split(r'\n# ', markdown, 1)

    # Initialize the result array
    result = []

    # The first part is the title
    if len(parts) > 1:
        title, rest_of_text = parts

        # Only grab data before the contents page, if if exists
        title_page = re.split(r'Contents', title)[0]

        # If we're not using the LLM, just add the title page
        result.append({
            "report_title": title
        })

    else:
        # If there's no heading, the entire text is the title
        rest_of_text = parts[0]

    # Regular expression for headings and contents
    pattern = r'#+ (.+)\n([\s\S]+?)(?=\n#+ |\Z)'

    # Find all matches in the rest of the text
    matches = re.findall(pattern, rest_of_text)

    # Process each match
    for heading, content in matches:
        result.append({
            heading.strip(): content.strip()
        })

    return result

# Convert a markdown/html table to JSON
def table_to_json(text):

    # Parse the HTML
    soup = BeautifulSoup(text.strip(), 'html.parser')

    # Initialize the JSON structure
    data = []

    # Locate the table header for column names
    thead = soup.find('thead')

    # Extract the column names
    column_names = [th.text.strip() for th in thead.find_all('th')]

    # Locate the table body
    tbody = soup.find('tbody')

    # Iterate through each row in the table body
    for row in tbody.find_all('tr'):

        # Extract data from each cell in the row
        cells = row.find_all('td')

        # If the row has cells
        if cells:
            # Pair up column names with cell data
            row_data = {column_names[i]: cells[i].text.strip() for i in range(len(cells))}

            # Add the row's dictionary to the data list
            data.append(row_data)

    # Convert the list of dictionaries to JSON
    return data
