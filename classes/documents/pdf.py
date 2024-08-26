import os
import tempfile
import pdfminer.high_level
from pdfminer.layout import LAParams
from pdf2image import convert_from_path
import io
import base64

from ..document_handler import DocumentHandler#
from ..ai_handler import AIHandler

# Import text functions
try:
    # Try relative imports for deployment
    from ....modules.text import *
except ImportError:
    # Fallback to absolute imports for local testing
    from ParchmentProphet.modules.text import *

ai = AIHandler.load()

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
        
    def image_ocr(self, skip=0, system_prompt_path=None, prompt_path=None):

        if system_prompt_path is None:
            system_prompt = """
            Your are a data entry assistant processing a PDF form. You must accurately transcribe the contents of the PDF images you are shown and output a transcription in markdown format.

            To complete your job, carefully follow the steps below.

            Step One: Meticulously and diligently read the form and identify all questions the form asks of the applicant.

            Step Two: For each question, identify where the applicant has submitted an answer. Some answers might be in the format of a checkbox, date, or other field. Be careful to identify what form the answer has taken and record its state.

            Step Three: Output your transcription of the form as markdown submitted text. Do not put the markdown in a codeblock. Represent fields such as checkboxes in plain text, for example "[ x ]" and "[ ]".

            Do not reply with any other content except your transcription.
            """
        else:
            system_prompt = load_prompt(system_prompt_path)

        if prompt_path is None:
            prompt = """
            Please extract the text from this image. Do not reply with any other content except your transcription.
            """
        else:
            prompt = load_prompt(prompt_path)

        images = convert_from_path(self.file_path)
        combined_text = ""

        for index, image in enumerate(images):

            if index < skip:
                continue

            # Convert the PIL image to a byte array
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            # Encode the byte array to base64
            base64_image = base64.b64encode(img_byte_arr).decode('utf-8')

            # Make the request to the OpenAI API with the image
            response = ai.request_completion(
                system_prompt=system_prompt,
                prompt=prompt,
                image=base64_image
            )

            combined_text += response + "\n\n"

        return combined_text