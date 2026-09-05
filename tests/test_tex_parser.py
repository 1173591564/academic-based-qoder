"""
Test tex_parser.py — TeX parsing including bibliography extraction.
Uses tmp_path fixtures, no dependency on actual paper data.
"""
import pytest

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from scholar.pdf_parser import PDFParser, parse_pdf
from scholar.parsed_schema import validate_parsed_document
from scholar.tex_parser import TeXParser, parse_paper


@pytest.fixture
def parser():
    return TeXParser()


class TestExtractBibliography:
    """Test _extract_bibliography method (Phase B1)."""

    def test_bib_file_parsing(self, parser, tmp_path):
        """Test .bib file parsing with bibtexparser."""
        bib_content = r"""
@article{vaswani2017,
  title = {Attention Is All You Need},
  author = {Vaswani, Ashish and Shazeer, Noam},
  year = {2017},
  doi = {10.5555/3295222.3295349},
}
@inproceedings{devlin2019,
  title = {BERT: Pre-training of Deep Bidirectional Transformers},
  author = {Devlin, Jacob and Chang, Ming-Wei},
  year = {2019},
}
"""
        bib_file = tmp_path / "refs.bib"
        bib_file.write_text(bib_content, encoding="utf-8")

        entries = parser._extract_bibliography("", tmp_path)

        assert len(entries) >= 2
        # Check first entry
        vaswani = next(e for e in entries if e["ref_key"] == "vaswani2017")
        assert "Attention" in vaswani["title"]
        assert vaswani["year"] == 2017
        assert vaswani["doi"] == "10.5555/3295222.3295349"
        assert len(vaswani["authors"]) >= 2

    def test_bibitem_parsing(self, parser):
        """Test \\bibitem entry parsing from TeX content."""
        tex_content = r"""
\begin{thebibliography}{99}
\bibitem[He et al.(2016)]{he2016deep}
Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun.
\newblock Deep residual learning for image recognition.
\newblock In \emph{CVPR}, 2016.

\bibitem[Goodfellow et al.(2014)]{goodfellow2014gan}
Ian Goodfellow et al.
\newblock Generative adversarial networks.
\newblock In \emph{NeurIPS}, 2014.
\end{thebibliography}
"""
        entries = parser._extract_bibliography(tex_content)

        assert len(entries) >= 2
        keys = [e["ref_key"] for e in entries]
        assert "he2016deep" in keys
        assert "goodfellow2014gan" in keys
        # Check year extraction
        he = next(e for e in entries if e["ref_key"] == "he2016deep")
        assert he["year"] == 2016

    def test_empty_bibliography(self, parser):
        """Test that empty content returns empty list."""
        entries = parser._extract_bibliography("")
        assert entries == []

    def test_bibtex_commas_remain_within_author_names(self, parser, tmp_path):
        """BibTeX commas separate name parts, not people."""
        (tmp_path / "refs.bib").write_text(
            """
@article{names,
  title = {Names},
  author = {Lovelace, Ada and Turing, Alan Mathison},
  year = {2026}
}
""",
            encoding="utf-8",
        )
        entries = parser._extract_bibliography("", tmp_path)
        assert entries[0]["authors"] == [
            "Ada Lovelace",
            "Alan Mathison Turing",
        ]

    def test_doi_extraction_from_url(self, parser, tmp_path):
        """Test DOI extraction from URL field in .bib."""
        bib_content = r"""
@article{test2024,
  title = {Test Paper},
  author = {Test Author},
  year = {2024},
  url = {https://doi.org/10.1000/test123},
}
"""
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bib_content, encoding="utf-8")

        entries = parser._extract_bibliography("", tmp_path)
        assert len(entries) == 1
        assert entries[0]["doi"] == "10.1000/test123"


class TestExtractCitations:
    """Test _extract_citations method."""

    def test_basic_citations(self, parser):
        content = r"Some text \cite{vaswani2017} and \cite{devlin2019, he2016deep}."
        refs = parser._extract_citations(content)
        assert "vaswani2017" in refs
        assert "devlin2019" in refs
        assert "he2016deep" in refs

    def test_bibitems_are_not_citation_mentions(self, parser):
        content = r"\bibitem{key2024} Author, Title, 2024."
        refs = parser._extract_citations(content)
        assert refs == []

    def test_no_citations(self, parser):
        content = "This text has no citations."
        refs = parser._extract_citations(content)
        assert refs == []


