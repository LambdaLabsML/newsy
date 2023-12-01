import os
from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LTTextContainer, LTChar, LTTextLine


def _get_font_size(paragraph: LTTextContainer):
    sizes = []
    for line in paragraph:
        if isinstance(line, LTChar):
            sizes.append(line.size)
        elif isinstance(line, LTTextLine):
            for char in line:
                if isinstance(char, LTChar):
                    sizes.append(char.size)
    return max(sizes)


class ParsedPdf:
    def __init__(self, path: str) -> None:
        self.path = path

        header_font_size = None
        self.section_names = []
        self._section_start_pages = []

        for i_page, page in enumerate(extract_pages(os.path.expanduser(path))):
            for paragraph in page:
                if isinstance(paragraph, LTTextContainer):
                    font_size = _get_font_size(paragraph)
                    if "Introduction" in paragraph.get_text():
                        header_font_size = font_size

                    if (
                        header_font_size is not None
                        and abs(font_size - header_font_size) < 1e-3
                    ):
                        self.section_names.append(paragraph.get_text().strip())
                        self._section_start_pages.append(i_page)
        self.num_pages = i_page + 1

        self._section_end_pages = []
        for i in range(len(self._section_start_pages) - 1):
            self._section_end_pages.append(self._section_start_pages[i + 1])
        self._section_end_pages.append(self.num_pages)

        # Deleting anything up to abstract
        i_abstract = None
        for i, name in enumerate(self.section_names):
            if "Abstract" in name:
                i_abstract = i
                break
            if "Introduction" in name:
                break
        if i_abstract is not None:
            del self.section_names[: i_abstract + 1]
            del self._section_start_pages[: i_abstract + 1]
            del self._section_end_pages[: i_abstract + 1]

        # Deleting references and everything after
        i_citations = None
        for i, name in enumerate(self.section_names):
            if "Reference" in name or "Citation" in name:
                i_citations = i
                break
        if i_citations is not None:
            del self.section_names[i_citations:]
            del self._section_start_pages[i_citations:]
            del self._section_end_pages[i_citations:]

        assert len(self._section_start_pages) == len(self._section_end_pages)

    def get_section(self, name):
        assert name in self.section_names
        i = self.section_names.index(name)
        start_page = self._section_start_pages[i]
        end_page = self._section_end_pages[i]
        content = extract_text(
            self.path, page_numbers=list(range(start_page, end_page + 1))
        )
        assert name in content
        return content
