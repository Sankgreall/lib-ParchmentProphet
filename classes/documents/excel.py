import os
import tempfile
import openpyxl
import xlrd
from ..document_handler import DocumentHandler

class ExcelHandler(DocumentHandler):

    def __init__(self, file_path):
        super().__init__(file_path)
        self.file_path = file_path

    def transcribe(self):
        temp_file_path = None
        try:
            if self.file_path.endswith('.xlsx'):
                temp_file_path = self._extract_text_from_xlsx()
            elif self.file_path.endswith('.xls'):
                temp_file_path = self._extract_text_from_xls()
            return temp_file_path
        except Exception as e:
            print(f"Error converting Excel to text: {e}")
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except PermissionError:
                    pass
            return None

    def _extract_text_from_xlsx(self):
        temp_file_path = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as outfp:
            workbook = openpyxl.load_workbook(self.file_path)
            for sheet in workbook.worksheets:
                outfp.write(f"Sheet: {sheet.title}\n".encode("utf-8"))
                for row in sheet.iter_rows(values_only=True):
                    row_data = "\t".join([str(cell) if cell is not None else "" for cell in row])
                    outfp.write(f"{row_data}\n".encode("utf-8"))
                outfp.write("\n".encode("utf-8"))
            outfp.flush()
            os.fsync(outfp.fileno())
            temp_file_path = outfp.name
        return temp_file_path

    def _extract_text_from_xls(self):
        temp_file_path = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as outfp:
            workbook = xlrd.open_workbook(self.file_path)
            for sheet_index in range(workbook.nsheets):
                sheet = workbook.sheet_by_index(sheet_index)
                outfp.write(f"Sheet: {sheet.name}\n".encode("utf-8"))
                for row_index in range(sheet.nrows):
                    row = sheet.row_values(row_index)
                    row_data = "\t".join([str(cell) if cell is not None else "" for cell in row])
                    outfp.write(f"{row_data}\n".encode("utf-8"))
                outfp.write("\n".encode("utf-8"))
            outfp.flush()
            os.fsync(outfp.fileno())
            temp_file_path = outfp.name
        return temp_file_path
