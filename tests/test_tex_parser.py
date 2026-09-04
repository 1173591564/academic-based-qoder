"""
Test tex_parser.py — TeX parsing including bibliography extraction.
Uses tmp_path fixtures, no dependency on actual paper data.
"""
import json
import pytest
from pathlib import Path

from scholar.tex_parser import TeXParser


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
