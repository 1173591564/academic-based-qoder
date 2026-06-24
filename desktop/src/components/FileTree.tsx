import { useState } from "react";
import type { FileNode } from "../types";
import { EmptyState } from "./EmptyState";
import {
  FileText,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  FileJson,
  FileCode,
  BookOpen,
  FolderOpenIcon,
} from "lucide-react";

interface FileTreeNodeProps {
  node: FileNode;
  depth: number;
  onFileClick: (path: string, name: string) => void;
}

function getFileIcon(name: string) {
  if (name.endsWith(".json")) return <FileJson size={14} className="file-icon file-icon-json" />;
  if (name.endsWith(".md")) return <BookOpen size={14} className="file-icon file-icon-md" />;
  if (name.endsWith(".py")) return <FileCode size={14} className="file-icon file-icon-py" />;
  return <FileText size={14} className="file-icon" />;
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
        {getFileIcon(node.name)}
        <span className="file-name">{node.name}</span>
      </div>
    );
  }

  return (
    <div>
      <div
        className="file-item folder"
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
        onClick={() => setExpanded(!expanded)}
      >
        <span className="folder-arrow">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
        {expanded ? (
          <FolderOpen size={14} className="file-icon file-icon-folder" />
        ) : (
          <Folder size={14} className="file-icon file-icon-folder" />
        )}
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
          <RefreshCw size={14} />
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
          <EmptyState
            icon={FolderOpenIcon}
            title="工作区暂无文件"
            description="选择目录后，输出文件将显示在此"
          />
        )}
      </div>
    </>
  );
}
