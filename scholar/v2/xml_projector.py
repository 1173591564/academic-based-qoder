"""Project LaTeXML documents into typed, evidence-addressable records."""

from collections import defaultdict
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

from .projection_models import (
    ChunkRecord,
    CitationMentionRecord,
    ContentRecord,
    FormulaRecord,
    PaperProjection,
    ReferenceRecord,
    SectionRecord,
    TableRecord,
)
from .xml_utils import (
    CONTENT_KINDS,
    SECTION_KINDS,
    XML_ID,
    YEAR_PATTERN,
    _direct_title,
    _extract_venue,
    _extract_year,
    _mathml_parts,
    _mixed_text,
    _text,
    local_name,
    normalized_name,
    normalized_title,
    semantic_role,
    stable_id,
)


class LaTeXMLProjector:
    """Pure XML-to-record projection with deterministic identifiers."""

    def parse(
        self, paper_id: str, xml_path: Path, namespace: str = "unversioned"
    ) -> PaperProjection:
        def record_id(prefix: str, *parts: str) -> str:
            return stable_id(prefix, namespace, *parts)

        root = ET.parse(xml_path).getroot()
        pointers = self._pointers(root)
        document_order = {id(item): ordinal for ordinal, item in enumerate(root.iter())}
        title = _direct_title(root)
        abstract_element = next(
            (item for item in root if local_name(item.tag) == "abstract"), None
        )
        abstract = _mixed_text(abstract_element) if abstract_element is not None else ""
        authors = []
        seen_authors: set[str] = set()
        for creator in root:
            if local_name(creator.tag) != "creator":
                continue
            person = next(
                (item for item in creator if local_name(item.tag) == "personname"),
                None,
            )
            name = _text(person) or _text(creator)
            author_key = normalized_name(name)
            if name and author_key and author_key not in seen_authors:
                authors.append(name)
                seen_authors.add(author_key)

        sections: list[SectionRecord] = []
        content_nodes: list[ContentRecord] = []
        formulas: list[FormulaRecord] = []
        tables: list[TableRecord] = []
        mentions: list[CitationMentionRecord] = []
        section_by_element: dict[int, str] = {}
        content_by_element: dict[int, str] = {}
        content_document_order: dict[str, int] = {}
        section_ordinal = 0
        content_ordinal = 0

        if abstract_element is not None:
            section_id = record_id("sec", paper_id, "abstract")
            sections.append(
                SectionRecord(
                    id=section_id,
                    parent_id=None,
                    xml_id=abstract_element.attrib.get(XML_ID),
                    node_kind="abstract",
                    semantic_role="abstract",
                    level=0,
                    ordinal=section_ordinal,
                    title="Abstract",
                    xml_pointer=pointers[id(abstract_element)],
                    metadata={"fact_level": "L1"},
                )
            )
            section_ordinal += 1
            section_by_element[id(abstract_element)] = section_id

        def walk_sections(
            element: ET.Element, parent_id: str | None, level: int
        ) -> None:
            nonlocal section_ordinal
            for child in element:
                name = local_name(child.tag)
                if name in SECTION_KINDS:
                    xml_id = child.attrib.get(XML_ID)
                    pointer = pointers[id(child)]
                    section_id = record_id("sec", paper_id, xml_id or pointer)
                    heading = _direct_title(child)
                    record = SectionRecord(
                        id=section_id,
                        parent_id=parent_id,
                        xml_id=xml_id,
                        node_kind=name,
                        semantic_role=semantic_role(heading),
                        level=level,
                        ordinal=section_ordinal,
                        title=heading,
                        xml_pointer=pointer,
                        metadata={"fact_level": "L1"},
                    )
                    sections.append(record)
                    section_by_element[id(child)] = section_id
                    section_ordinal += 1
                    walk_sections(child, section_id, level + 1)
                else:
                    walk_sections(child, parent_id, level)

        walk_sections(root, None, 1)

        def containing_section(
            element: ET.Element, ancestors: list[ET.Element]
        ) -> str | None:
            for ancestor in reversed(ancestors):
                section_id = section_by_element.get(id(ancestor))
                if section_id:
                    return section_id
            return section_by_element.get(id(element))

        def add_content(
            element: ET.Element,
            ancestors: list[ET.Element],
            parent_content_id: str | None = None,
        ) -> str:
            nonlocal content_ordinal
            name = local_name(element.tag)
            pointer = pointers[id(element)]
            xml_id = element.attrib.get(XML_ID)
            content_id = record_id("node", paper_id, xml_id or pointer)
            section_id = containing_section(element, ancestors)
            section = next((item for item in sections if item.id == section_id), None)
            role = section.semantic_role if section else None
            text = _mixed_text(element)
            title_value = ""
            if name in {"table", "figure", "theorem", "proof"}:
                caption = next(
                    (child for child in element if local_name(child.tag) == "caption"),
                    None,
                )
                title_value = _text(caption)
            content_nodes.append(
                ContentRecord(
                    id=content_id,
                    section_id=section_id,
                    parent_id=parent_content_id,
                    xml_id=xml_id,
                    node_kind=name,
                    semantic_role=role,
                    granularity="block",
                    ordinal=content_ordinal,
                    title=title_value,
                    text=text,
                    tex=element.attrib.get("tex"),
                    xml_pointer=pointer,
                    metadata={"fact_level": "L1"},
                )
            )
            content_ordinal += 1
            content_by_element[id(element)] = content_id
            content_document_order[content_id] = document_order[id(element)]
            if name == "table":
                tables.append(
                    self._table(paper_id, element, content_id, pointers, namespace)
                )
            return content_id

        def walk_content(
            element: ET.Element,
            ancestors: list[ET.Element],
            parent_content_id: str | None = None,
        ) -> None:
            name = local_name(element.tag)
            next_parent = parent_content_id
            if name in CONTENT_KINDS:
                next_parent = add_content(element, ancestors, parent_content_id)
                if name in {"p", "table", "figure", "equation", "equationgroup"}:
                    return
            for child in element:
                if local_name(child.tag) not in {
                    "bibliography",
                    "biblist",
                    "bibitem",
                    "TOC",
                    "tags",
                }:
                    walk_content(child, [*ancestors, element], next_parent)

        if abstract_element is not None:
            walk_content(abstract_element, [root])
        for child in root:
            if local_name(child.tag) not in {
                "abstract",
                "bibliography",
                "biblist",
                "TOC",
                "resource",
                "creator",
                "title",
            }:
                walk_content(child, [root])

        parent_map = {child: parent for parent in root.iter() for child in parent}

        def nearest_content(element: ET.Element) -> str | None:
            current = parent_map.get(element)
            while current is not None:
                content_id = content_by_element.get(id(current))
                if content_id:
                    return content_id
                current = parent_map.get(current)
            return None

        def nearest_section(element: ET.Element) -> str | None:
            current = parent_map.get(element)
            while current is not None:
                section_id = section_by_element.get(id(current))
                if section_id:
                    return section_id
                current = parent_map.get(current)
            return None

        def has_ancestor(element: ET.Element, names: set[str]) -> bool:
            current = parent_map.get(element)
            while current is not None:
                if local_name(current.tag) in names:
                    return True
                current = parent_map.get(current)
            return False

        for missing_element in (
            item for item in root.iter() if local_name(item.tag) in CONTENT_KINDS
        ):
            if id(missing_element) in content_by_element:
                continue
            name = local_name(missing_element.tag)
            pointer = pointers[id(missing_element)]
            xml_id = missing_element.attrib.get(XML_ID)
            content_id = record_id("node", paper_id, xml_id or pointer)
            section_id = nearest_section(missing_element)
            section = next((item for item in sections if item.id == section_id), None)
            caption = next(
                (
                    child
                    for child in missing_element
                    if local_name(child.tag) == "caption"
                ),
                None,
            )
            content_nodes.append(
                ContentRecord(
                    id=content_id,
                    section_id=section_id,
                    parent_id=nearest_content(missing_element),
                    xml_id=xml_id,
                    node_kind=name,
                    semantic_role=section.semantic_role if section else None,
                    granularity="block",
                    ordinal=content_ordinal,
                    title=_text(caption),
                    text=_mixed_text(missing_element),
                    tex=missing_element.attrib.get("tex"),
                    xml_pointer=pointer,
                    metadata={"fact_level": "L1"},
                )
            )
            content_by_element[id(missing_element)] = content_id
            content_document_order[content_id] = document_order[id(missing_element)]
            content_ordinal += 1
            if name == "table":
                tables.append(
                    self._table(
                        paper_id,
                        missing_element,
                        content_id,
                        pointers,
                        namespace,
                    )
                )

        content_records = {item.id: item for item in content_nodes}
        for math_index, math in enumerate(
            item for item in root.iter() if local_name(item.tag) == "Math"
        ):
            owner = nearest_content(math)
            if owner is None:
                pointer = pointers[id(math)]
                owner = record_id("node", paper_id, "orphan-math", pointer)
                section_id = nearest_section(math)
                section = next(
                    (item for item in sections if item.id == section_id), None
                )
                record = ContentRecord(
                    id=owner,
                    section_id=section_id,
                    parent_id=None,
                    xml_id=math.attrib.get(XML_ID),
                    node_kind="formula",
                    semantic_role=section.semantic_role if section else None,
                    granularity="inline",
                    ordinal=content_ordinal,
                    title="",
                    text=f"${math.attrib.get('tex', '')}$",
                    tex=math.attrib.get("tex"),
                    xml_pointer=pointer,
                    metadata={"fact_level": "L1", "synthetic_owner": True},
                )
                content_nodes.append(record)
                content_records[owner] = record
                content_document_order[owner] = document_order[id(math)]
                content_ordinal += 1
            math_pointer = pointers[id(math)]
            presentation, content, cmml_valid = _mathml_parts(math)
            formulas.append(
                FormulaRecord(
                    id=record_id(
                        "formula",
                        paper_id,
                        math.attrib.get(XML_ID) or math_pointer,
                        str(math_index),
                    ),
                    content_node_id=owner,
                    xml_id=math.attrib.get(XML_ID),
                    mode=math.attrib.get("mode"),
                    tex=math.attrib.get("tex", ""),
                    presentation_mathml=presentation,
                    content_mathml=content,
                    cmml_valid=cmml_valid,
                    xml_pointer=math_pointer,
                    metadata={"fact_level": "L1"},
                )
            )
        for cite_index, cite in enumerate(
            item for item in root.iter() if local_name(item.tag) == "cite"
        ):
            if has_ancestor(cite, {"bibliography", "biblist", "bibitem"}):
                continue
            owner = nearest_content(cite)
            context_text = content_records[owner].text[:1000] if owner else ""
            cite_pointer = pointers[id(cite)]
            for ref_index, ref in enumerate(
                item for item in cite.iter() if local_name(item.tag) == "ref"
            ):
                target = ref.attrib.get("idref")
                if target:
                    mentions.append(
                        CitationMentionRecord(
                            id=record_id(
                                "mention",
                                paper_id,
                                cite_pointer,
                                str(cite_index),
                                str(ref_index),
                                target,
                            ),
                            content_node_id=owner,
                            reference_xml_id=target,
                            context_text=context_text,
                            xml_pointer=cite_pointer,
                        )
                    )

        content_nodes.sort(key=lambda item: content_document_order[item.id])
        for ordinal, item in enumerate(content_nodes):
            item.ordinal = ordinal

        references = self._references(paper_id, root, pointers, namespace)
        chunks = self._chunks(
            paper_id, title, sections, content_nodes, namespace=namespace
        )
        return PaperProjection(
            paper_id=paper_id,
            title=title,
            normalized_title=normalized_title(title),
            abstract=abstract,
            authors=authors,
            year=_extract_year(root),
            venue=_extract_venue(root),
            sections=sections,
            content_nodes=content_nodes,
            formulas=formulas,
            tables=tables,
            references=references,
            citation_mentions=mentions,
            chunks=chunks,
        )

    def _pointers(self, root: ET.Element) -> dict[int, str]:
        pointers = {id(root): f"/{local_name(root.tag)}[1]"}

        def walk(parent: ET.Element) -> None:
            counts: dict[str, int] = defaultdict(int)
            for child in parent:
                name = local_name(child.tag)
                counts[name] += 1
                pointers[id(child)] = f"{pointers[id(parent)]}/{name}[{counts[name]}]"
                walk(child)

        walk(root)
        return pointers

    def _table(
        self,
        paper_id: str,
        element: ET.Element,
        content_node_id: str,
        pointers: dict[int, str],
        namespace: str,
    ) -> TableRecord:
        pointer = pointers[id(element)]
        xml_id = element.attrib.get(XML_ID)
        caption_element = next(
            (child for child in element if local_name(child.tag) == "caption"), None
        )
        cells = []
        rows = [item for item in element.iter() if local_name(item.tag) == "tr"]
        for row_index, row in enumerate(rows):
            column_index = 0
            for cell in row:
                if local_name(cell.tag) not in {"td", "th"}:
                    continue
                cells.append(
                    {
                        "id": stable_id(
                            "cell",
                            namespace,
                            paper_id,
                            xml_id or pointer,
                            str(row_index),
                            str(column_index),
                        ),
                        "row_index": row_index,
                        "column_index": column_index,
                        "row_span": int(cell.attrib.get("rowspan", "1") or 1),
                        "column_span": int(cell.attrib.get("colspan", "1") or 1),
                        "text": _mixed_text(cell),
                        "is_header": (
                            local_name(cell.tag) == "th"
                            or cell.attrib.get("thead") is not None
                        ),
                        "metadata": {
                            "align": cell.attrib.get("align"),
                            "border": cell.attrib.get("border"),
                        },
                    }
                )
                column_index += int(cell.attrib.get("colspan", "1") or 1)
        return TableRecord(
            id=stable_id("table", namespace, paper_id, xml_id or pointer),
            content_node_id=content_node_id,
            xml_id=xml_id,
            caption=_text(caption_element),
            xml_pointer=pointer,
            cells=cells,
            metadata={"fact_level": "L1"},
        )

    def _references(
        self,
        paper_id: str,
        root: ET.Element,
        pointers: dict[int, str],
        namespace: str,
    ) -> list[ReferenceRecord]:
        records = []
        for item in root.iter():
            if local_name(item.tag) != "bibitem":
                continue
            pointer = pointers[id(item)]
            xml_id = item.attrib.get(XML_ID)
            raw_text = _text(item)
            title_element = next(
                (
                    child
                    for child in item.iter()
                    if local_name(child.tag) in {"bib-title", "title"}
                ),
                None,
            )
            people = [
                _text(child)
                for child in item.iter()
                if local_name(child.tag) in {"bib-name", "personname"} and _text(child)
            ]
            year_match = YEAR_PATTERN.search(raw_text)
            identifiers = {}
            for child in item.iter():
                name = local_name(child.tag)
                if name in {"bib-data", "ref"}:
                    role = child.attrib.get("role", "").lower()
                    value = _text(child)
                    if role in {"doi", "arxiv", "url"} and value:
                        identifiers[role] = value
            records.append(
                ReferenceRecord(
                    id=stable_id("ref", namespace, paper_id, xml_id or pointer),
                    xml_id=xml_id,
                    citation_key=item.attrib.get("key"),
                    raw_text=raw_text,
                    title=_text(title_element) or None,
                    authors=people,
                    year=int(year_match.group(0)) if year_match else None,
                    identifiers=identifiers,
                    xml_pointer=pointer,
                )
            )
        return records

    def _chunks(
        self,
        paper_id: str,
        paper_title: str,
        sections: list[SectionRecord],
        content_nodes: list[ContentRecord],
        max_chars: int = 4_000,
        namespace: str = "unversioned",
    ) -> list[ChunkRecord]:
        section_map = {item.id: item for item in sections}
        node_map = {item.id: item for item in content_nodes}
        child_counts: dict[str, int] = defaultdict(int)
        for node in content_nodes:
            if node.parent_id:
                child_counts[node.parent_id] += 1

        def has_container(node: ContentRecord, kinds: set[str]) -> bool:
            parent_id = node.parent_id
            while parent_id:
                parent = node_map.get(parent_id)
                if parent is None:
                    break
                if parent.node_kind in kinds:
                    return True
                parent_id = parent.parent_id
            return False

        selected = []
        for node in content_nodes:
            if node.node_kind == "p":
                if not has_container(node, {"p", "table", "figure"}):
                    selected.append(node)
            elif node.node_kind in {"table", "figure", "formula"}:
                selected.append(node)
            elif node.node_kind in {"equation", "equationgroup"}:
                if not has_container(node, {"p", "table", "figure"}):
                    selected.append(node)
            elif node.node_kind in {"theorem", "proof"} and not child_counts[node.id]:
                selected.append(node)
        groups: dict[str | None, list[ContentRecord]] = defaultdict(list)
        for node in selected:
            if node.text:
                groups[node.section_id].append(node)
        chunks: list[ChunkRecord] = []
        ordinal = 0
        for section_id, nodes in groups.items():
            section = section_map.get(section_id)
            heading = section.title if section else ""
            prefix = f"[{paper_title}"
            if heading:
                prefix += f" > {heading}"
            prefix += "] "
            current: list[ContentRecord] = []
            current_chars = len(prefix)

            def flush() -> None:
                nonlocal ordinal, current, current_chars
                if not current:
                    return
                content = prefix + "\n\n".join(item.text for item in current)
                chunks.append(
                    ChunkRecord(
                        id=stable_id(
                            "chunk",
                            namespace,
                            paper_id,
                            str(ordinal),
                            hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        ),
                        section_id=section_id,
                        source_node_ids=[item.id for item in current],
                        chunk_kind=(
                            "abstract"
                            if section and section.node_kind == "abstract"
                            else "section"
                        ),
                        semantic_role=section.semantic_role if section else None,
                        ordinal=ordinal,
                        content=content,
                        xml_pointer_start=current[0].xml_pointer,
                        xml_pointer_end=current[-1].xml_pointer,
                        content_sha256=hashlib.sha256(
                            content.encode("utf-8")
                        ).hexdigest(),
                    )
                )
                ordinal += 1
                current = []
                current_chars = len(prefix)

            for node in nodes:
                if current and current_chars + len(node.text) + 2 > max_chars:
                    flush()
                current.append(node)
                current_chars += len(node.text) + 2
            flush()
        return chunks
