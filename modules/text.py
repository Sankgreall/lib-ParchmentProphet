import tiktoken
import re

def sanitise_text(text):
    # Define a dictionary mapping Unicode punctuation to their ASCII equivalents
    punctuation_map = {
        '‚': ',',  # Single low-9 quotation mark
        '„': '"',  # Double low-9 quotation mark
        '‹': '<',  # Single left-pointing angle quotation mark
        '›': '>',  # Single right-pointing angle quotation mark
        '«': '"',  # Left-pointing double angle quotation mark
        '»': '"',  # Right-pointing double angle quotation mark
        '‐': '-',  # Hyphen
        '–': '-',  # En dash
        '—': '--', # Em dash
        '⁄': '/',  # Fraction slash
        '’': "'",  # Right single quotation mark
        '‘': "'",  # left single quotation mark
        '”': '"',  # right double quotation mark
        '“': '"',  # left double quotation mark
        '′': "'",  # Prime
        '″': '"',  # Double prime
        '‴': "'",  # Triple prime
        '⁗': '?',  # Double question mark
        '⁓': '~',  # Swung dash
        '…': '...', # Horizontal ellipsis
    }

    # Replace Unicode punctuation with their ASCII equivalents
    sanitized_text = ''.join(punctuation_map.get(char, char) for char in text)

    return sanitized_text


def load_prompt(input_file_path, replacement_dict={}):

    try:
        with open(input_file_path, 'r') as file:
            # Read the file content
            content = file.read()
            
    # If not file exists, treat the input as the content
    except (FileNotFoundError, OSError):
        content = input_file_path
    
    # Iterate over the dictionary to replace placeholders
    for placeholder, replacement in replacement_dict.items():
        # Format the placeholder with double curly brackets
        wrapped_placeholder = "{{" + placeholder + "}}"
        # Replace the placeholder with the replacement value
        content = content.replace(wrapped_placeholder, replacement)
    
    return content


def count_tokens(str, model="gpt-4"):
    # Get token encoding for GPT-4
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(str))


def chunk_large_text(text, token_limit):
    current_chunk = ""  # Temporary storage for the current chunk
    
    for line in text.splitlines():  # Keep the original lines intact
        if not line:  # Skip empty lines
            continue
        
        # Consider adding this line to the current chunk
        if current_chunk:
            temp_chunk = current_chunk + "\n" + line
        else:
            temp_chunk = line

        token_count = count_tokens(temp_chunk)  # Count tokens in the temp chunk
        
        if token_count > token_limit:  # If adding this line exceeds the limit
            # Join current_chunk into a string to find the last period
            current_chunk_text = current_chunk
            last_period_index = current_chunk_text.rfind('.')  # Assign before referencing
            
            if last_period_index != -1:  # If there's a period, split at the period
                # Yield the chunk up to the last period
                yield current_chunk_text[:last_period_index + 1].strip()
                # Restart the current chunk with content after the period and the new line
                current_chunk = current_chunk_text[last_period_index + 1:].strip() + "\n" + line
            else:  # If no period, yield the current chunk and start a new one
                yield current_chunk_text.strip()
                current_chunk = line
        else:  # If the token count is within the limit
            current_chunk = temp_chunk  # Update the current chunk with the new line

    # Yield any remaining text in the last chunk
    if current_chunk.strip():
        yield current_chunk.strip()

def get_first_n_tokens(text, n_tokens):
    current_chunk = ""
    lines = text.splitlines()  # Split the text into a list of lines
    
    for line in lines:
        if not line:
            continue  # Skip empty lines
        
        temp_chunk = line.strip() if not current_chunk else current_chunk + "\n" + line.strip()
        token_count = count_tokens(temp_chunk)
        
        if token_count <= n_tokens:
            current_chunk = temp_chunk
        else:
            break
    
    return current_chunk.strip()

def get_last_n_tokens(text, token_limit):
    current_chunk = ""
    lines = text.splitlines()

    # Iterate over the lines from the end
    for line in reversed(lines):
        if not line:
            continue
        temp_chunk = line  # Initialize temp_chunk with the current line
        if current_chunk:
            temp_chunk += "\n" + current_chunk  # Append the existing chunk
        token_count = count_tokens(temp_chunk)  # Re-count tokens

        if token_count <= token_limit:
            current_chunk = temp_chunk
        else:
            # If adding this line exceeds the limit, break the loop
            break

    return current_chunk.strip()  # Return the final chunk as is


# Split text at the first line containing a keyword, returning the text before and after the keyword
def split_at_containing_line(text, keyword):
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if keyword in line.strip():
            return '\n'.join(lines[:i]), '\n'.join(lines[i+1:])
    return text, ''

# Remove single line breaks from text
def remove_single_line_breaks(text):
    # Replace single line breaks with nothing, but leave double line breaks
    # This pattern looks for instances of \n not followed or preceded by another \n
    cleaned_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    return cleaned_text