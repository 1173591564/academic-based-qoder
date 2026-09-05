"""Normalization and XML helpers for LaTeXML projections."""

import hashlib
import re
import unicodedata
import xml.etree.ElementTree as ET

LTX = "http://dlmf.nist.gov/LaTeXML"
MATHML = "http://www.w3.org/1998/Math/MathML"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
SECTION_KINDS = {
    "part",
    "chapter",
    "section",
    "subsection",
    "subsubsection",
    "appendix",
}
CONTENT_KINDS = {
    "p",
    "table",
    "figure",
    "theorem",
    "proof",
    "equation",
    "equationgroup",
}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalized_space(text: str) -> str:
    return " ".join(text.split())


def normalized_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalized_name(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^\w]+", " ", value).strip()


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"


def semantic_role(title: str) -> str | None:
    value = normalized_title(title)
    rules = (
        ("abstract", ("abstract",)),
        ("introduction", ("introduction", "motivation")),
        ("related_work", ("related work", "prior work", "literature review")),
        ("background", ("background", "preliminaries", "preliminary")),
        (
            "method",
            (
                "method",
                "approach",
                "architecture",
                "framework",
                "model",
                "algorithm",
            ),
        ),
        (
            "experiments",
            ("experiment", "evaluation", "experimental setup", "implementation"),
        ),
        ("results", ("results", "analysis", "ablation")),
        ("limitations", ("limitation", "threats to validity")),
        ("conclusion", ("conclusion", "discussion", "future work")),
        ("appendix", ("appendix", "supplement")),
        ("references", ("reference", "bibliography")),
    )
    for role, needles in rules:
        if any(needle in value for needle in needles):
            return role
    return None


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return normalized_space("".join(element.itertext()))


def _direct_title(element: ET.Element) -> str:
    for child in element:
        if local_name(child.tag) == "title":
            parts = []
            if child.text:
                parts.append(child.text)
            for descendant in child:
                if local_name(descendant.tag) != "tag" and descendant.text:
                    parts.append(descendant.text)
                if descendant.tail:
                    parts.append(descendant.tail)
            return normalized_space(" ".join(parts))
    return ""


def _mixed_text(element: ET.Element) -> str:
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            name = local_name(child.tag)
            if name == "Math":
                tex = child.attrib.get("tex") or _text(child)
                parts.append(f" ${tex}$ ")
            elif name == "cite":
                targets = [
                    ref.attrib.get("idref", "")
                    for ref in child.iter()
                    if local_name(ref.tag) == "ref" and ref.attrib.get("idref")
                ]
                parts.append(" [" + ",".join(targets) + "] ")
            elif name not in {"tags", "tag"}:
                visit(child)
            if child.tail:
                parts.append(child.tail)

    visit(element)
    return normalized_space("".join(parts))


def _extract_year(root: ET.Element) -> int | None:
    candidates = []
    for element in root.iter():
        name = local_name(element.tag)
        if name in {"date", "note"}:
            candidates.append(_text(element))
    for candidate in candidates:
        match = YEAR_PATTERN.search(candidate)
        if match:
            return int(match.group(0))
    return None


def _extract_venue(root: ET.Element) -> str:
    for element in root.iter():
        if local_name(element.tag) != "note":
            continue
        if element.attrib.get("role") in {"journal", "venue", "conference"}:
            return _text(element)
    return ""


def _mathml_parts(element: ET.Element) -> tuple[str | None, str | None, bool | None]:
    math = next((item for item in element if local_name(item.tag) == "math"), None)
    if math is None:
        return None, None, None
    presentation = ET.tostring(math, encoding="unicode")
    content_nodes = [
        item
        for item in math.iter()
        if item.attrib.get(XML_ID, "").endswith(".cmml")
        or local_name(item.tag) in {"apply", "ci", "cn", "csymbol"}
    ]
    content = (
        ET.tostring(content_nodes[0], encoding="unicode") if content_nodes else None
    )
    valid = not any(local_name(item.tag) == "merror" for item in math.iter())
    return presentation, content, valid
