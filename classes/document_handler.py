import abc

class DocumentHandler(abc.ABC):
    def __init__(self, file_path):
        self.file_path = file_path

    @abc.abstractmethod
    def transcribe(self):
        pass

    @abc.abstractmethod
    def count_pages(self):
        pass

    def get_first_n_pages(self, n):
        pass

    def get_last_n_pages(self, n): 
        pass

    def get_page_n(self, n):
        pass

    def add_comment(self, text, comment):
        pass

    def track_change(self, text, replacement):
        pass

    @classmethod
    def load(cls, file_path):
        if file_path.endswith('.pdf'):
            from .pdf_handler import PDFHandler
            return PDFHandler(file_path)
        elif file_path.endswith('.docx'):
            from .docx_handler import DOCXHandler
            return DOCXHandler(file_path)
        else:
            raise ValueError("Unsupported file format")