class TestTitleExtraction:
    """Test _extract_title method."""

    def test_simple_title(self, parser):
        content = r"\title{Attention Is All You Need}"
        title = parser._extract_title(content, {})
        assert "Attention" in title

    def test_title_with_macros(self, parser):
        content = r"\newcommand{\T}{Transformer}\title{Attention Is All You Need for \T{}}"
        macros = parser._extract_macros(content)
        title = parser._extract_title(content, macros)
        assert "Attention" in title

    def test_deeply_nested_layout_title(self, parser):
        content = r"""
\title{
  \begin{minipage}{0.12\textwidth}
    \includegraphics[width=\textwidth]{logo.pdf}
  \end{minipage}
  \begin{minipage}{0.80\textwidth}
    \begin{center}
      \textbf{AgentPoison: Red-teaming LLM Agents via Poisoning Memory}
    \end{center}
  \end{minipage}
}
"""
        title = parser._extract_title(content, {})

        assert title == "AgentPoison: Red-teaming LLM Agents via Poisoning Memory"


class TestContentCleaning:
    def test_preserves_citation_keys_lists_and_theorems(self, parser):
        content = r"""
\section{Method}
See \citep[Section 2]{vaswani2017,devlin2019} and \ref{sec:proof}.
\begin{itemize}[leftmargin=1em]
\item First contribution.
\end{itemize}
\begin{theorem}[Guarantee]
For every input $x_i$, the method converges.
\end{theorem}
"""
        section = parser._extract_sections(content, {})[0]["content"]

        assert "[cite:vaswani2017; devlin2019]" in section
        assert "[ref:sec:proof]" in section
        assert "leftmargin" not in section
        assert "- First contribution." in section
        assert "the method converges" in section
        assert "[math: x_i]" in section

    def test_long_sections_are_not_truncated(self, parser):
        content = "\\section{Results}\n" + ("complete evidence " * 900)

        section = parser._extract_sections(content, {})[0]["content"]

        assert len(section) > 10000
        assert "[truncated]" not in section

    def test_abstract_preserves_citation_keys_and_math(self, parser):
        content = r"""
\begin{abstract}
We extend \citet{vaswani2017} with objective $\mathcal{L}_{new}$.
\end{abstract}
"""
        abstract = parser._extract_abstract(content, {})

        assert "[cite:vaswani2017]" in abstract
        assert "[math: L_new]" in abstract


class TestYearExtraction:
    def test_conference_style_year_is_attributable(self, parser):
        content = r"""
\documentclass[11pt]{article}
\usepackage[hyperref]{naaclhlt2019}
"""

        year, source = parser._extract_year_with_source(content, content)

        assert year == 2019
        assert source == "tex:conference_style"

    def test_arbitrary_year_in_prose_is_not_metadata(self, parser):
        content = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
We compare against a benchmark released in 2017.
"""

        year, source = parser._extract_year_with_source(content, content)

        assert year is None
        assert source is None


class TestVenueExtraction:
    def test_naacl_is_not_downgraded_to_acl(self, parser):
        content = r"\usepackage[hyperref]{naaclhlt2019}"

        assert parser._detect_venue(content, content) == "NAACL"

    def test_arxiv_derived_venue_is_attributable(self, parser, tmp_path):
        (tmp_path / "main.tex").write_text(
            r"""
