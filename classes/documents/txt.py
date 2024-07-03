import tempfile
from ..document_handler import DocumentHandler

class TXTHandler(DocumentHandler):
    def __init__(self, file_path):
        super().__init__(file_path)
        self.file_path = file_path

    def transcribe(self):
        # Create a temporary Markdown file and write the contents of the .txt file to it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md") as temp_md:
            with open(self.file_path, 'r') as file:
                temp_md.write(file.read().encode())
            return temp_md.name
