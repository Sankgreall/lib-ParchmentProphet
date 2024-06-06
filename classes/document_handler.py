import abc

class DocumentHandler(abc.ABC):
    def __init__(self, file_path):
        self.file_path = file_path

    @abc.abstractmethod
    def transcribe(self):
        pass

    @classmethod
    def load(cls, file_path):
            if file_path.endswith('.pdf'):
                from .pdf_handler import PDFHandler
                return PDFHandler(file_path)
            elif file_path.endswith('.docx'):
                from .docx_handler import DOCXHandler
                return DOCXHandler(file_path)
            elif file_path.endswith('.xlsx') or file_path.endswith('.xls'):
                from .excel_handler import ExcelHandler
                return ExcelHandler(file_path)
            elif file_path.endswith('.txt'):
                from .txt_handler import TXTHandler
                return TXTHandler(file_path)
            else:
                raise ValueError("Unsupported file format")