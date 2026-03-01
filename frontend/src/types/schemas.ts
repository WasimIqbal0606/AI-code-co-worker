/**
 * Shared TypeScript types mirroring the backend Pydantic schemas.
 * Enhanced with auto-fix remediation, strategic planning, and temperature intelligence.
 */

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type SkillType =
  | "security"
  | "tests"
  | "speedup"
  | "architecture"
  | "prompt_quality";

export type EventType =
  | "supervisor_started"
  | "agent_started"
  | "agent_progress"
  | "agent_done"
  | "supervisor_done"
  | "error";

export type RunStatus = "pending" | "running" | "completed" | "failed";

export type PermissionLevel = "read_only" | "propose" | "apply";

export type RunMode = "auto" | "manual";

export interface Patch {
  file_path: string;
  diff: string;
  description: string;
}

export interface BenchmarkGuidance {
  tool: string;
  command: string;
  expected_improvement: string;
  before_complexity: string;
  after_complexity: string;
}

export interface ArchitecturePlan {
  current_summary: string;
  proposed_changes: string;
  risks_tradeoffs: string;
  refactor_steps: string[];
  acceptance_criteria: string[];
  ascii_diagram: string;
}

export interface TestRunInstructions {
  framework: string;
  install_command: string;
  run_command: string;
  notes: string;
}

// ── Auto-Fix Remediation Types ──────────────────────────────────────

export interface AutoFixResult {
  finding_id: string;
  file_path: string;
  original_code: string;
  fixed_code: string;
  fix_type: string;
  explanation: string;
  breaking_changes: string[];
  imports_needed: string[];
  dependencies_needed: string[];
  confidence: number;
  is_safe_to_auto_apply: boolean;
}

// ── Strategic Planning Types ────────────────────────────────────────

export interface StrategicCluster {
  cluster_id: string;
  cluster_name: string;
  category: string;
  finding_ids: string[];
  root_cause: string;
  combined_severity: string;
  effort_estimate: string;
  risk_score: number;
}

export interface RolloutPhase {
  phase_number: number;
  phase_name: string;
  description: string;
  cluster_ids: string[];
  estimated_effort: string;
  risk_level: string;
  prerequisites: string[];
  rollback_strategy: string;
}

export interface RemediationRoadmap {
  total_findings: number;
  total_clusters: number;
  clusters: StrategicCluster[];
  rollout_phases: RolloutPhase[];
  executive_summary: string;
  estimated_total_effort: string;
  quick_wins: string[];
  deferred: string[];
}

// ── Core Types ──────────────────────────────────────────────────────

export interface Finding {
  id: string;
  agent: string;
  severity: Severity;
  confidence: number;
  title: string;
  description: string;
  file_path: string;
  line_range: number[] | null;
  evidence: string;
  recommendation: string;
  patch: Patch | null;
  explain_steps: string[];
  // Enhanced fields
  benchmark: BenchmarkGuidance | null;
  architecture_plan: ArchitecturePlan | null;
  test_instructions: TestRunInstructions | null;
  why_slow: string;
  complexity_delta: string;
  // Auto-Fix Remediation fields
  auto_fix: AutoFixResult | null;
  cluster_id: string;
}

export interface FileEntry {
  path: string;
  size_bytes: number;
  language: string;
}

export interface RepoManifest {
  repo_id: string;
  total_files: number;
  total_size_bytes: number;
  files: FileEntry[];
}

export interface AgentEvent {
  run_id: string;
  event_type: EventType;
  agent: string;
  message: string;
  progress: number;
  findings_count: number;
  timestamp: string;
}

export interface RunRequest {
  repo_id: string;
  skills: SkillType[];
  permission: PermissionLevel;
  mode: RunMode;
  user_request: string;
}

export interface HealthScores {
  security: number;
  performance: number;
  architecture: number;
  tests: number;
  overall: number;
}

export interface RunResult {
  run_id: string;
  repo_id: string;
  status: RunStatus;
  skills_used: SkillType[];
  findings: Finding[];
  summary: string;
  total_files_analyzed: number;
  duration_seconds: number;
  permission: PermissionLevel;
  health_scores: HealthScores | null;
  critic_summary: string;
  dependency_summary: string;
  // Auto-Fix Remediation & Strategic Planning
  remediation_summary: string;
  roadmap: RemediationRoadmap | null;
}
