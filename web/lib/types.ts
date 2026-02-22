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
  description: string;
  evidence: string;
  remediation: string;
  crawl_job_id: string;
  found_at: string;
}

export interface AgentProvider {
  id: string;
  name: string;
  type: 'openai' | 'anthropic' | 'ollama' | 'custom';
  base_url: string;
  api_key_set: boolean;
  model: string;
  status: 'connected' | 'disconnected' | 'error';
  last_checked: string | null;
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
