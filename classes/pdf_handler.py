import os
import tempfile
import pdfminer.high_level
from pdfminer.layout import LAParams

from classes.document_handler import DocumentHandler


class PDFHandler(DocumentHandler):

    def __init__(self, file_path):
        super().__init__(file_path)
        self.file_path = file_path
        self.temp_file = None

    def count_pages(self):
        with open(self.file_path, "rb") as infp:
            # Get the total number of pages in the PDF
            return len(list(pdfminer.high_level.extract_pages(infp)))

    def get_first_n_pages(self, n):
        try:
            with open(self.file_path, "rb") as infp:
                pages = pdfminer.high_level.extract_pages(
                    infp,
                    page_numbers=set(range(1, n + 1)),
                    laparams=LAParams(),
                    password="",
                )
                combined_text = ""
                for page_layout in pages:
                    for element in page_layout:
                        if isinstance(element, pdfminer.layout.LTTextBoxHorizontal):
                            text = element.get_text()
                            if text is not None or text.strip() != "None":
                                combined_text += text
                
                return combined_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None
        
    def get_last_n_pages(self, n):
        try:
            with open(self.file_path, "rb") as infp:
                # Get the total number of pages in the PDF
                num_pages = len(list(pdfminer.high_level.extract_pages(infp)))

                # Calculate the starting page number for the last n pages
                start_page = max(1, num_pages - n + 1)

                # Extract the last n pages
                pages = pdfminer.high_level.extract_pages(
                    infp,
                    page_numbers=set(range(start_page, num_pages + 1)),
                    laparams=LAParams(),
                    password="",
                )

                combined_text = ""
                for page_layout in pages:
                    for element in page_layout:
                        if isinstance(element, pdfminer.layout.LTTextBoxHorizontal):
                            text = element.get_text()
                            if text is not None and text.strip() != "None":
                                combined_text += text

                return combined_text

        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None
        
    def get_page_n(self, n):
        try:
            with open(self.file_path, "rb") as infp:
                pages = pdfminer.high_level.extract_pages(
                    infp,
                    page_numbers=set([n]),
                    laparams=LAParams(),
                    password="",
                )
                combined_text = ""
                for page_layout in pages:
                    for element in page_layout:
                        if isinstance(element, pdfminer.layout.LTTextBoxHorizontal):
                            text = element.get_text()
                            if text is not None or text.strip() != "None":
                                combined_text += text
                
                return combined_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None
        
    def transcribe(self):
        temp_file_path = None  # Declare temp_file_path here
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as outfp:
                with open(self.file_path, "rb") as infp:
                    pdfminer.high_level.extract_text_to_fp(
                        inf=infp,
                        outfp=outfp,
                        output_type="text",
                        laparams=LAParams(),
                        codec="utf-8",
                        scale=1.0,
                        rotation=0,
                        layoutmode="normal",
                        strip_control=False,
                        page_numbers=None,
                        maxpages=0,
                        password="",
                        debug=False,
                        disable_caching=False
                    )
                # Flush and ensure data is written to disk before closing
                outfp.flush()
                os.fsync(outfp.fileno())
                temp_file_path = outfp.name

            return temp_file_path

        except Exception as e:
            print(f"Error converting PDF to HTML: {e}")
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except PermissionError:
                    pass
            return None
        