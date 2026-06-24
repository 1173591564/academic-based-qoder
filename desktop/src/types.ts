/* ============================================================ */
/*  Shared Types                                                 */
/* ============================================================ */

export interface FileNode {
  name: string;
  path: string;
  is_dir: boolean;
  children?: FileNode[];
}

export interface Conversation {
  id: string;
  title: string;
  date: string;
  preview: string;
  messageCount: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  streaming?: boolean;
}

export interface ConversationRecord {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  work_dir: string;
  cli_ide: string;
  session_id: string;
  messages: ChatMessage[];
}

export interface Settings {
  cliIde: "claude-code" | "qoder-cli";
  workDir: string;
  cliPath: string;
}

export interface HealthStatus {
  scholar_exe: boolean;
  scholar_exe_path: string;
  python: boolean;
  python_path: string;
  claude_cli: boolean;
  claude_cli_path: string;
  qoder_cli: boolean;
  qoder_cli_path: string;
  mcp_importable: boolean;
  rules_dir: boolean;
  skills_count: number;
  output_dir: boolean;
  pg_running: boolean;
  neo4j_running: boolean;
  overall: boolean;
}

export interface SkillInfo {
  name: string;
  display_name: string;
  description: string;
  is_workflow: boolean;
}

export interface DockerService {
  name: string;
  running: boolean;
  status: string;
}

export interface DotfilesStatus {
  has_claude: boolean;
  has_qoder: boolean;
  claude_md_exists: boolean;
  mcp_json_exists: boolean;
  rules_count: number;
  skills_count: number;
  commands_count: number;
  hooks_count: number;
  total_files: number;
  qoder_total: number;
  last_distributed: string;
}

export interface DistributionResult {
  success: boolean;
  claude_files_copied: number;
  qoder_files_copied: number;
  mcp_json_customized: boolean;
  claude_md_generated: boolean;
  message: string;
}

/* ============================================================ */
/*  Academic Visualization Types                                */
/* ============================================================ */

export interface CitationNode {
  id: string;
  title: string;
  year: number | null;
  in_degree: number;
  is_center: boolean;
}

export interface CitationEdge {
  source: string;
  target: string;
  type: string;
}

export interface CitationGraphData {
  nodes: CitationNode[];
  edges: CitationEdge[];
  error?: string;
}

export interface SectionTOC {
  heading: string;
  level: number;
  content_length: number;
}

export interface PaperCardData {
  paper_id: string;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  abstract: string;
  arxiv_id: string | null;
  doi: string | null;
  sections_toc: SectionTOC[];
  sections_count: number;
  formulas_count: number;
  citations_count: number;
  tags: Record<string, string[]>;
  quality: Record<string, unknown>;
  error?: string;
}

export interface QualityDimension {
  name: string;
  key: string;
  score: number;
  max: number;
  detail: string;
}

export interface QualityRadarData {
  paper_id: string;
  grade: string;
  total: number;
  dimensions: QualityDimension[];
  error?: string;
}

export interface KBDashboardData {
  paper_folders: number;
  parsed: number;
  sections: number;
  formulas: number;
  citations: number;
  coverage: Record<string, number>;
  by_year: Record<string, number>;
  by_venue: Record<string, number>;
  error?: string;
}

export interface ExperimentMetric {
  name: string;
  value: number;
  type: string;
}

export interface MetricComparison {
  name: string;
  ours: number;
  theirs: number | null;
  gap: number | null;
  type: string;
}

export interface ExperimentMetricsData {
  paper_id: string;
  paper_title: string;
  has_experiment: boolean;
  has_results: boolean;
  has_log: boolean;
  mode: string | null;
  runtime_seconds: number | null;
  our_metrics: ExperimentMetric[];
  comparison: MetricComparison[];
  error?: string;
}

export interface TimelineYear {
  year: number;
  count: number;
  papers: { id: string; title: string }[];
}

export interface TimelineData {
  topic: string;
  total: number;
  years: TimelineYear[];
  error?: string;
}
