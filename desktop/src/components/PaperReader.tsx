import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import type { PaperCardData } from "../types";

export function PaperReader({ data }: { data: PaperCardData }) {
  if (data.error) {
    return (
      <div className="preview-error">
        <p>{data.error}</p>
      </div>
    );
  }

  const authorStr = Array.isArray(data.authors)
    ? data.authors.join(", ")
    : String(data.authors || "");

  return (
    <div className="paper-reader">
      {/* Metadata header */}
      <div className="paper-header">
        <h2 className="paper-title">{data.title}</h2>
        <div className="paper-meta">
          {authorStr && <span className="paper-authors">{authorStr}</span>}
          {data.year && <span className="paper-year">{data.year}</span>}
          {data.venue && <span className="paper-venue">{data.venue}</span>}
          {data.arxiv_id && (
            <span className="paper-arxiv">arXiv:{data.arxiv_id}</span>
          )}
          {data.doi && <span className="paper-doi">DOI:{data.doi}</span>}
        </div>
        <div className="paper-stats">
          <span>{data.sections_count} sections</span>
          <span>{data.formulas_count} formulas</span>
          <span>{data.citations_count} citations</span>
        </div>
      </div>

      <div className="paper-body">
        {/* TOC sidebar */}
        {data.sections_toc && data.sections_toc.length > 0 && (
          <div className="paper-toc">
            <h3>Contents</h3>
            {data.sections_toc.map((s, i) => (
              <div
                key={i}
                className={`toc-item toc-level-${s.level}`}
                title={s.heading}
              >
                {s.heading}
              </div>
            ))}
          </div>
        )}

        {/* Abstract */}
        <div className="paper-content">
          {data.abstract && (
            <div className="paper-abstract">
              <h3>Abstract</h3>
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeHighlight, rehypeKatex]}
              >
                {data.abstract}
              </ReactMarkdown>
            </div>
          )}

          {/* Tags */}
          {data.tags && Object.keys(data.tags).length > 0 && (
            <div className="paper-tags">
              <h3>Tags</h3>
              {Object.entries(data.tags).map(([category, tags]) => (
                <div key={category} className="tag-group">
                  <span className="tag-category">{category}:</span>
                  {(tags as string[]).map((tag) => (
                    <span key={tag} className="tag-badge">
                      {tag}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
