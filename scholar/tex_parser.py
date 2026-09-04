"""
Scholar Studio — TeX Source Parser (v2)

Comprehensive rewrite with improved extraction for:
- Authors: comma / \\and / \\And / authblk, superscript & macro cleaning
- Titles: macro resolution, formatting strip, line-break handling
- Year: conference style, arXiv ID, preamble scan
- Formulas: \\[...\\] display math, more environments
- Sections: cleaner text with aggressive LaTeX stripping
"""
import re
import os
import json
import hashlib
import tarfile
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from collections import Counter

from .parsed_schema import build_parsed_document


class TeXParser:
    """Parse TeX source archives into structured JSON."""

    # --- Regex patterns ---
    RE_DOCTYPE = re.compile(r"\\documentclass(\[.*?\])?\{.*?\}")
    RE_INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")
    RE_TITLE = re.compile(
        r"\\(?:title|icmltitle|icmltitlerunning)"
        r"(?:\[.*?\])?"                       # optional [short title]
        r"\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}"  # 2-level nested braces
    )
    # Author: capture up to 3 levels of brace nesting
    RE_AUTHOR = re.compile(
        r"\\author(?:\*?)\{((?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*)\}"
    )
    RE_ICML_AUTHOR = re.compile(
        r"\\icmlauthor\{((?:[^{}]|\{[^{}]*\})*)\}\{([^}]*)\}"
    )
    RE_NEWCOMMAND = re.compile(
        r"\\(?:re)?newcommand\{?\\([a-zA-Z@]+)\}?"
        r"(?:\[(\d)\])?"                      # optional arg count
        r"\{((?:[^{}]|\{[^{}]*\})*)\}"        # definition (1-level nested)
    )
    RE_DEF = re.compile(
        r"\\def\\([a-zA-Z@]+)\{([^}]*)\}"    # simple \def\name{value}
    )
    RE_DATE = re.compile(r"\\date\{([^}]*)\}")
    RE_YEAR_COMMENT = re.compile(r"%\s*(?:year|date)\s*[:=]?\s*(\d{4})", re.I)
    RE_ACM_YEAR = re.compile(r"\\acmYear\{(\d{4})\}")
    # Broader conference style year pattern
    RE_CONF_STYLE_YEAR = re.compile(
        r"\\usepackage(?:\[.*?\])?\{.*?"
        r"(?:icml|nips|neurips|cvpr|iccv|eccv|aaai|ijcai|acl|emnlp|naacl|"
        r"coling|sigir|kdd|www|wsdm|cikm|recsys|mlsys|aistats|uai|alt)"
        r"[_-]?(\d{4})"
        r".*?\}",
        re.I
    )
    # Conference name with year in any context (e.g., "NeurIPS 2023", "ICLR 2022")
    RE_CONF_YEAR_TEXT = re.compile(
        r"\b(NeurIPS|NIPS|ICML|ICLR|AAAI|IJCAI|CVPR|ICCV|ECCV|"
        r"ACL|EMNLP|NAACL|COLING|KDD|SIGIR|WWW|AISTATS|UAI|"
        r"MLSys|RecSys|CIKM|WSDM|ALT)\s*(\d{4})\b",
        re.I
    )
    # arXiv ID patterns: arXiv:YYMM.NNNNN or arxiv.org/abs/YYMM.NNNNN
    RE_ARXIV_ID = re.compile(
        r"arxiv(?:\.org/abs/)?[:/]?\s*(\d{2})(0[1-9]|1[0-2])\.\d{4,5}",
        re.I
    )
    # Full arXiv ID extraction: captures YYMM.NNNNN
    RE_ARXIV_ID_FULL = re.compile(
        r"arxiv(?:\.org/abs/)?[:/]?\s*(\d{4}\.\d{4,5})(?:v\d+)?",
        re.I
    )
    RE_ABSTRACT = re.compile(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL
    )
    RE_SECTION = re.compile(
        r"\\((?:sub)*section|chapter|part)\*?\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}"
    )
    RE_CITATION = re.compile(
        r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|Cite)\*?"
        r"(?:\[.*?\])?\{([^}]+)\}"
    )
    RE_BIBITEM = re.compile(r"\\bibitem(?:\[.*?\])?\{([^}]+)\}")

    # Math environments (expanded)
    MATH_ENVS = [
        "equation", "equation*", "align", "align*",
        "gather", "gather*", "multline", "multline*",
        "eqnarray", "eqnarray*", "displaymath",
        "flalign", "flalign*", "alignat", "alignat*",
        "subequations",
    ]
    RE_MATH_ENV = re.compile(
        r"\\begin\{(" + "|".join(re.escape(e) for e in MATH_ENVS) + r")\}"
        r"(.*?)"
        r"\\end\{\1\}",
        re.DOTALL,
    )
    RE_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
    # \[ ... \] display math (new)
    RE_BRACKET_MATH = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
    RE_LABEL = re.compile(r"\\label\{([^}]+)\}")

    # Formatting commands to strip from titles and headings
    STRIP_FORMATTING_CMDS = [
        "textbf", "textit", "emph", "underline", "textsc", "texttt",
        "textsf", "textrm", "textmd", "textnormal", "textup",
        "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathcal",
        "mathbb", "mathfrak", "boldsymbol", "bm",
        "Large", "LARGE", "huge", "Huge", "large", "small", "footnotesize",
        "normalsize", "scriptsize", "tiny",
        "centering", "raggedright", "raggedleft",
        "bfseries", "itshape", "slshape", "scshape", "mdseries",
        "bf", "it", "sl", "sc", "rm", "sf", "tt",
        "MakeUppercase", "MakeLowercase", "uppercase", "lowercase",
    ]
    RE_STRIP_FORMAT = re.compile(
        r"\\(?:" + "|".join(STRIP_FORMATTING_CMDS) + r")\b\s*",
        re.I,
    )
    # Commands with arguments to strip entirely (keep arg content)
    RE_STRIP_CMD_KEEP_ARG = re.compile(
        r"\\(?:" + "|".join(STRIP_FORMATTING_CMDS) + r")\{([^}]*)\}"
    )

    # Noise commands to remove from section content
    SECTION_NOISE_CMDS = re.compile(
        r"\\(?:"
        r"vspace\*?\{[^}]*\}|"
        r"vskip[^\\]*|"
        r"hspace\*?\{[^}]*\}|"
        r"phantom\{[^}]*\}|"
        r"vphantom\{[^}]*\}|"
        r"hphantom\{[^}]*\}|"
        r"label\{[^}]*\}|"
        r"index\{[^}]*\}|"
        r"footnote\{[^}]*\}|"
        r"marginpar\{[^}]*\}|"
        r"tag\{[^}]*\}|"
        r"notag|"
        r"nonumber|"
        r"newpage|"
        r"clearpage|"
        r"pagebreak|"
        r"bigskip|"
        r"medskip|"
        r"smallskip|"
        r"par\b|"
        r"noindent|"
        r"centering|"
        r"raggedright|"
        r"raggedleft"
        r")",
        re.I,
    )

    # Venue detection patterns
    VENUE_PATTERNS = [
        (re.compile(r"neurips|nips", re.I), "NeurIPS"),
        (re.compile(r"icml", re.I), "ICML"),
        (re.compile(r"iclr", re.I), "ICLR"),
        (re.compile(r"aaai", re.I), "AAAI"),
        (re.compile(r"ijcai", re.I), "IJCAI"),
        (re.compile(r"acl\b", re.I), "ACL"),
        (re.compile(r"emnlp", re.I), "EMNLP"),
        (re.compile(r"naacl", re.I), "NAACL"),
        (re.compile(r"cvpr", re.I), "CVPR"),
        (re.compile(r"iccv", re.I), "ICCV"),
        (re.compile(r"eccv", re.I), "ECCV"),
        (re.compile(r"siggraph", re.I), "SIGGRAPH"),
        (re.compile(r"acmsig|acmart", re.I), "ACM"),
        (re.compile(r"ieee", re.I), "IEEE"),
        (re.compile(r"nature", re.I), "Nature"),
        (re.compile(r"science\b", re.I), "Science"),
        (re.compile(r"arxiv", re.I), "arXiv"),
        (re.compile(r"jmlr", re.I), "JMLR"),
        (re.compile(r"tpami", re.I), "TPAMI"),
        (re.compile(r"ijcv", re.I), "IJCV"),
        (re.compile(r"kdd", re.I), "KDD"),
        (re.compile(r"sigir", re.I), "SIGIR"),
        (re.compile(r"coling", re.I), "COLING"),
        (re.compile(r"mlsys", re.I), "MLSys"),
        (re.compile(r"aistats", re.I), "AISTATS"),
        (re.compile(r"recsys", re.I), "RecSys"),
    ]

    # Affiliation keywords for filtering
    AFFILIATION_KEYWORDS = [
        "department", "university", "institute", "college",
        "school", "laboratory", "lab", "address", "faculty",
        "center", "centre", "research", "division",
        "technology", "engineering", "science", "affiliation",
        "correspondence", "email", "http", "www",
        "inc.", "inc,", "corp.", "corp,", "ltd", "llc",
        "academy", "digital economy",
        "google", "microsoft", "meta", "openai", "deepmind",
        "anthropic", "nvidia", "intel", "ibm", "amazon",
        "facebook", "apple", "twitter", "salesforce",
        "ai language", "ai research", "ai team",
        "tech limited", "villa tech",
        # Common city/location patterns in affiliations
        "mountain view", "palo alto", "san francisco", "san jose",
        "los angeles", "new york", "menlo park", "redwood city",
        "san diego",
    ]

    def __init__(self):
        pass

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------

    def parse_archive(self, archive_path: Path, paper_id: str) -> dict:
        """Parse a paper from a tar.gz or zip archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            self._extract(archive_path, tmpdir)
            return self._parse_directory(tmpdir, paper_id, str(archive_path))

    def parse_directory(self, dir_path: Path, paper_id: str) -> dict:
        """Parse from an already-extracted directory of .tex files."""
        return self._parse_directory(dir_path, paper_id, str(dir_path))

    def _parse_directory(
        self,
        dir_path: Path,
        paper_id: str,
        source_description: str,
    ) -> dict:
        tex_files = sorted(dir_path.rglob("*.tex"))
        if not tex_files:
            raise ValueError(f"No .tex files found in {source_description}")
        main_file = self._find_main_tex(tex_files)
        if main_file is None:
            raise ValueError(
                f"No main .tex file (with \\documentclass) found among {len(tex_files)} files"
            )
        warnings = []
        all_content = self._resolve_inputs_with_diagnostics(
            main_file,
            dir_path,
            set(),
            warnings,
        )
        warnings.extend(self._syntax_warnings(all_content, main_file, dir_path))
        raw_main = self._read_source(main_file, dir_path, warnings)

        macros = self._extract_macros(raw_main)
        all_macros = self._extract_macros(all_content)
        for k, v in all_macros.items():
            if k not in macros:
                macros[k] = v

        legacy = {
            "paper_id": paper_id,
            "title": self._extract_title(raw_main, macros),
            "authors": self._extract_authors(raw_main, macros),
            "year": self._extract_year(raw_main, all_content),
            "venue": self._detect_venue(raw_main, all_content),
            "arxiv_id": self._extract_arxiv_id(raw_main, all_content),
            "abstract": self._extract_abstract(all_content, macros),
            "sections": self._extract_sections(all_content, macros),
            "formulas": self._extract_formulas(all_content),
            "citations": self._extract_citations(all_content),
            "bibliography": self._extract_bibliography(all_content, dir_path),
            "tex_file_count": len(tex_files),
            "main_tex_file": main_file.relative_to(dir_path).as_posix(),
        }
        if legacy["arxiv_id"] and not legacy["venue"]:
            legacy["venue"] = "arXiv"
        derived_text = "\n".join(
            [
                legacy.get("abstract") or "",
                *(section["content"] for section in legacy["sections"]),
            ]
        )
        losses = []
        if len(derived_text) != len(all_content):
            losses.append({
                "code": "clean_text_projection",
                "stage": "normalize",
                "operation": "derive",
                "message": "Search text is a lossy derived view of the expanded TeX source.",
                "input_chars": len(all_content),
                "output_chars": len(derived_text),
                "locator": {
                    "path": main_file.relative_to(dir_path).as_posix(),
                },
            })
        source_files = []
        for tex_file in tex_files:
            raw = tex_file.read_bytes()
            try:
                raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                encoding = "utf-8-replacement"
            source_files.append({
                "path": tex_file.relative_to(dir_path).as_posix(),
                "encoding": encoding,
                "sha256": f"sha256:{hashlib.sha256(raw).hexdigest()}",
                "byte_length": len(raw),
            })
        return build_parsed_document(
            legacy,
            source={
                "kind": "tex",
                "main_file": main_file.relative_to(dir_path).as_posix(),
                "files": source_files,
            },
            warnings=warnings,
            losses=losses,
        )

    # ---------------------------------------------------------------
    # Extraction helpers
    # ---------------------------------------------------------------

    @staticmethod
    def _extract(archive_path: Path, dest: Path):
        """Extract tar.gz or zip to dest directory."""
        path_str = str(archive_path).lower()
        if path_str.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(dest, filter="data")
        elif path_str.endswith(".tar"):
            with tarfile.open(archive_path, "r:") as tf:
                tf.extractall(dest, filter="data")
        elif path_str.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                # Prevent Zip Slip: validate all entries stay within dest
                dest_resolved = dest.resolve()
                for member in zf.namelist():
                    member_path = (dest / member).resolve()
                    if not str(member_path).startswith(str(dest_resolved)):
                        raise ValueError(f"Unsafe zip entry (path traversal): {member}")
                zf.extractall(dest)
        else:
            raise ValueError(f"Unsupported archive format: {archive_path}")

    @staticmethod
    def _find_main_tex(tex_files: list[Path]) -> Optional[Path]:
        """Find the main .tex file (the one with \\documentclass).
        
        Improved: prefer the file that has \\input{} references (orchestrator),
        since standalone large files often miss chapter content.
        """
        candidates = []
        for f in tex_files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "\\documentclass" in content:
                input_count = len(re.findall(r"\\(?:input|include)\{", content))
                candidates.append((f, len(content), input_count))
        if not candidates:
            return None
        
        # Sort: prefer files with most \input references, then by size as tiebreaker
        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
        
        # If the top candidate has 0 inputs but others also have 0,
        # fall back to largest file (original behavior)
        return candidates[0][0]

    def _resolve_inputs(
        self, tex_file: Path, base_dir: Path, visited: set
    ) -> str:
        """Recursively resolve \\input{} and \\include{} to build full content."""
        return self._resolve_inputs_with_diagnostics(
            tex_file,
            base_dir,
            visited,
            [],
        )

    def _read_source(
        self,
        tex_file: Path,
        base_dir: Path,
        warnings: list[dict],
    ) -> str:
        try:
            return tex_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append({
                "code": "decode_replacement",
                "stage": "read",
                "severity": "warning",
                "message": "Invalid UTF-8 bytes were replaced while decoding TeX.",
                "locator": {
                    "path": tex_file.relative_to(base_dir).as_posix(),
                },
            })
            return tex_file.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            warnings.append({
                "code": "source_read_failed",
                "stage": "read",
                "severity": "error",
                "message": str(error),
                "locator": {
                    "path": tex_file.relative_to(base_dir).as_posix(),
                },
            })
            return ""

    def _resolve_inputs_with_diagnostics(
        self,
        tex_file: Path,
        base_dir: Path,
        visited: set,
        warnings: list[dict],
    ) -> str:
        real = tex_file.resolve()
        if real in visited:
            warnings.append({
                "code": "cyclic_input",
                "stage": "include",
                "severity": "warning",
                "message": "A cyclic TeX input was skipped.",
                "locator": {
                    "path": tex_file.relative_to(base_dir).as_posix(),
                },
            })
            return ""
        visited.add(real)
        content = self._read_source(tex_file, base_dir, warnings)
        base_resolved = base_dir.resolve()

        def replace_input(match):
            ref = match.group(1).strip()
            for ext in [".tex", ""]:
                candidate = tex_file.parent / (ref + ext)
                if candidate.exists() and candidate.resolve().is_relative_to(base_resolved):
                    return self._resolve_inputs_with_diagnostics(
                        candidate,
                        base_dir,
                        visited,
                        warnings,
                    )
                candidate = base_dir / (ref + ext)
                if candidate.exists() and candidate.resolve().is_relative_to(base_resolved):
                    return self._resolve_inputs_with_diagnostics(
                        candidate,
                        base_dir,
                        visited,
                        warnings,
                    )
                for found in base_dir.rglob(ref + ext):
                    return self._resolve_inputs_with_diagnostics(
                        found,
                        base_dir,
                        visited,
                        warnings,
                    )
            warnings.append({
                "code": "missing_input",
                "stage": "include",
                "severity": "warning",
                "message": f"TeX input could not be resolved: {ref}",
                "locator": {
                    "path": tex_file.relative_to(base_dir).as_posix(),
                    "target": ref,
                },
            })
            return f"% [MISSING INPUT: {ref}]"

        resolved = self.RE_INPUT.sub(replace_input, content)
        return resolved

    @staticmethod
    def _syntax_warnings(
        content: str,
        main_file: Path,
        base_dir: Path,
    ) -> list[dict]:
        locator = {"path": main_file.relative_to(base_dir).as_posix()}
        warnings = []
        unescaped = re.sub(r"\\[{}]", "", content)
        if unescaped.count("{") != unescaped.count("}"):
            warnings.append({
                "code": "unbalanced_braces",
                "stage": "parse",
                "severity": "warning",
                "message": "Expanded TeX contains unbalanced braces.",
                "locator": locator,
            })
        begins = Counter(re.findall(r"\\begin\{([^}]+)\}", content))
        ends = Counter(re.findall(r"\\end\{([^}]+)\}", content))
        for environment in sorted(set(begins) | set(ends)):
            if begins[environment] == ends[environment]:
                continue
            warnings.append({
                "code": "unbalanced_environment",
                "stage": "parse",
                "severity": "warning",
                "message": (
                    f"TeX environment has {begins[environment]} begin marker(s) "
                    f"and {ends[environment]} end marker(s): {environment}"
                ),
                "locator": locator,
            })
        return warnings

    def _clean_tex(self, text: str) -> str:
        """Remove common TeX noise for cleaner text extraction."""
        # Remove comments
        text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
        # Remove formatting commands with args (keep content)
        text = re.sub(
            r"\\(?:textbf|textit|emph|underline|textsc|texttt|textsf|"
            r"textrm|mathrm|mathbf|mathit|mathsf|mathtt|mathcal|"
            r"mathbb|mathfrak|boldsymbol|bm)\{([^}]*)\}",
            r"\1", text,
        )
        # Remove \newcommand, \renewcommand definitions
        text = re.sub(r"\\(?:re)?newcommand\{[^}]*\}(\[\d\])?\{[^}]*\}", "", text)
        # Remove standalone formatting commands (no args)
        text = re.sub(
            r"\\(?:Large|LARGE|huge|Huge|large|small|footnotesize|normalsize|"
            r"scriptsize|tiny|centering|raggedright|raggedleft|"
            r"bfseries|itshape|slshape|scshape|mdseries|"
            r"bf|it|sl|sc|rm|sf|tt)\b\s*",
            "", text,
        )
        return text

    # ---------------------------------------------------------------
    # Macro handling
    # ---------------------------------------------------------------

    def _extract_macros(self, content: str) -> dict:
        """Extract \\newcommand and \\def definitions for macro resolution."""
        macros = {}
        # \newcommand / \renewcommand
        for m in self.RE_NEWCOMMAND.finditer(content):
            name = m.group(1)
            value = m.group(3)
            macros[name] = value
        # \def (simple cases only)
        for m in self.RE_DEF.finditer(content):
            name = m.group(1)
            value = m.group(2)
            if name not in macros:  # newcommand takes priority
                macros[name] = value
        return macros

    def _resolve_macros(self, text: str, macros: dict) -> str:
        """Replace custom macros with their definitions (multi-pass)."""
        for _ in range(3):  # up to 3 passes for nested macros
            changed = False
            for name, value in macros.items():
                old_text = text
                # Use re.sub with lambda to avoid backreference interpretation in value
                text = re.sub(
                    r"\\" + re.escape(name) + r"(?![a-zA-Z@])",
                    lambda m, v=value: v,
                    text,
                )
                if text != old_text:
                    changed = True
            if not changed:
                break
        return text

    # ---------------------------------------------------------------
    # Metadata extractors
    # ---------------------------------------------------------------

    def _extract_title(self, content: str, macros: dict = None) -> Optional[str]:
        """Extract title with macro resolution and formatting cleanup."""
        if macros is None:
            macros = self._extract_macros(content)

        # Remove comments first
        clean = re.sub(r"(?<!\\)%.*$", "", content, flags=re.MULTILINE)

        for pattern in [
            r"\\icmltitlerunning\{([^}]+)\}",
            r"\\icmltitle\{([^}]+)\}",
            r"\\title(?:\[.*?\])?\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}",
        ]:
            m = re.search(pattern, clean, re.DOTALL)
            if not m:
                continue
            title = m.group(1).strip()

            # 1. Resolve custom macros
            title = self._resolve_macros(title, macros)

            # 2. Replace \\ (line breaks) with space
            title = re.sub(r"\\\\", " ", title)

            # 3. Remove LaTeX environments entirely (minipage, center, etc.)
            for env in ["minipage", "center", "tabular", "figure", "picture"]:
                title = re.sub(
                    r"\\begin\{" + env + r"\}.*?\\end\{" + env + r"\}",
                    " ", title, flags=re.DOTALL,
                )

            # 4. Remove \includegraphics[...]{...} and \includegraphics[...]...
            title = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}", "", title)
            title = re.sub(r"\\includegraphics\[[^\]]*\][^{]*", "", title)

            # 4b. Remove \color{...}, \textcolor{...}{...}, \colorbox{...}{...}
            title = re.sub(r"\\(?:color|textcolor|colorbox|definecolor)\{[^}]*\}(?:\{[^}]*\})?", "", title)

            # 5. Strip formatting commands with args (keep content)
            title = self.RE_STRIP_CMD_KEEP_ARG.sub(r"\1", title)

            # 6. Strip standalone formatting commands
            title = self.RE_STRIP_FORMAT.sub("", title)

            # 7. Remove \vspace, \hspace, \rule, \hrule, \vskip, box commands
            title = re.sub(r"\\[vh]space\*?\{[^}]*\}", "", title)
            title = re.sub(r"\\rule(?:\[[^\]]*\])?\{[^}]*\}\{[^}]*\}", "", title)
            title = re.sub(r"\\[a-zA-Z]+box(?:\[[^\]]*\])?\{[^}]*\}", "", title)
            title = re.sub(r"\\(?:hrule|vskip|parskip|hfill|vfill|bigskip|medskip|smallskip)\b[^\\]*?", " ", title)

            # 8. Remove \xspace and other zero-arg spacing macros
            title = re.sub(r"\\(?:xspace|thinspace|negthinspace|enspace|quad|qquad)\b", "", title)

            # 9. Remove logo/brand macros that didn't resolve (keep name, drop command)
            title = re.sub(r"\\(?:LogoWithText|olmoLogoWithText|emojidizzy|icon)\b(?:\{[^}]*\})*", "", title)

            # 10. Replace escaped special chars
            title = title.replace("\\&", "&")
            title = title.replace("\\%", "%")
            title = title.replace("\\#", "#")
            title = title.replace("\\$", "$")
            title = title.replace("\\_", "_")
            title = title.replace("\\@", "")  # \@ is a LaTeX sentence-end flag, remove

            # 11. Remove remaining generic commands (keep args)
            title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)

            # 12. Remove any remaining standalone \commandname (including non-alpha like \, \; etc.)
            title = re.sub(r"\\[a-zA-Z]+", " ", title)
            title = re.sub(r"\\[,;:!. ]", " ", title)  # LaTeX spacing commands

            # 13. Clean braces, brackets and whitespace
            title = re.sub(r"[{}]", "", title)
            title = re.sub(r"#\d", "", title)  # remove #1, #2 parameter markers
            # Remove filename-like artifacts (fig/path.png, etc.) — no \b needed
            title = re.sub(r"(?:fig|figs|img|images)/\S+\.(?:png|jpg|jpeg|pdf|eps|svg)", "", title)
            title = re.sub(r"\s+", " ", title).strip()

            # 14. Fix colon prefix (": Title" -> "Title")
            title = re.sub(r"^:\s*", "", title)

            # 15. Strip leading/trailing non-alpha noise
            title = re.sub(r"^[\s\-\.,:;]+", "", title)

            if title and len(title) > 3:
                return title
        return None

    def _extract_authors(self, content: str, macros: dict = None) -> list[str]:
        """Extract authors with comprehensive separator and cleaning support."""
        if macros is None:
            macros = self._extract_macros(content)

        # Remove comments
        clean = re.sub(r"(?<!\\)%.*$", "", content, flags=re.MULTILINE)

        # ---- Strategy 1: \icmlauthor{name}{affil} (ICML format) ----
        icml_matches = self.RE_ICML_AUTHOR.findall(clean)
        if icml_matches:
            authors = []
            for name_raw, _email in icml_matches:
                name = self._clean_author_name(name_raw, macros)
                if name and not self._is_affiliation(name):
                    authors.append(name)
            if authors:
                return authors[:20]

        # ---- Strategy 2: Standard \author{...} ----
        authors = []
        for m in self.RE_AUTHOR.finditer(clean):
            raw = m.group(1)
            raw = self._resolve_macros(raw, macros)
            block_authors = self._parse_author_block(raw)
            authors.extend(block_authors)

        if authors:
            return authors[:20]

        # ---- Strategy 3: authblk — multiple \author{} commands ----
        # When authblk package is used, each \author{} has one name
        acmart_authors = re.findall(r"\\author(?:\*?)\{([^}]+)\}", clean)
        if len(acmart_authors) > 1:
            for a in acmart_authors:
                name = self._clean_author_name(a, macros)
                if name and not self._is_affiliation(name):
                    authors.append(name)
            return authors[:20]

        # ---- Strategy 4: Single \author{} with one name ----
        for a in acmart_authors:
            name = self._clean_author_name(a, macros)
            if name and not self._is_affiliation(name):
                authors.append(name)

        return authors[:20]

    def _parse_author_block(self, raw: str) -> list[str]:
        """Parse an author block from \\author{...} content.
        
        Handles comma-separated, \\and, \\And, \\\\, \\quad separators.
        Also handles key-value formats: name={John}, affiliation={MIT}
        """
        # Handle key-value author format: name={John Smith}, affiliation={MIT}
        # Extract just the name= values and discard affiliation=
        kv_names = re.findall(r"name\s*=\s*\{([^}]*)\}", raw)
        if kv_names:
            # This is a key-value format author block
            authors = []
            for n in kv_names:
                cleaned = self._clean_author_name(n.strip(), {})
                if cleaned:
                    authors.append(cleaned)
            if authors:
                return authors

        # Extract names from tabular environments BEFORE removing them
        # (some papers put all authors inside tabular cells with \textbf{})
        tabular_contents = re.findall(
            r"\\begin\{tabular\*?\}(?:\[[^\]]*\])?\{[^}]*\}(.*?)\\end\{tabular\*?\}",
            raw, flags=re.DOTALL,
        )
        tabular_names = []
        for tc in tabular_contents:
            # Split on & (cell separators) and \\ (row separators)
            cells = re.split(r"&|\\\\", tc)
            for cell in cells:
                cell = cell.strip()
                # Names are typically in \textbf{} in tabular cells
                bf_match = re.search(r"\\textbf\{([^}]+)\}", cell)
                if bf_match:
                    name_candidate = bf_match.group(1).strip()
                    if name_candidate and not self._is_affiliation(name_candidate):
                        cleaned = self._clean_author_name(name_candidate, {})
                        if cleaned:
                            tabular_names.append(cleaned)
        if tabular_names:
            # Found names in tabulars — use them directly
            seen = set()
            authors = []
            for n in tabular_names:
                if n not in seen:
                    seen.add(n)
                    authors.append(n)
            return authors

        # Remove tabular environments entirely
        raw = re.sub(r"\\begin\{tabular\*?\}(?:\[[^\]]*\])?\{[^}]*\}.*?\\end\{tabular\*?\}", "", raw, flags=re.DOTALL)

        # Remove \thanks{...} and other note commands (including \samethanks, \cofirstthanks, etc.)
        # Handle nested/escaped braces: \thanks{Corresponding: \{deng.595\}@osu.edu}
        raw = re.sub(r"\\(?:thanks|footnote)\{(?:[^{}]|\{[^{}]*\})*\}", "", raw)
        raw = re.sub(r"\\[a-zA-Z]*thanks\b(?:\{[^}]*\})?", ",", raw)  # catches \samethanks, replace with comma
        raw = re.sub(r"\\(?:protect)?footnotemark(?:\[[^\]]*\])?", "", raw)
        raw = re.sub(r"\\same\b", ",", raw)  # \same (same affiliation marker) → comma separator

        # Strip \text{} and basic formatting early (CRITICAL: before comma/name detection)
        raw = re.sub(r"\\text\{([^}]*)\}", r"\1", raw)
        raw = re.sub(
            r"\\(?:textbf|textit|emph|underline|textsc|texttt|textsf|"
            r"textrm|mathrm|mathbf|mathit|textsuperscript|textsubscript)\{([^}]*)\}",
            r"\1", raw,
        )
        # Replace \textless and \textgreater with empty/space
        raw = raw.replace("\\textless", " ")
        raw = raw.replace("\\textgreater", " ")
        # Replace ~ with space early (for name splitting)
        raw = raw.replace("~", " ")
        # \space produces a literal space
        raw = re.sub(r"\\space\b", " ", raw)
        raw = re.sub(r"\\enspace\b", " ", raw)

        # Remove email addresses (including \texttt{email} patterns)
        raw = re.sub(r"\\texttt\{[^}]*@[^}]*\}", "", raw)
        raw = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "", raw)

        # Remove \url{...}
        raw = re.sub(r"\\url\{[^}]*\}", "", raw)

        # Remove affiliation-related constructs
        raw = re.sub(r"\\(?:affil|affiliation|address|institution)\*?\{[^}]*\}", "", raw)

        # Remove \authorinfo{...}{...}{...} (ACM style)
        raw = re.sub(r"\\authorinfo\{[^}]*\}\{[^}]*\}\{[^}]*\}", "", raw)

        # Replace spacing-based separators with comma (common in NeurIPS/ICLR)
        # \quad, \qquad, \enskip, \hspace{...} between names
        raw = re.sub(r"\\(?:quad|qquad|enskip)\b", ",", raw)
        raw = re.sub(r"\\[vh]space\*?\{[^}]*\}", ",", raw)
        # Replace \; (thick space) with comma when between author names
        raw = re.sub(r"\\;", ",", raw)

        # Remove inline math $...$ (superscripts like $^\star$, $\dagger$ etc.)
        raw = re.sub(r"\$[^$]*\$", "", raw)

        # Remove nested formatting: \textnormal{\textsuperscript{1}} etc.
        # Run twice to handle 2-level nesting
        for _ in range(2):
            raw = re.sub(
                r"\\(?:textnormal|textbf|textit|emph|underline|textsc|texttt|"
                r"textsf|textrm|mathrm|mathbf|mathit|textsuperscript|textsubscript)"
                r"\{([^}]*)\}",
                r"\1", raw,
            )
        # Remove remaining braces content (catches any deeper nesting)
        raw = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", raw)
        raw = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", raw)  # second pass for nesting

        # Split on known separators: \and, \And, \AND
        parts = re.split(r"\\[aA][nN][dD]\b", raw)

        # Further split each part
        expanded_parts = []
        for part in parts:
            # Split on \\ (line breaks)
            subparts = re.split(r"\\\\", part)
            for sub in subparts:
                sub_stripped = sub.strip()
                # Skip lines that look like pure affiliations (no person names)
                if sub_stripped and not self._line_has_names(sub_stripped):
                    continue
                if self._looks_like_comma_authors(sub):
                    expanded_parts.extend(self._split_comma_authors(sub))
                else:
                    expanded_parts.append(sub)

        authors = []
        seen = set()
        for part in expanded_parts:
            name = self._clean_author_name(part, {})
            if name and not self._is_affiliation(name) and name not in seen:
                seen.add(name)
                authors.append(name)

        return authors

    @staticmethod
    def _line_has_names(text: str) -> bool:
        """Check if a line contains person-name-like tokens (not just affiliation text).
        
        A person name token: starts with uppercase, is 2+ chars, and is not a known
        affiliation keyword. At least 2 such tokens should be present for a line
        to be considered as containing names.
        """
        # Remove LaTeX commands for cleaner analysis
        clean = re.sub(r"\\[a-zA-Z]+(?:\{[^}]*\}|\[[^\]]*\])*", " ", text)
        clean = re.sub(r"[{}$^~]", " ", clean)
        words = [w.strip(".,;:!?") for w in clean.split() if len(w.strip(".,;:!?")) >= 2]
        
        AFFIL_WORDS = {
            "google", "deepmind", "microsoft", "meta", "openai", "anthropic",
            "nvidia", "amazon", "facebook", "apple", "salesforce", "twitter",
            "university", "institute", "department", "school", "college",
            "laboratory", "lab", "research", "center", "centre",
            "inc", "corp", "ltd", "llc", "inc.", "corp.",
            "company", "group", "systems", "technologies",
            "switzerland", "china", "usa", "uk", "japan", "korea",
            "beijing", "shanghai", "london", "york", "francisco",
            "ai", "fair", "tech", "limited",
            # City/location tokens commonly found in affiliations
            "mountain", "view", "berkeley", "cambridge", "oxford", "boston",
            "seattle", "austin", "pittsburgh", "toronto", "montreal",
            "zurich", "berlin", "paris", "tokyo", "seoul", "palo", "alto",
            "menlo", "park", "redmond", "angeles", "jose", "diego",
            "francisco", "york", "washington", "virginia",
            # State/country abbreviations
            "ca", "ny", "ma", "wa", "tx", "pa", "il", "on", "qc",
            "us", "cn", "jp", "kr", "de", "fr",
        }
        
        name_count = 0
        for w in words:
            if not w or not w[0].isupper():
                continue
            if w.lower() in AFFIL_WORDS:
                continue
            # Looks like a person name word
            name_count += 1
        
        return name_count >= 2

    @staticmethod
    def _looks_like_comma_authors(text: str) -> bool:
        """Check if text looks like comma-separated author names."""
        # Need at least one comma
        if "," not in text:
            return False
        # Split by comma and check if parts look like names
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) < 2:
            return False
        # At least 2 parts should start with an uppercase letter (name-like)
        name_like = sum(1 for p in parts if p and p[0].isupper())
        return name_like >= 2

    @staticmethod
    def _split_comma_authors(text: str) -> list[str]:
        """Split comma-separated author names, handling edge cases."""
        parts = [p.strip() for p in text.split(",") if p.strip()]
        result = []
        i = 0
        while i < len(parts):
            part = parts[i]
            # Check if this is "Last, First" format (single name split by comma)
            # Heuristic: if part is a single word and next part is also single word,
            # and both are short, they might be "Last, First"
            if (i + 1 < len(parts)
                    and len(part.split()) == 1
                    and len(parts[i + 1].split()) == 1
                    and part[0].isupper()
                    and parts[i + 1][0].isupper()):
                # Could be "Last, First" — but also could be two separate authors
                # If the next comma-separated chunk also looks like a name, treat separately
                # Only merge if we see a pattern like "Smith, John" followed by another pair
                if i + 2 < len(parts) and len(parts[i + 2].split()) <= 2:
                    # Likely "Last, First, Last2, First2" pattern
                    merged = f"{parts[i+1]} {part}"
                    result.append(merged)
                    i += 2
                    continue
            result.append(part)
            i += 1
        return result

    def _clean_author_name(self, raw: str, macros: dict) -> Optional[str]:
        """Clean a raw author name string into a presentable name."""
        if not raw or not raw.strip():
            return None

        name = raw
        # Resolve macros
        if macros:
            name = self._resolve_macros(name, macros)

        # 1. Replace ~ with space EARLY (before other processing)
        name = name.replace("~", " ")

        # 2. Remove \text{...} (keep content, ~ already replaced)
        name = re.sub(r"\\text\{([^}]*)\}", r"\1", name)

        # 3. Remove LaTeX commands but keep their text content
        name = re.sub(
            r"\\(?:textbf|textit|emph|underline|textsc|texttt|textsf|"
            r"textrm|mathrm|mathbf|mathit|textsuperscript|textsubscript)\{([^}]*)\}",
            r"\1", name,
        )

        # 4. Remove \centerline, \parbox, \makebox, etc. (keep content)
        name = re.sub(r"\\(?:centerline|parbox|makebox|mbox|hbox|vbox)(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", name)

        # 5. Remove \thanks{...}, \footnote{...}, \footnotemark[...] entirely
        name = re.sub(r"\\(?:thanks|footnote)\{[^}]*\}", "", name)
        name = re.sub(r"\\(?:protect)?footnotemark(?:\[[^\]]*\])?", "", name)

        # 6. Remove spacing commands with args: \hspace{6mm}, \vspace{0.2cm}, etc.
        name = re.sub(r"\\[vh]space\*?\{[^}]*\}", " ", name)
        name = re.sub(r"\\[hH]skip[^\s]*", " ", name)

        # 7. Remove standalone spacing commands: \quad, \qquad, \enskip, \xspace etc.
        name = re.sub(r"\\(?:quad|qquad|enskip|thinspace|negthinspace|xspace|,) ?", " ", name)
        # \space and \enspace produce actual spaces — replace with space
        name = re.sub(r"\\(?:space|enspace)\b", " ", name)

        # 8. Remove size commands: \scriptsize, \footnotesize, \small, etc.
        name = re.sub(
            r"\\(?:scriptsize|footnotesize|small|normalsize|large|Large|LARGE|"
            r"huge|Huge|tiny)\b\s*",
            "", name,
        )

        # 9. Remove font series/shape: \bfseries, \itshape, \mdseries, etc.
        name = re.sub(r"\\(?:bfseries|itshape|slshape|scshape|mdseries)\b\s*", "", name)

        # 10. Remove standalone formatting commands
        name = self.RE_STRIP_FORMAT.sub("", name)

        # 11. Remove inline math $...$ entirely (handles $^{1,2,4}$, $\dagger$, etc.)
        name = re.sub(r"\$[^$]*\$", "", name)

        # 12. Remove remaining standalone superscript markers
        name = re.sub(r"\^[^{}\s]*", "", name)

        # 13. Remove remaining standalone $ signs
        name = re.sub(r"\$", "", name)

        # 14. Remove symbol commands: \dagger, \ddagger, \star, \ast, etc.
        name = re.sub(r"\\(?:dagger|ddagger|star|ast|diamond|triangle|bullet|circ)\b", "", name)

        # 14b. Remove author-role/note commands: \affil*, \thanks, \footnote, \same, etc.
        name = re.sub(r"\\(?:affil|affilsup|affilmark|authfn|authnote|thanks|footnote)\w*\{[^}]*\}", "", name)
        name = re.sub(r"\\[a-zA-Z]*thanks\b(?:\{[^}]*\})?", "", name)  # catches \samethanks
        name = re.sub(r"\\(?:affil|affilsup|affilmark|authfn|authnote|same|and)\b", "", name)

        # 14c. Handle LaTeX accent commands: \'{a} → a, \"{u} → u, \`{e} → e, etc.
        name = re.sub(r"\\['\"`^~=.|]{([^}])\}", r"\1", name)
        name = re.sub(r"\\['\"`^~=.|](\w)", r"\1", name)  # \'a without braces

        # 15. Remove remaining generic single-arg commands (keep content)
        name = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", name)

        # 16. Remove table-related noise (tabular, &, etc.)
        name = re.sub(r"\\(?:begin|end)\{tabular\*?\}", "", name)
        name = re.sub(r"[&]", " ", name)

        # 17. Remove dimension literals: 6mm, 0.23cm, 1.2pt, [2mm], etc.
        name = re.sub(r"\[?\d+\.?\d*\s*(?:mm|cm|pt|em|ex|in)\]?", " ", name)

        # 18. Remove affiliation number markers: standalone digits or comma-separated digits
        #     (but be careful not to remove numbers in names like "III" or "Jr.")
        name = re.sub(r"(?:^|[\s,;])\d+(?:\s*,\s*\d+)*(?=\s|$|[,;])", " ", name)

        # 18b. Remove affiliation numbers directly attached to names:
        #      "Min1" → "Min", "Wang2" → "Wang", "Lewis4" → "Lewis"
        #      Does NOT affect Roman numerals (III, IV) or name-like tokens
        name = re.sub(r"(\b[A-Za-z]{2,})\d{1,3}\b", r"\1", name)

        # 18b2. Remove bracket superscript affiliation markers: [1], [2], [1,2], [1, 2, 3]
        name = re.sub(r"\s*\[\d[\d,\s]*\]", "", name)

        # 18b3. Re-apply: remove digits directly attached after bracket removal
        #       (e.g., "Chen [1]1" → "Chen 1" after 18b2, need to strip trailing "1")
        name = re.sub(r"(\b[A-Za-z]{2,})\d{1,3}\b", r"\1", name)
        # Also strip standalone trailing digits
        name = re.sub(r"\s+\d{1,3}\s*$", "", name)

        # 18c. Remove font family/series/shape commands (no braces, must be handled before backslash removal)
        name = re.sub(
            r"\\(?:normalfont|sffamily|rmfamily|ttfamily|upshape|slshape|scshape|"
            r"itshape|bfseries|mdseries|bf|it|rm|sf|tt|sc|sl|up|md)\b\s*",
            "", name,
        )

        # 18d. Remove citation-instruction text that may leak from \author blocks
        name = re.sub(r"(?i)please\s+cite\s+this\s+.*$", "", name)
        name = re.sub(r"(?i)full\s+authorship\s+.*$", "", name)
        name = re.sub(r"(?i)correspondence\s+regarding\s+.*$", "", name)

        # 19. Remove any remaining standalone \commandname (BEFORE stripping backslashes)
        name = re.sub(r"\\[a-zA-Z]+", " ", name)
        # Remove backslash-based punctuation: \; \: \! etc.
        name = re.sub(r"\\[,;:! ]", " ", name)

        # 20. Remove dollar signs, braces, tildes, remaining backslashes
        name = re.sub(r"[{}\\]", "", name)

        # 21. Remove common footnote symbols (unicode)
        name = re.sub(r"[*\u2020\u2021\u00a7\u00b6\u2660\u2663\u2662\u2661]", "", name)

        # 22. Clean whitespace
        name = re.sub(r"\s+", " ", name).strip()

        # 24. Remove leading/trailing punctuation artifacts
        name = re.sub(r"^[,\s;:.]+", "", name)
        name = re.sub(r"[,\s;:.]+$", "", name)

        # 25. Remove "equal contribution", "project lead", "joint first author" notes
        name = re.sub(r"(?i)equal\s*contrib\w*", "", name)
        name = re.sub(r"(?i)corresponding\s*author\w*", "", name)
        name = re.sub(r"(?i)work\s+done\s+(?:at|during)\s+.*", "", name)
        name = re.sub(r"(?i)project\s*lead\b", "", name)
        name = re.sub(r"(?i)joint\s+first\s+author\b", "", name)
        name = re.sub(r"(?i)directional\s+lead\b", "", name)
        name = re.sub(r"(?i)equal\s+advis\w*", "", name)

        # 25b. Remove "name=" or standalone "name " prefix from author formats
        name = re.sub(r"(?i)^name\s*=\s*", "", name)
        name = re.sub(r"(?i)^name\s+", "", name)  # "name Colin Raffel" -> "Colin Raffel"

        # 25c. Remove trailing sentences/descriptions after author name
        # (e.g., "Colin Raffel. A description of each author's contribution...")
        # If name has a period followed by long text, keep only before the period
        if ". " in name and len(name) > 30:
            # Check if the text after ". " looks like a description (not a name part)
            parts = name.split(". ", 1)
            if parts[0] and re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$", parts[0].strip()):
                name = parts[0].strip()

        # 26. Clean again after removals
        name = re.sub(r"\s+", " ", name).strip()
        name = re.sub(r"^[,\s;:.]+", "", name)
        name = re.sub(r"[,\s;:.]+$", "", name)

        # Filter if name is too short or looks like noise
        if not name or len(name) < 2:
            return None

        # Must contain at least one letter
        if not re.search(r"[a-zA-Z\u00C0-\u024F\u4e00-\u9fff]", name):
            return None

        return name

    def _is_affiliation(self, text: str) -> bool:
        """Check if text looks like an affiliation rather than a person name."""
        lower = text.lower()
        for kw in self.AFFILIATION_KEYWORDS:
            # Use word boundary for short keywords (<=4 chars) to avoid
            # false positives like "lab" matching inside "Oquab"
            if len(kw) <= 4:
                if re.search(r'\b' + re.escape(kw) + r'\b', lower):
                    return True
            else:
                if kw in lower:
                    return True
        # Check if it looks like an address (contains numbers and street-like words)
        if re.search(r"\b\d{2,}\b", text) and any(
            w in lower for w in ["street", "road", "avenue", "ave", "blvd", "drive", "way"]
        ):
            return True
        # "City Name, ST" pattern (e.g., "Mountain View, CA")
        if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}$", text.strip()):
            return True
        # Standalone US state abbreviation or short location (1-2 words, all uppercase or short)
        stripped = text.strip()
        if re.match(r"^[A-Z]{2}$", stripped):  # "CA", "NY" etc.
            return True
        # All-uppercase 2-5 letter abbreviations likely org/institution codes (UAB, MIT, etc.)
        if re.match(r"^[A-Z]{2,5}$", stripped) and not re.match(r"^[A-Z][a-z]+", stripped):
            return True
        # Pattern like "[2]International Digital Economy Academy" — starts with [N]
        if re.match(r"^\[\d+\]", stripped):
            return True
        return False

    # ---------------------------------------------------------------
    # Year extraction (significantly expanded)
    # ---------------------------------------------------------------

    def _extract_year(self, main_content: str, full_content: str) -> Optional[int]:
        """Extract publication year with multiple fallback strategies."""

        # 1. \acmYear{YYYY}
        m = self.RE_ACM_YEAR.search(main_content)
        if m:
            return int(m.group(1))

        # 2. Conference style file year (e.g., icml2016, neurips_2023, iclr2015)
        m = self.RE_CONF_STYLE_YEAR.search(main_content)
        if m:
            return int(m.group(1))

        # 3. Broad: ANY \usepackage or \documentclass option containing a 4-digit year
        #    Catches: iclr2024_conference, colm2024_conference, naaclhlt2018,
        #             nips14submit_e, etc.
        for pattern in [
            r"\\usepackage(?:\[[^\]]*\])?\{([^}]*\d{4}[^}]*)\}",
            r"\\documentclass(?:\[([^\]]*)\])?\{([^}]*)\}",
        ]:
            for pm in re.finditer(pattern, main_content, re.I):
                matched_text = " ".join(g for g in pm.groups() if g)
                years = re.findall(r"\b(20[012]\d|19\d\d)\b", matched_text)
                if years:
                    recent = [y for y in years if 2015 <= int(y) <= 2026]
                    if recent:
                        return int(recent[0])
                    return int(years[0])

        # 4. Comment-based year (% year: 2023, % date = 2023)
        m = self.RE_YEAR_COMMENT.search(main_content)
        if m:
            return int(m.group(1))

        # 5. \date{...}
        m = self.RE_DATE.search(main_content)
        if m:
            date_str = m.group(1)
            years = re.findall(r"\b(20[012]\d|19\d\d)\b", date_str)
            if years:
                return int(years[0])

        # 6. Conference + year text pattern in preamble (e.g., "NeurIPS 2023")
        preamble = main_content[:8000]
        m = self.RE_CONF_YEAR_TEXT.search(preamble)
        if m:
            return int(m.group(2))

        # 7. arXiv ID year: arXiv:2301.xxxxx -> 2023
        arxiv_match = self.RE_ARXIV_ID.search(main_content)
        if arxiv_match:
            yy = int(arxiv_match.group(1))
            if yy >= 90:
                return 1900 + yy
            else:
                return 2000 + yy

        # 7b. Explicit year macro definitions: \def\confYear{2023}, \newcommand{\year}{2023}, etc.
        for pattern in [
            r"\\def\\[a-zA-Z]*[Yy]ear\{(\d{4})\}",
            r"\\(?:newcommand|renewcommand)\{?\\[a-zA-Z]*[Yy]ear\}?\{(\d{4})\}",
            r"\\def\\[a-zA-Z]*[Cc]onf[a-zA-Z]*[Yy]ear\{(\d{4})\}",
            r"\\(?:newcommand|renewcommand)\{?\\[a-zA-Z]*[Cc]onf[a-zA-Z]*[Yy]ear\}?\{(\d{4})\}",
        ]:
            m = re.search(pattern, main_content[:15000])
            if m:
                y = int(m.group(1))
                if 2010 <= y <= 2026:
                    return y

        # 8. Scan preamble for any 4-digit year (2015-2026)
        # Filter out years that appear to be part of dataset/version names or citation keys
        preamble = main_content[:8000]
        # Strip citation commands to avoid picking up years from cite keys
        preamble_cleaned = re.sub(r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|bibitem)\*?(?:\[[^\]]*\])?\{[^}]*\}", "", preamble)
        year_matches = list(re.finditer(r"\b(20[12]\d)\b", preamble_cleaned))
        if year_matches:
            # Collect years that are NOT preceded by a hyphen or part of a dataset name
            filtered_years = []
            for ym in year_matches:
                y = ym.group(1)
                start = ym.start()
                # Check if preceded by hyphen (dataset version like ImageNet-2012)
                if start > 0 and preamble_cleaned[start - 1] in "-_":
                    continue
                # Check if part of a command name context
                preceding = preamble_cleaned[max(0, start - 30):start]
                if re.search(r"(?:dataset|version|benchmark|challenge|track)\b[^.]*$", preceding, re.I):
                    continue
                filtered_years.append(y)
            if filtered_years:
                counter = Counter(filtered_years)
                most_common = counter.most_common(1)[0]
                return int(most_common[0])

        # 9. Check full content for conference-year patterns
        m = self.RE_CONF_YEAR_TEXT.search(full_content)
        if m:
            return int(m.group(2))

        # 10. arXiv ID in full content
        arxiv_match = self.RE_ARXIV_ID.search(full_content)
        if arxiv_match:
            yy = int(arxiv_match.group(1))
            if yy >= 90:
                return 1900 + yy
            else:
                return 2000 + yy

        # 11. Last resort: scan first 15000 chars of full content for years
        full_snippet = full_content[:15000]
        full_snippet_cleaned = re.sub(
            r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|bibitem)\*?(?:\[[^\]]*\])?\{[^}]*\}",
            "", full_snippet,
        )
        years = re.findall(r"\b(20[12]\d)\b", full_snippet_cleaned)
        if years:
            # Filter out years preceded by hyphens or underscores (dataset versions)
            filtered = []
            for ym in re.finditer(r"\b(20[12]\d)\b", full_snippet_cleaned):
                y = ym.group(1)
                start = ym.start()
                if start > 0 and full_snippet_cleaned[start - 1] in "-_":
                    continue
                filtered.append(y)
            if filtered:
                counter = Counter(filtered)
                most_common = counter.most_common(1)[0]
                return int(most_common[0])

        return None

    def _detect_venue(self, main_content: str, full_content: str) -> Optional[str]:
        header = main_content[:5000]
        for pattern, venue in self.VENUE_PATTERNS:
            if pattern.search(header):
                return venue
        sty_refs = re.findall(r"\\usepackage.*?\{([^}]+)\}", header)
        for ref in sty_refs:
            for pattern, venue in self.VENUE_PATTERNS:
                if pattern.search(ref):
                    return venue
        return None

    def _extract_arxiv_id(self, main_content: str, full_content: str) -> Optional[str]:
        """Extract arXiv ID from TeX content (e.g., arXiv:2401.12345v2 → 2401.12345)."""
        # Search header first (most likely location), then full content
        for text in (main_content[:5000], full_content):
            m = self.RE_ARXIV_ID_FULL.search(text)
            if m:
                return m.group(1)
        return None

    def _extract_abstract(self, content: str, macros: dict = None) -> Optional[str]:
        """Extract abstract with macro resolution and comprehensive cleaning."""
        if macros is None:
            macros = self._extract_macros(content[:5000])

        # Try standard \begin{abstract}...\end{abstract}
        m = self.RE_ABSTRACT.search(content)
        if m:
            abstract = m.group(1).strip()
            abstract = self._clean_abstract_text(abstract, macros)
            if abstract and len(abstract) > 20:
                return abstract

        # Fallback: try \abstract{...} (some custom classes)
        m = re.search(r"\\abstract\{((?:[^{}]|\{[^{}]*\})*)\}", content, re.DOTALL)
        if m:
            abstract = m.group(1).strip()
            abstract = self._clean_abstract_text(abstract, macros)
            if abstract and len(abstract) > 20:
                return abstract

        return None

    def _clean_abstract_text(self, abstract: str, macros: dict) -> str:
        """Clean abstract text with macro resolution and LaTeX stripping."""
        # 1. Resolve custom macros FIRST (e.g., \model -> "AgentBench", \method -> "Ours")
        abstract = self._resolve_macros(abstract, macros)

        # 2. Basic TeX cleanup (comments, font commands)
        abstract = self._clean_tex(abstract)

        # 2b. Handle escaped special chars EARLY (before backslash removal)
        abstract = abstract.replace("\\&", "&")
        abstract = abstract.replace("\\%", "%")
        abstract = abstract.replace("\\#", "#")
        abstract = abstract.replace("\\$", "$")
        abstract = abstract.replace("\\_", "_")
        abstract = abstract.replace("\\@", "")

        # 3. Remove \noindent, \indent (common in abstracts)
        abstract = re.sub(r"\\(?:no)?indent\b", "", abstract)

        # 4. Remove \includegraphics[...]{...} entirely
        abstract = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}", "", abstract)
        abstract = re.sub(r"\\includegraphics\[[^\]]*\][^{]*", "", abstract)

        # 5. Remove \textwidth, \linewidth, \columnwidth dimension references
        abstract = re.sub(r"\\(?:textwidth|linewidth|columnwidth|textheight|paperwidth)\b", "", abstract)

        # 6. Replace citations with [cite]
        abstract = re.sub(
            r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear)\*?(?:\[[^\]]*\])?\{[^}]*\}",
            "[cite]", abstract,
        )

        # 7. Replace cross-references with [ref]
        abstract = re.sub(r"\\(?:ref|eqref|autoref|cref|Cref)\{[^}]*\}", "[ref]", abstract)

        # 8. Remove \em (standalone emphasis marker)
        abstract = re.sub(r"\\em\b\s*", "", abstract)

        # 9. Remove \url{...} (keep URL text)
        abstract = re.sub(r"\\url\{([^}]*)\}", r"\1", abstract)
        # Remove \href{url}{text} -> keep text
        abstract = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", abstract)

        # 10. Remove \xspace and spacing macros
        abstract = re.sub(r"\\(?:xspace|thinspace|negthinspace|enspace|quad|qquad)\b", "", abstract)

        # 11. Remove \color{...}, \textcolor{...}{...}
        abstract = re.sub(r"\\(?:color|textcolor)\{[^}]*\}(?:\{[^}]*\})?", "", abstract)

        # 12. Remove dimension literals: 0.05in, -0.05in, etc.
        abstract = re.sub(r"-?\d+\.?\d*\s*(?:mm|cm|pt|em|ex|in)\b", "", abstract)

        # 12b. Remove inline math $...$
        abstract = re.sub(r"\$[^$\n]+?\$", "", abstract)

        # 13. Remove remaining generic commands (keep content) — 2 passes for nesting
        for _ in range(2):
            abstract = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", abstract)

        # 14. Remove remaining standalone commands
        abstract = re.sub(r"\\[a-zA-Z]+", " ", abstract)

        # 14b. Remove remaining backslash-based punctuation
        abstract = re.sub(r"\\[,;:!. ]", " ", abstract)

        # 15. Clean braces, brackets, remaining backslashes
        abstract = re.sub(r"[{}\\]", "", abstract)

        # 16. Remove remaining $ signs
        abstract = abstract.replace("$", "")

        # 17. Collapse whitespace
        abstract = re.sub(r"\s+", " ", abstract).strip()

        # 19. Clean leading/trailing punctuation artifacts
        abstract = re.sub(r"^[\s\-\.,:;]+", "", abstract)
        abstract = re.sub(r"[\s\-\.,:;]+$", "", abstract)

        return abstract

    # ---------------------------------------------------------------
    # Structure extractors
    # ---------------------------------------------------------------

    def _extract_sections(self, content: str, macros: dict = None) -> list[dict]:
        sections = []
        if macros is None:
            macros = self._extract_macros(content)
        matches = list(self.RE_SECTION.finditer(content))
        for i, m in enumerate(matches):
            level_map = {
                "part": 0, "chapter": 0,
                "section": 1, "subsection": 2,
                "subsubsection": 3,
            }
            cmd = m.group(1)
            heading = m.group(2).strip()
            # Clean heading (comprehensive pipeline)
            heading = self._resolve_macros(heading, macros)
            # Strip \label{...} entirely (before generic cmd stripping keeps arg)
            heading = re.sub(r"\\label\{[^}]*\}", "", heading)
            # Strip \xspace and other zero-arg spacing macros
            heading = re.sub(r"\\(?:xspace|thinspace|negthinspace|enspace|quad|qquad)\b", "", heading)
            # Strip formatting commands with args (keep content)
            heading = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", heading)
            # Strip standalone formatting commands
            heading = self.RE_STRIP_FORMAT.sub("", heading)
            # Remove remaining standalone commands (e.g. \em, \bf)
            heading = re.sub(r"\\[a-zA-Z]+", " ", heading)
            # LaTeX spacing commands: \, \; \: \!
            heading = re.sub(r"\\[,;:!. ]", " ", heading)
            # Escaped special chars
            heading = heading.replace("\\&", "&").replace("\\%", "%")
            heading = heading.replace("\\#", "#").replace("\\$", "$")
            heading = heading.replace("\\_", "_")
            # Clean braces, brackets, trailing backslash
            heading = re.sub(r"[{}]", "", heading)
            heading = re.sub(r"\\\s", " ", heading)  # trailing backslash before space
            heading = re.sub(r"\s+", " ", heading).strip()
            heading = re.sub(r"^[\s\-\.,:;]+", "", heading)
            heading = re.sub(r"[\s\-\.,:;]+$", "", heading)

            level = level_map.get(cmd, 1)

            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_text = content[start:end]

            # --- Aggressive section content cleaning ---
            # 1. Resolve custom macros first
            section_text = self._resolve_macros(section_text, macros)

            # 2. Basic TeX cleanup (comments, font commands)
            section_text = self._clean_tex(section_text)

            # 3. Convert \paragraph{Title} to plain text heading
            section_text = re.sub(r"\\paragraph\*?\{([^}]*)\}", r"\n\1.\n", section_text)
            section_text = re.sub(r"\\subparagraph\*?\{([^}]*)\}", r"\n\1.\n", section_text)

            # 4. Remove noise commands (vspace, label, etc.)
            section_text = self.SECTION_NOISE_CMDS.sub("", section_text)

            # 3. Replace cross-references with [ref]
            section_text = re.sub(
                r"\\(?:ref|eqref|autoref|cref|Cref|nameref|hyperref|secref)\{[^}]*\}",
                "[ref]", section_text,
            )

            # 4. Replace citations with [cite] (including \shortcite)
            section_text = re.sub(
                r"\\(?:cite|citep|citet|citealp|citeauthor|citeyear|shortcite)\*?"
                r"(?:\[[^\]]*\])?\{[^}]*\}",
                "[cite]", section_text,
            )

            # 5. Remove footnote/marginpar/index
            section_text = re.sub(
                r"\\(?:footnote|marginpar|index)\{[^}]*\}", "", section_text,
            )

            # 6. Remove entire environments that are too noisy
            for env in [
                "figure", "figure*", "table", "table*",
                "tikzpicture", "lstlisting", "algorithm", "algorithm*",
                "algorithmic", "algorithmic*",
                "tabular", "tabular*", "tabularx",
                "picture", "minipage", "subfigure", "subtable",
                "verbatim", "Verbatim", "minted",
                "center", "quote", "quotation", "flushleft", "flushright",
                "proof", "remark", "example", "definition", "theorem",
                "lemma", "corollary", "proposition", "note",
            ]:
                section_text = re.sub(
                    r"\\begin\{" + re.escape(env) + r"\}.*?"
                    r"\\end\{" + re.escape(env) + r"\}",
                    "", section_text, flags=re.DOTALL,
                )

            # 6b. Remove conditional blocks: \iffalse...\fi, \if...\else...\fi
            for _ in range(2):  # multiple passes for nested conditionals
                section_text = re.sub(
                    r"\\iffalse\b.*?\\fi\b", "", section_text, flags=re.DOTALL
                )
                section_text = re.sub(
                    r"\\if[a-zA-Z]+\b.*?\\else\b.*?\\fi\b",
                    "", section_text, flags=re.DOTALL,
                )
                section_text = re.sub(
                    r"\\if[a-zA-Z]+\b.*?\\fi\b",
                    "", section_text, flags=re.DOTALL,
                )
            section_text = re.sub(r"\\else\b", "", section_text)
            section_text = re.sub(r"\\fi\b", "", section_text)

            # 6c. Remove \appendix
            section_text = re.sub(r"\\appendix\b", "", section_text)

            # 7. Convert list environments to plain text
            for env in ["itemize", "enumerate", "description"]:
                # Remove \begin/\end markers
                section_text = re.sub(
                    r"\\begin\{" + env + r"\}", "\n", section_text,
                )
                section_text = re.sub(r"\\end\{" + env + r"\}", "\n", section_text)
            # Convert \item[...] or \item to bullet-like prefix
            section_text = re.sub(r"\\item(?:\[[^\]]*\])?\s*", "\n- ", section_text)

            # 8. Strip remaining LaTeX commands but keep their text content
            # Handle \textbf{...}, \emph{...}, etc. (keep content)
            section_text = re.sub(
                r"\\(?:textbf|textit|emph|underline|textsc|texttt|textsf|"
                r"textrm|mathrm|mathbf|mathit|mathsf|mathtt|mathcal|"
                r"mathbb|mathfrak|boldsymbol|bm)\{([^}]*)\}",
                r"\1", section_text,
            )
            # Remove \url{...} -> keep URL text
            section_text = re.sub(r"\\url\{([^}]*)\}", r"\1", section_text)
            # Remove \href{url}{text} -> keep text
            section_text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", section_text)

            # 9. Remove display math environments from section text
            #    (they're already extracted as formulas separately)
            for env in [
                "equation", "equation*", "align", "align*",
                "gather", "gather*", "multline", "multline*",
                "eqnarray", "eqnarray*", "displaymath", "math",
                "alignat", "alignat*", "split",
            ]:
                section_text = re.sub(
                    r"\\begin\{" + re.escape(env) + r"\}.*?"
                    r"\\end\{" + re.escape(env) + r"\}",
                    " [formula] ", section_text, flags=re.DOTALL,
                )
            section_text = re.sub(r"\$\$.+?\$\$", " [formula] ", section_text, flags=re.DOTALL)
            section_text = re.sub(r"\\\[.+?\\\]", " [formula] ", section_text, flags=re.DOTALL)
            # Remove \(...\) inline display math
            section_text = re.sub(r"\\\(.+?\\\)", " [formula] ", section_text, flags=re.DOTALL)

            # 9b. Remove inline math $...$ (keep as [math] placeholder)
            section_text = re.sub(r"\$[^$\n]+?\$", " [math] ", section_text)

            # 10. Remove bibliography-related commands
            section_text = re.sub(r"\\bibliographystyle\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\bibliography\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\nocite\{[^}]*\}", "", section_text)

            # 11. Remove \xspace and other zero-arg spacing macros
            section_text = re.sub(
                r"\\(?:xspace|thinspace|negthinspace|enspace|quad|qquad)\b",
                " ", section_text,
            )

            # 12. Remove TikZ styling commands
            section_text = re.sub(r"\\tikzstyle\{[^}]*\}=\[[^\]]*\]", "", section_text)
            section_text = re.sub(r"\\tikzset\{[^}]*\}", "", section_text)

            # 13. Remove \newlength, \setlength, \settowidth, \addtolength, \setcounter, \let
            section_text = re.sub(r"\\(?:newlength|setlength|settowidth|addtolength)\{[^}]*\}(?:\{[^}]*\})?", "", section_text)
            section_text = re.sub(r"\\setcounter\{[^}]*\}\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\let\\[a-zA-Z]+\\?[a-zA-Z]*", "", section_text)

            # 14. Remove \definecolor and \textcolor (keep text content)
            section_text = re.sub(r"\\definecolor\{[^}]*\}\{[^}]*\}\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\textcolor\{[^}]*\}\{([^}]*)\}", r"\1", section_text)

            # 15. Remove remaining TODO/note commands
            section_text = re.sub(r"\\(?:TODO|todo|FIXME|fixme|note|Note)\{[^}]*\}", "", section_text)

            # 15b. Remove bibliography-related commands and environments
            section_text = re.sub(r"\\bibliographystyle\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\bibliography\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\bibitem(?:\[[^\]]*\])?\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\(?:bibinfo|newblock|howpublished)\b(?:\{[^}]*\})?", "", section_text)
            section_text = re.sub(r"\\thebibliography\b(?:\{[^}]*\})?", "", section_text)
            section_text = re.sub(r"\\end\{thebibliography\}", "", section_text)

            # 15c. Remove \color{...} (but keep \textcolor text content)
            section_text = re.sub(r"\\color\{[^}]*\}", "", section_text)

            # 15d. Remove \newline and similar line-break commands
            section_text = re.sub(r"\\newline\b", "\n", section_text)

            # 15e. Remove table-related commands that leak from tabular environments
            section_text = re.sub(
                r"\\(?:toprule|midrule|bottomrule|cmidrule|booktabs|"
                r"hline|cline|multirow|multicolumn|cellcolor|rowcolor|"
                r"arraystretch|tabcolsep|arraycolsep)\b"
                r"(?:\([^)]*\))?(?:\[[^\]]*\])?(?:\{[^}]*\})*",
                "", section_text,
            )

            # 15f. Remove image/figure residue
            section_text = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\caption(?:\[[^\]]*\])?\{[^}]*\}", "", section_text)
            section_text = re.sub(
                r"\\(?:textwidth|linewidth|columnwidth|textheight|paperwidth|"
                r"textfloatsep|intextsep|floatsep)\b",
                "", section_text,
            )

            # 15g. Remove \linespread, \baselinestretch, \fontsize and similar
            section_text = re.sub(r"\\linespread\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\baselinestretch\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\fontsize\{[^}]*\}\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\renewcommand\{[^}]*\}(?:\[[^\]]*\])?\{[^}]*\}", "", section_text)

            # 15h. Remove \footnoteref, \footnotemark, \autoref, \hyperref, etc.
            section_text = re.sub(r"\\footnoteref\{[^}]*\}", "", section_text)
            section_text = re.sub(r"\\footnotemark(?:\[[^\]]*\])?", "", section_text)
            section_text = re.sub(r"\\autoref\{[^}]*\}", "[ref]", section_text)
            section_text = re.sub(r"\\hyperref\{[^}]*\}", "[ref]", section_text)
            section_text = re.sub(r"\\nameref\{[^}]*\}", "[ref]", section_text)

            # --- Final comprehensive catch-all cleanup ---

            # 16a. Multi-pass: strip \command{arg} → arg (handles nested commands)
            for _ in range(3):
                section_text = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", section_text)

            # 16b. Remove all remaining \commandname (standalone, no args)
            section_text = re.sub(r"\\[a-zA-Z]+", " ", section_text)

            # 16c. LaTeX spacing/punctuation commands: \, \; \: \! \ \& \% \# \$ \_
            section_text = section_text.replace("\\&", "&")
            section_text = section_text.replace("\\%", "%")
            section_text = section_text.replace("\\#", "#")
            section_text = section_text.replace("\\_", "_")
            section_text = section_text.replace("\\@", "")
            section_text = section_text.replace("\\textbackslash", "\\")
            section_text = re.sub(r"\\[,;:!. ]", " ", section_text)

            # 16d. Remove remaining \begin{...} / \end{...} markers
            section_text = re.sub(r"\\begin\{[^}]*\}(?:\[[^\]]*\])?", "", section_text)
            section_text = re.sub(r"\\end\{[^}]*\}", "", section_text)

            # 16e. Remove remaining braces and backslashes
            section_text = re.sub(r"[{}]", "", section_text)
            section_text = section_text.replace("\\", " ")

            # 16f. Remove remaining $ signs
            section_text = section_text.replace("$", "")

            # 17. Collapse whitespace
            section_text = re.sub(r"\n{3,}", "\n\n", section_text)
            section_text = re.sub(r"[ \t]+", " ", section_text)

            if len(section_text) > 10000:
                section_text = section_text[:10000] + "\n... [truncated]"

            sections.append({
                "heading": heading,
                "level": level,
                "content": section_text.strip(),
                "position": i,
            })

        return sections

    def _extract_formulas(self, content: str) -> list[dict]:
        formulas = []
        seen = set()

        def formula_key(latex: str) -> str:
            normalized = re.sub(r"\s+", " ", latex).strip()
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        # Named math environments
        for m in self.RE_MATH_ENV.finditer(content):
            env_type = m.group(1)
            latex = m.group(2).strip()
            label_m = self.RE_LABEL.search(latex)
            label = label_m.group(1) if label_m else None

            key = formula_key(latex)
            if key in seen:
                continue
            seen.add(key)

            formulas.append({
                "latex": latex,
                "label": label,
                "env_type": env_type,
            })

        # Display math $$...$$
        for m in self.RE_DISPLAY_MATH.finditer(content):
            latex = m.group(1).strip()
            key = formula_key(latex)
            if key in seen:
                continue
            seen.add(key)
            label_m = self.RE_LABEL.search(latex)
            formulas.append({
                "latex": latex,
                "label": label_m.group(1) if label_m else None,
                "env_type": "displaymath",
            })

        # Display math \[...\] (new!)
        for m in self.RE_BRACKET_MATH.finditer(content):
            latex = m.group(1).strip()
            key = formula_key(latex)
            if key in seen:
                continue
            seen.add(key)
            label_m = self.RE_LABEL.search(latex)
            formulas.append({
                "latex": latex,
                "label": label_m.group(1) if label_m else None,
                "env_type": "displaymath",
            })

        return formulas

    def _extract_bibliography(self, content: str, file_dir: Path = None) -> list[dict]:
        """Extract structured bibliography entries with title/authors/year/doi.

        Two sources:
        1. .bib files (bibtexparser) — if file_dir available, scan for *.bib
        2. \\bibitem entries in TeX content — regex parse

        Returns: [{ref_key, title, authors, year, doi}, ...]
        """
        entries = []
        seen_keys = set()

        # Source 1: .bib files
        if file_dir and file_dir.exists():
            try:
                import bibtexparser
            except ImportError:
                bibtexparser = None

            if bibtexparser:
                for bib_file in file_dir.rglob("*.bib"):
                    try:
                        raw = bib_file.read_text(encoding="utf-8", errors="ignore")
                        db = bibtexparser.loads(raw)
                        for entry in db.entries:
                            key = entry.get("ID", "").strip()
                            if not key or key in seen_keys:
                                continue
                            seen_keys.add(key)
                            title = re.sub(r"[{}]", "", entry.get("title", "").strip())
                            authors_raw = entry.get("author", "")
                            authors = self._split_bibtex_authors(authors_raw)
                            year = None
                            year_str = entry.get("year", "")
                            if year_str:
                                m = re.search(r"\d{4}", year_str)
                                if m:
                                    year = int(m.group())
                            doi = entry.get("doi", "").strip()
                            if not doi:
                                url = entry.get("url", "")
                                m = re.search(r"doi\.org/(10\.\d+/[^\s]+)", url)
                                if m:
                                    doi = m.group(1)
                            entries.append({
                                "ref_key": key,
                                "title": title,
                                "authors": authors[:5],
                                "year": year,
                                "doi": doi,
                            })
                    except Exception:
                        pass

        # Source 2: \bibitem entries in TeX content
        bib_match = re.search(
            r"\\begin\{thebibliography\}.*?\n(.*?)(?:\\end\{thebibliography\}|$)",
            content, re.DOTALL,
        )
        bib_text = bib_match.group(1) if bib_match else ""

        if bib_text:
            parts = re.split(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", bib_text)
            for i in range(1, len(parts) - 1, 2):
                key = parts[i].strip()
                body = parts[i + 1] if i + 1 < len(parts) else ""

                if key in seen_keys:
                    continue
                seen_keys.add(key)

                title = ""
                title_match = re.search(r"\\bibinfo\{title\}\{([^}]+)\}", body)
                if title_match:
                    title = title_match.group(1)
                else:
                    lines = [l.strip() for l in body.strip().split("\n") if l.strip()]
                    if lines:
                        first = lines[0]
                        first = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", first)
                        first = re.sub(r"[{}\\]", "", first).strip()
                        title = first[:200]

                year = None
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", body)
                if year_match:
                    year = int(year_match.group())

                doi = ""
                doi_match = re.search(r"doi[:\s]*\{?(10\.\d+/[^\s\}]+)", body, re.I)
                if doi_match:
                    doi = doi_match.group(1)

                entries.append({
                    "ref_key": key,
                    "title": title.strip(),
                    "authors": [],
                    "year": year,
                    "doi": doi,
                })

        return entries

    @staticmethod
    def _split_bibtex_authors(authors_raw: str) -> list[str]:
        """Split BibTeX authors without treating name-internal commas as separators."""
        authors = []
        for raw_author in re.split(r"\s+and\s+", authors_raw):
            raw_author = re.sub(r"[{}]", "", raw_author).strip()
            if not raw_author:
                continue
            comma_parts = [
                part.strip()
                for part in raw_author.split(",")
                if part.strip()
            ]
            if len(comma_parts) == 2:
                author = f"{comma_parts[1]} {comma_parts[0]}"
            elif len(comma_parts) == 3:
                author = f"{comma_parts[2]} {comma_parts[0]} {comma_parts[1]}"
            else:
                author = raw_author
            authors.append(re.sub(r"\s+", " ", author).strip())
        return authors

    def _extract_citations(self, content: str) -> list[str]:
        refs = set()
        for m in self.RE_CITATION.finditer(content):
            keys = m.group(1)
            for key in re.split(r"[,\s]+", keys):
                key = key.strip()
                if key and not key.startswith("%"):
                    refs.add(key)
        return sorted(refs)


# ---------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------

def parse_paper(paper_dir: Path, paper_id: str) -> dict:
    """Parse a paper directory containing source.tar.gz or source.zip."""
    parser = TeXParser()

    for name in ["source.tar.gz", "source.tgz", "source.tar", "source.zip"]:
        archive = paper_dir / name
        if archive.exists():
            return parser.parse_archive(archive, paper_id)

    tex_files = list(paper_dir.rglob("*.tex"))
    if tex_files:
        return parser.parse_directory(paper_dir, paper_id)

    raise FileNotFoundError(
        f"No source archive or .tex files found in {paper_dir}"
    )
