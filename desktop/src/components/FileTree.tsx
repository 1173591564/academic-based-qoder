import { useState } from "react";
import type { FileNode } from "../types";

interface FileTreeNodeProps {
  node: FileNode;
  depth: number;
  onFileClick: (path: string, name: string) => void;
}

function FileTreeNode({ node, depth, onFileClick }: FileTreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);

  if (!node.is_dir) {
    return (
      <div
        className="file-item file"
        style={{ paddingLeft: `${depth * 16 + 12}px` }}
        title={node.path}
        onClick={() => onFileClick(node.path, node.name)}
      >
        <span className="file-icon">📄</span>
        <span className="file-name">{node.name}</span>
      </div>
    );
  }

  return (
    <div>
      <div
        className="file-item folder"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => setExpanded(!expanded)}
      >
        <span className="folder-arrow">{expanded ? "▾" : "▸"}</span>
        <span className="file-icon">📁</span>
        <span className="file-name">{node.name}</span>
      </div>
      {expanded && node.children && (
        <div>
          {node.children.map((child) => (
            <FileTreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              onFileClick={onFileClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({
  files,
  fileFilter,
  setFileFilter,
  onFileClick,
  onRefresh,
}: {
  files: FileNode[];
  fileFilter: string;
  setFileFilter: (f: string) => void;
  onFileClick: (path: string, name: string) => void;
  onRefresh: () => void;
}) {
  return (
    <>
      <div className="sidebar-header">
        <span className="sidebar-title">工作区</span>
        <button className="icon-btn" onClick={onRefresh} title="刷新">
          ↻
        </button>
      </div>
      <div className="file-filter-bar">
        {["", "notes", "drafts", "experiments", "digests"].map((f) => (
          <button
            key={f}
            className={`filter-btn ${fileFilter === f ? "active" : ""}`}
            onClick={() => setFileFilter(f)}
          >
            {f === ""
              ? "全部"
              : f === "notes"
                ? "笔记"
                : f === "drafts"
                  ? "草稿"
                  : f === "experiments"
                    ? "实验"
                    : "报告"}
          </button>
        ))}
      </div>
      <div className="file-tree">
        {files.length > 0 ? (
          files
            .filter(
              (node) =>
                !fileFilter ||
                node.path.startsWith(fileFilter + "/") ||
                node.path.startsWith(fileFilter)
            )
            .map((node) => (
              <FileTreeNode
                key={node.path}
                node={node}
                depth={0}
                onFileClick={onFileClick}
              />
            ))
        ) : (
          <div className="empty-hint">暂无文件</div>
        )}
      </div>
    </>
  );
}
