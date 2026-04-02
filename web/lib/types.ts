export interface CrawlJob {
  id: string;
  url: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  depth: number;
  concurrency: number;
  stealth: boolean;
  pages_crawled: number;
  pages_total: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
}

export interface Page {
  id: string;
  url: string;
  status_code: number;
  content_type: string;
  title: string;
  response_time_ms: number;
  links_found: number;
  crawl_job_id: string;
  crawled_at: string;
}

export interface SecurityFinding {
  id: string;
  url: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  category: string;
  title: string;
  description?: string;
  evidence?: string;
  remediation?: string;
  crawl_job_id?: string;
  found_at: string;
  type?: string;
  parameter?: string;
  workspace_id?: string | null;
  crawl_id?: string | null;
  triage_status?: string;
  triage_assignee?: string | null;
  triage_tags?: string[];
  triage_notes?: string | null;
  endpoint_id?: string | null;
  transaction_id?: string | null;
  verified?: boolean;
  false_positive?: boolean;
  confidence?: string;
}

export interface AgentProvider {
  id: string;
  name: string;
  type: 'openai' | 'anthropic' | 'ollama' | 'custom' | 'openclaw';
  base_url: string;
  api_key_set: boolean;
  model: string;
  status: 'connected' | 'disconnected' | 'error';
  last_checked: string | null;
  active?: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system' | 'tool';
  content: string;
  tool_name?: string;
  tool_params?: Record<string, unknown>;
  tool_result?: string;
  tool_status?: 'pending' | 'approved' | 'denied' | 'completed' | 'error';
  timestamp: string;
}

export interface MetricsSnapshot {
  pages_crawled: number;
  security_findings: number;
  active_jobs: number;
  queue_depth: number;
  requests_per_second: number;
  error_rate: number;
  status_codes: Record<string, number>;
  throughput_history: ThroughputPoint[];
  uptime_seconds: number;
}

export interface ThroughputPoint {
  timestamp: string;
  pages_per_second: number;
}

export interface LogEntry {
  id: string;
  level: 'error' | 'warn' | 'info' | 'debug';
  source: string;
  message: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

export interface IntelligenceBrief {
  id: string;
  title: string;
  summary: string;
  content: string;
  sources: string[];
  tags: string[];
  created_at: string;
}

export interface TopologyNode {
  id: string;
  domain: string;
  pages: number;
  status: number;
}

export interface TopologyLink {
  source: string;
  target: string;
  weight: number;
}

export interface TopologyData {
  nodes: TopologyNode[];
  links: TopologyLink[];
}

export interface LicenseStatus {
  installed: boolean;
  tier: 'FREE' | 'LITE' | 'PRO' | 'SELF_HOST';
  key_preview: string | null;
  installed_at: string | null;
  pages_limit: number | null;
  pages_used: number;
  pages_remaining: number | null;
  pct_used: number;
  month: string;
  tier_description: string;
}

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  scope_rules: Array<Record<string, unknown>>;
  tags: string[];
  risk_policy: Record<string, unknown>;
  archived: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface WorkspaceLibraryItem {
  page_id: string;
  workspace_id: string;
  crawl_id: string;
  crawl_target_url: string;
  crawl_status: string | null;
  url: string;
  domain: string;
  path: string;
  title: string;
  h1: string;
  meta_description: string;
  status_code: number | null;
  content_type: string;
  content_family: string;
  word_count: number;
  depth: number;
  fetch_mode: string;
  scraped_at: string | null;
  suggested_category: string;
  suggested_folder: string;
  suggested_labels: string[];
  category: string;
  folder: string;
  labels: string[];
  category_source: 'manual' | 'suggested';
  folder_source: 'manual' | 'suggested';
  filing_id: string | null;
  starred: boolean;
  notes: string | null;
  has_manual_filing: boolean;
}

export interface WorkspaceCategoryCount {
  category: string;
  count: number;
}

export interface WorkspaceFolderCount {
  folder: string;
  count: number;
}

export interface WorkspaceDomainCount {
  domain: string;
  count: number;
}

export interface WorkspaceContentFamilyCount {
  content_family: string;
  count: number;
}

export interface WorkspaceLibrarySummary {
  total_pages: number;
  filed_pages: number;
  starred_pages: number;
  domains: number;
  by_category: WorkspaceCategoryCount[];
  by_folder: WorkspaceFolderCount[];
  by_domain: WorkspaceDomainCount[];
  by_content_family: WorkspaceContentFamilyCount[];
  avg_word_count: number;
}

export interface WorkspaceLibrarySummaryResponse {
  workspace: Workspace;
  summary: WorkspaceLibrarySummary;
  recent_items: WorkspaceLibraryItem[];
}

export interface WorkspaceLibraryListResponse {
  workspace: Workspace;
  summary: WorkspaceLibrarySummary;
  total: number;
  page: number;
  per_page: number;
  items: WorkspaceLibraryItem[];
}