\documentclass{article}
\title{An arXiv Paper}
\begin{document}
arXiv:2401.12345
\section{Introduction}
Complete visible content.
""",
            encoding="utf-8",
        )

        result = parser.parse_directory(tmp_path, "paper-arxiv")

        assert result["venue"] == "arXiv"
        assert result["metadata_sources"]["venue"] == "derived:arxiv"


class TestPdfFallback:
    @staticmethod
    def _write_pdf(path, year=2019):
        document = pymupdf.open()
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(72, 72, 540, 720),
            (
                f"Published as a conference paper at ICLR {year}\n"
                "ABSTRACT\n"
                "This paper presents a reliable rendered-text fallback for parsing.\n"
                "1 INTRODUCTION\n"
                "The visible paper text remains available when TeX is only a wrapper.\n"
                "2 RESULTS\n"
                "The fallback recovers complete sections."
            ),
            fontsize=11,
        )
        page.insert_text(
            (30, 500),
            "arXiv:1412.6980v9 [cs.LG] 30 Jan 2017",
            fontsize=8,
            rotate=90,
        )
        document.set_metadata(
            {
                "title": "Rendered Paper Title",
                "author": "Ada Lovelace; Alan Turing",
            }
        )
        document.save(path)
        document.close()

    def test_pdf_fills_tex_wrapper(self, tmp_path):
        (tmp_path / "wrapper.tex").write_text(
            r"""
\documentclass{article}
\usepackage{pdfpages}
\begin{document}
\includepdf[pages=-]{paper.pdf}
\end{document}
""",
            encoding="utf-8",
        )
        self._write_pdf(tmp_path / "paper.pdf")

        result = parse_paper(tmp_path, "paper-1")

        assert result["title"] == "Rendered Paper Title"
        assert result["authors"] == ["Ada Lovelace", "Alan Turing"]
        assert result["year"] == 2019
        assert result["venue"] == "ICLR"
        assert result["arxiv_id"] == "1412.6980"
        assert result["abstract"].startswith("This paper presents")
        assert "2017" not in result["abstract"]
        assert "Jan" not in result["abstract"]
        assert [section["heading"] for section in result["sections"]] == [
            "Introduction",
            "Results",
        ]
        assert result["parse_source"] == "tex+pdf"
        assert result["source"]["kind"] == "hybrid"
        assert {item["path"] for item in result["source"]["files"]} == {
            "paper.pdf",
            "wrapper.tex",
        }
        assert next(
            assertion
            for assertion in result["metadata_assertions"]
            if assertion["field"] == "year"
        )["source_kind"] == "pdf"
        validate_parsed_document(result)

    def test_pdf_front_matter_resolves_year_conflict(self, tmp_path):
        (tmp_path / "main.tex").write_text(
            r"""
\documentclass{article}
\title{Rendered Paper Title}
\author{Ada Lovelace}
\date{2017}
\begin{document}
\begin{abstract}A sufficiently long TeX abstract for parser validation.\end{abstract}
\section{Introduction}
This TeX section contains enough structured text to remain the primary source.
""" + ("More structured content. " * 30),
            encoding="utf-8",
        )
        self._write_pdf(tmp_path / "paper.pdf", year=2019)

        result = parse_paper(tmp_path, "paper-2")

        assert result["year"] == 2019
        assert result["metadata_sources"]["year"] == "pdf:front_matter"
        assert result["metadata_conflicts"]["year"] == {
            "tex": 2017,
            "pdf": 2019,
        }

    def test_pdf_only_uses_visible_title_when_metadata_is_missing(self, tmp_path):
        pdf_path = tmp_path / "visible-title.pdf"
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text(
            (72, 90),
            "A Reliable Visible Paper Title",
            fontsize=18,
        )
        page.insert_text(
            (72, 140),
            "Abstract\nVisible content remains parseable.",
            fontsize=11,
        )
        document.save(pdf_path)
        document.close()

        result = parse_pdf(pdf_path, "paper-3")

        assert result["title"] == "A Reliable Visible Paper Title"
        assert result["metadata_sources"]["title"] == "pdf:visual_title"
        assert result["parse_source"] == "pdf"

        document = parse_paper(tmp_path, "paper-3")
        assert document["source"]["kind"] == "pdf"
        assert document["source"]["main_file"] == "visible-title.pdf"
        validate_parsed_document(document)

    def test_pdf_normalization_rejoins_split_numbered_heading(self):
        assert PDFParser._normalize_text("2\nALGORITHM\nBody") == (
            "2 ALGORITHM\nBody"
        )
