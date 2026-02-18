import json
import re
from pathlib import Path
from typing import Dict, List

import pdfplumber


class PDFQAParser:
    """
    Parses a PDF document to extract Question-Answer pairs based on
    specific 'Question:' and 'Answer:' text markers.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"The file {pdf_path} does not exist.")

    def _extract_raw_text(self) -> str:
        """
        Extracts and concatenates text from all pages in the PDF.
        """
        full_text = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    # extract_text(x_tolerance=1) helps maintain layout integrity
                    text = page.extract_text(x_tolerance=1)
                    if text:
                        full_text.append(text)
        except Exception as e:
            raise RuntimeError(f"Error reading PDF: {e}")

        return "\n".join(full_text)

    def _clean_text(self, text: str) -> str:
        """
        Helper to clean whitespace and newlines from extracted strings.
        """
        # Remove excessive internal whitespace but keep single spaces
        return re.sub(r"\s+", " ", text).strip()

    def parse(self) -> List[Dict[str, str]]:
        """
        Parses the raw text using regex to find Q&A pairs.

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing 'question' and 'answer'.
        """
        raw_text = self._extract_raw_text()

        # Regex Explanation:
        # Question:\s* -> Matches literal 'Question:' followed by whitespace
        # (.*?)         -> Group 1 (Question): Non-greedy match of anything
        # \s*Answer:\s* -> Matches literal 'Answer:' surrounded by whitespace
        # (.*?)         -> Group 2 (Answer): Non-greedy match of anything
        # (?=\nQuestion:|\Z) -> Lookahead: Stop at the next 'Question:' OR end of string

        pattern = re.compile(
            r"Question:\s*(.*?)\s*Answer:\s*(.*?)(?=\nQuestion:|\Z)", re.DOTALL | re.IGNORECASE
        )

        qa_pairs = []

        for match in pattern.finditer(raw_text):
            question_text = self._clean_text(match.group(1))
            answer_text = self._clean_text(match.group(2))

            # Basic validation to ensure we don't capture empty blocks
            if question_text and answer_text:
                qa_pairs.append({"question": question_text, "answer": answer_text})

        return qa_pairs

    def save_to_json(self, output_path: str):
        """
        Parses the PDF and saves the result to a JSON file.
        """
        data = self.parse()
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Successfully saved {len(data)} Q&A pairs to {output_path}")
        except IOError as e:
            print(f"Error saving file: {e}")


# --- Usage Example ---

if __name__ == "__main__":
    # 1. Initialize the parser with your PDF path
    # Replace 'faq_document.pdf' with your actual file path
    parser = PDFQAParser("faq_document.pdf")

    # 2. Extract the data directly
    try:
        qa_data = parser.parse()

        # Print the first 2 parsed items to verify
        print(json.dumps(qa_data[:2], indent=2))

        # 3. Or save to a JSON file
        parser.save_to_json("mft_faq_data.json")

    except Exception as e:
        print(f"An error occurred: {e}")
