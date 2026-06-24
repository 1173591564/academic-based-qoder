import { useMemo } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import type { CitationGraphData } from "../types";

export function CitationGraph({
  data,
  onPaperSelect,
}: {
  data: CitationGraphData;
  onPaperSelect?: (paperId: string) => void;
}) {
  const elements = useMemo(() => {
    if (data.error || !data.nodes) return [];
    const nodes = data.nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.title.length > 40 ? n.title.slice(0, 37) + "..." : n.title,
        year: n.year || "",
        weight: Math.max(20, Math.min(80, n.in_degree * 5 + 20)),
        isCenter: n.is_center,
      },
    }));
    const edges = data.edges.map((e, i) => ({
      data: {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        type: e.type,
      },
    }));
    return [...nodes, ...edges];
  }, [data]);

  const stylesheet = [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "text-valign": "bottom",
        "text-halign": "center",
        "font-size": "10px",
        color: "#aaa",
        width: "data(weight)",
        height: "data(weight)",
        "background-color": "#4a9eff",
        "border-width": 2,
        "border-color": "#2a7edf",
      },
    },
    {
      selector: "node[isCenter = true]",
      style: {
        "background-color": "#ff6b6b",
        "border-color": "#cc4444",
        "border-width": 3,
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#555",
        "target-arrow-color": "#555",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        opacity: 0.6,
      },
    },
  ];

  if (data.error) {
    return (
      <div className="preview-error">
        <p>Unable to load citation graph: {data.error}</p>
        <p className="hint">Make sure Neo4j is running and graph-build has been executed.</p>
      </div>
    );
  }

  if (!data.nodes || data.nodes.length === 0) {
    return (
      <div className="preview-empty">
        <p>No citation data available.</p>
      </div>
    );
  }

  return (
    <div className="citation-graph-container">
      <div className="graph-header">
        <span className="graph-stats">
          {data.nodes.length} papers | {data.edges.length} citations
        </span>
      </div>
      <CytoscapeComponent
        elements={elements}
        layout={{ name: "cose", animate: true, padding: 30 } as never}
        stylesheet={stylesheet as never}
        style={{ width: "100%", height: "100%", minHeight: "400px" }}
        cy={(cy: unknown) => {
          const cyRef = cy as { on: (event: string, selector: string, cb: (evt: unknown) => void) => void };
          cyRef.on("tap", "node", (evt: unknown) => {
            const target = (evt as { target: { id: () => string } }).target;
            onPaperSelect?.(target.id());
          });
        }}
      />
    </div>
  );
}
