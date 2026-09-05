"""Conservative PDF fallback for paper metadata and visible text."""

import re
from pathlib import Path
from typing import ClassVar, Optional

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf


class PDFParser:
    """Extract fields that remain reliable in a rendered paper."""

    VENUE_PATTERNS: ClassVar[list[tuple[re.Pattern, str]]] = [
        (re.compile(r"\b(?:NeurIPS|NIPS)\b", re.I), "NeurIPS"),
        (re.compile(r"\bICML\b", re.I), "ICML"),
        (re.compile(r"\bICLR\b", re.I), "ICLR"),
        (re.compile(r"\bAAAI\b", re.I), "AAAI"),
        (re.compile(r"\bIJCAI\b", re.I), "IJCAI"),
        (re.compile(r"\bNAACL(?:-HLT)?\b", re.I), "NAACL"),
        (re.compile(r"\bEMNLP\b", re.I), "EMNLP"),
        (re.compile(r"\bACL\b", re.I), "ACL"),
        (re.compile(r"\bCVPR\b", re.I), "CVPR"),
        (re.compile(r"\bICCV\b", re.I), "ICCV"),
        (re.compile(r"\bECCV\b", re.I), "ECCV"),
        (re.compile(r"\bKDD\b", re.I), "KDD"),
        (re.compile(r"\bSIGIR\b", re.I), "SIGIR"),
        (re.compile(r"\bAISTATS\b", re.I), "AISTATS"),
        (re.compile(r"\bJMLR\b", re.I), "JMLR"),
    ]
    FRONT_MATTER_YEAR = re.compile(
        r"(?:published|accepted|appearing|proceedings|conference paper)"
        r".{0,100}?\b((?:19|20)\d{2})\b",
        re.I | re.DOTALL,
    )
    VENUE_YEAR = re.compile(
        r"\b(?:NeurIPS|NIPS|ICML|ICLR|AAAI|IJCAI|NAACL(?:-HLT)?|"
        r"EMNLP|ACL|CVPR|ICCV|ECCV|KDD|SIGIR|AISTATS)\s*"
        r"((?:19|20)\d{2})\b",
        re.I,
    )
    ARXIV_ID = re.compile(r"arXiv:(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
    NUMBERED_HEADING = re.compile(
        r"^(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z0-9 ,:;()/'&+\-]{2,100})$"
    )
    KNOWN_HEADINGS: ClassVar[set[str]] = {
        "INTRODUCTION",
        "BACKGROUND",
        "RELATED WORK",
        "METHOD",
        "METHODS",
        "METHODOLOGY",
        "APPROACH",
        "MODEL",
        "EXPERIMENTS",
        "EXPERIMENTAL SETUP",
        "RESULTS",
        "DISCUSSION",
        "CONCLUSION",
        "CONCLUSIONS",
        "LIMITATIONS",
        "ACKNOWLEDGMENTS",
        "ACKNOWLEDGEMENTS",
        "REFERENCES",
        "APPENDIX",
    }

    def parse(self, pdf_path: Path, paper_id: str) -> dict:
        with pymupdf.open(pdf_path) as document:
            metadata = document.metadata or {}
            metadata_front = (
                self._normalize_text(document[0].get_text("text"))
                if len(document)
                else ""
            )
            visual_title = (
                self._extract_visual_title(document[0])
                if len(document)
                else None
            )
            raw_page_texts = [
                self._extract_page_text(page)
                for page in document
            ]

        front = raw_page_texts[0] if raw_page_texts else ""
        page_texts = self._remove_repeated_margins(raw_page_texts)
        text = "\n\n".join(page_texts).strip()
        title = self._clean_metadata(metadata.get("title")) or visual_title
        authors = self._parse_authors(metadata.get("author"))
        year = self._extract_year(front)
        venue = self._detect_venue(front) if year else None
        arxiv_id = self._extract_arxiv_id(metadata_front)
        abstract = self._extract_abstract(front)
        metadata_sources = {}
        if title:
            metadata_sources["title"] = (
                "pdf:metadata"
                if self._clean_metadata(metadata.get("title"))
                else "pdf:visual_title"
            )
        if authors:
            metadata_sources["authors"] = "pdf:metadata"
        if year:
            metadata_sources["year"] = "pdf:front_matter"
        if venue:
            metadata_sources["venue"] = "pdf:front_matter"
        if arxiv_id:
            metadata_sources["arxiv_id"] = "pdf:front_matter"
        if abstract:
            metadata_sources["abstract"] = "pdf:visible_text"

        return {
            "paper_id": paper_id,
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "arxiv_id": arxiv_id,
            "abstract": abstract,
            "sections": self._extract_sections(text),
            "formulas": [],
            "citations": [],
            "bibliography": [],
            "pdf_file": pdf_path.name,
            "parse_source": "pdf",
            "metadata_sources": metadata_sources,
            "content_sources": {
                "sections": "pdf",
                "formulas": "unavailable",
                "citations": "unavailable",
                "bibliography": "unavailable",
            },
        }

    @staticmethod
    def _clean_metadata(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        value = re.sub(r"\s+", " ", value).strip()
        if not value or value.lower() in {"untitled", "unknown"}:
            return None
        return value

    def _parse_authors(self, value: Optional[str]) -> list[str]:
        value = self._clean_metadata(value)
        if not value:
            return []
        authors = [
            author.strip()
            for author in re.split(r"\s*(?:;|\band\b)\s*", value)
            if author.strip()
        ]
        if len(authors) == 1 and "," in authors[0]:
            comma_parts = [
                part.strip() for part in authors[0].split(",") if part.strip()
            ]
            if len(comma_parts) > 1 and all(
                len(part.split()) >= 2 for part in comma_parts
            ):
                authors = comma_parts
        return authors[:20]

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.translate(
            str.maketrans(
                {
                    "ﬀ": "ff",
                    "ﬁ": "fi",
                    "ﬂ": "fl",
                    "ﬃ": "ffi",
                    "ﬄ": "ffl",
                }
            )
        )
        text = text.replace("\u00ad", "")
        text = re.sub(r"(?<=\w)-\n\s*(?=[a-z])", "", text)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        normalized = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if (
                re.fullmatch(r"\d+(?:\.\d+)*", line)
                and index + 1 < len(lines)
                and PDFParser._looks_like_heading(lines[index + 1])
            ):
                normalized.append(f"{line} {lines[index + 1]}")
                index += 2
                continue
            normalized.append(line)
            index += 1
        return "\n".join(normalized)

    def _extract_page_text(self, page) -> str:
        blocks = []
        page_width = page.rect.width
        for block in page.get_text("blocks", sort=True):
            x0, y0, x1, y1, text = block[:5]
            width = x1 - x0
            height = y1 - y0
            is_vertical_margin = (
                height > max(width * 2.5, 80)
                and (x1 < page_width * 0.12 or x0 > page_width * 0.88)
            )
            if text.strip() and not is_vertical_margin:
                blocks.append(text)
        return self._normalize_text("\n".join(blocks))

    @staticmethod
    def _extract_visual_title(page) -> Optional[str]:
        lines = []
        for block in page.get_text("dict", sort=True).get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(span.get("text", "") for span in spans).strip()
                if not text or len(text) > 300:
                    continue
                if line.get("bbox", [0, 0])[1] > page.rect.height * 0.45:
                    continue
                size = max((span.get("size", 0) for span in spans), default=0)
                if size:
                    lines.append((line.get("bbox", [0, 0])[1], size, text))

        if not lines:
            return None
        max_size = max(size for _, size, _ in lines)
        candidates = [
            (top, text)
            for top, size, text in lines
            if size >= max_size * 0.9
            and not re.search(
                r"\b(?:arxiv|proceedings|published|preprint)\b", text, re.I
            )
        ]
        title = " ".join(text for _, text in sorted(candidates))
        title = re.sub(r"\s+", " ", title).strip()
        return title if 8 <= len(title) <= 300 else None

    @staticmethod
    def _remove_repeated_margins(page_texts: list[str]) -> list[str]:
        if len(page_texts) < 2:
            return page_texts

        margin_counts = {}
        page_lines = []
        for text in page_texts:
            lines = text.splitlines()
            nonempty = [line for line in lines if line.strip()]
            margins = set(nonempty[:2] + nonempty[-2:])
            for line in margins:
                normalized = re.sub(r"\s+", " ", line).strip()
                if normalized and len(normalized) < 120:
                    margin_counts[normalized] = margin_counts.get(normalized, 0) + 1
            page_lines.append(lines)

        threshold = max(2, len(page_texts) // 2)
        repeated = {
            line for line, count in margin_counts.items() if count >= threshold
        }
        return [
            "\n".join(
                line
                for line in lines
                if re.sub(r"\s+", " ", line).strip() not in repeated
            )
            for lines in page_lines
        ]

    def _extract_year(self, front: str) -> Optional[int]:
        for pattern in (self.FRONT_MATTER_YEAR, self.VENUE_YEAR):
            match = pattern.search(front[:5000])
            if match:
                return int(match.group(1))
        return None

    def _detect_venue(self, front: str) -> Optional[str]:
        header = front[:5000]
        for pattern, venue in self.VENUE_PATTERNS:
            if pattern.search(header):
                return venue
        return None

    def _extract_arxiv_id(self, front: str) -> Optional[str]:
        match = self.ARXIV_ID.search(front)
        return match.group(1) if match else None

    @staticmethod
    def _extract_abstract(front: str) -> Optional[str]:
        match = re.search(
            r"(?:^|\n)\s*ABSTRACT\s*\n(.*?)(?=\n\s*1(?:\.0)?\s+"
            r"(?:INTRODUCTION|Introduction)\b|\n\s*INTRODUCTION\s*\n)",
            front,
            re.DOTALL | re.I,
        )
        if not match:
            return None
        abstract = re.sub(r"\s+", " ", match.group(1)).strip()
        return abstract if len(abstract) > 20 else None

    def _extract_sections(self, text: str) -> list[dict]:
        lines = text.splitlines()
        headings: list[tuple[int, str, int]] = []
        for index, line in enumerate(lines):
            heading = self._heading(line)
            if heading:
                headings.append((index, heading[0], heading[1]))

        sections = []
        for position, (line_index, heading, level) in enumerate(headings):
            end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
            content = self._join_lines(lines[line_index + 1:end])
            if content:
                sections.append(
                    {
                        "heading": heading,
                        "level": level,
                        "content": content,
                        "position": len(sections),
                    }
                )

        if sections:
            return sections

        full_text = self._join_lines(lines)
        if not full_text:
            return []
        return [
            {
                "heading": "Full Text",
                "level": 1,
                "content": full_text,
                "position": 0,
            }
        ]

    def _heading(self, line: str) -> Optional[tuple[str, int]]:
        line = re.sub(r"\s+", " ", line).strip()
        if not line or len(line) > 110:
            return None

        match = self.NUMBERED_HEADING.match(line)
        if match:
            number, heading = match.groups()
            if self._looks_like_heading(heading):
                heading = heading.title() if heading.isupper() else heading
                return heading.strip(), number.count(".") + 1

        normalized = line.upper().rstrip(":")
        if normalized in self.KNOWN_HEADINGS:
            return line.title() if line.isupper() else line, 1
        return None

    @staticmethod
    def _looks_like_heading(value: str) -> bool:
        letters = [char for char in value if char.isalpha()]
        if not letters:
            return False
        uppercase_ratio = sum(char.isupper() for char in letters) / len(letters)
        return uppercase_ratio >= 0.65 or value.istitle()

    @staticmethod
    def _join_lines(lines: list[str]) -> str:
        paragraphs = []
        current = []
        for line in lines:
            line = line.strip()
            if not line:
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                continue
            if re.fullmatch(r"\d+", line):
                continue
            current.append(line)
        if current:
            paragraphs.append(" ".join(current))
        return "\n\n".join(paragraphs).strip()


def parse_pdf(pdf_path: Path, paper_id: str) -> dict:
    return PDFParser().parse(pdf_path, paper_id)
