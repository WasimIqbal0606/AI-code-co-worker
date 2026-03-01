"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { useRunEvents } from "@/hooks/useRunEvents";
import { getManifest, getRunResult, getDownloadUrl } from "@/lib/api";
import type { RepoManifest, RunResult } from "@/types/schemas";
import FileManifest from "@/components/FileManifest";
import AgentTimeline from "@/components/AgentTimeline";
import FindingsPanel from "@/components/FindingsPanel";
import HealthScoreCard from "@/components/HealthScoreCard";
import Link from "next/link";

const permLabel: Record<string, string> = {
    read_only: "👁️ Read Only",
    propose: "📝 Propose",
    apply: "🚀 Apply",
};

export default function RunPage() {
    const params = useParams();
    const searchParams = useSearchParams();
    const router = useRouter();
    const runId = params.runId as string;
    const repoId = searchParams.get("repo_id") || "";

    const { events, isConnected, isDone, error } = useRunEvents(runId);
    const [manifest, setManifest] = useState<RepoManifest | null>(null);
    const [result, setResult] = useState<RunResult | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [showHealth, setShowHealth] = useState(true);

    // Load manifest
    useEffect(() => {
        if (repoId) {
            getManifest(repoId)
                .then(setManifest)
                .catch(() => setLoadError("Repository not found. It may have been cleared when the server restarted."));
        }
    }, [repoId]);

    // Load final result when done
    useEffect(() => {
        if (isDone && !error) {
            getRunResult(runId)
                .then(setResult)
                .catch(() => setLoadError("Failed to load run result. The server may have restarted."));
        }
    }, [isDone, error, runId]);

    // Count findings by severity
    const sevCounts: Record<string, number> = {};
    (result?.findings || []).forEach((f) => {
        sevCounts[f.severity] = (sevCounts[f.severity] || 0) + 1;
    });

    // Auto-redirect to home on error after 5 seconds
    useEffect(() => {
        if (error || loadError) {
            const timer = setTimeout(() => router.push("/"), 5000);
            return () => clearTimeout(timer);
        }
    }, [error, loadError, router]);

    // Show error overlay
    if (error || loadError) {
        return (
            <div className="h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
                <div className="text-center space-y-4 p-8 rounded-2xl max-w-md glass-strong animate-scale-in">
                    <p className="text-5xl">🔄</p>
                    <p className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                        Run Not Available
                    </p>
                    <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                        {error || loadError}
                    </p>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        Redirecting to home in a few seconds...
                    </p>
                    <button
                        onClick={() => router.push("/")}
                        className="px-6 py-2.5 rounded-xl font-bold text-white transition-all duration-300"
                        style={{
                            background: "linear-gradient(135deg, var(--mistral-orange), var(--accent-blue))",
                            boxShadow: "0 4px 15px rgba(255,107,43,0.2)",
                        }}>
                        ← Start a New Run
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex flex-col bg-[var(--bg-primary)]">
            {/* Top Bar */}
            <header className="flex items-center justify-between px-5 py-3 border-b"
                style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}>
                <div className="flex items-center gap-3">
                    <Link href="/"
                        className="text-sm px-3 py-1.5 rounded-lg transition-all duration-200 hover:bg-[var(--bg-hover)]"
                        style={{ color: "var(--text-muted)" }}>
                        ← Back
                    </Link>
                    <h1 className="text-lg font-extrabold text-gradient-mistral">
                        Code Co-Worker
                    </h1>
                    <span className="text-xs px-2 py-0.5 rounded-md"
                        style={{
                            background: "var(--bg-card)",
                            color: "var(--text-muted)",
                            fontFamily: "JetBrains Mono, monospace",
                            border: "1px solid var(--border)",
                        }}>
                        {runId}
                    </span>
                </div>

                <div className="flex items-center gap-3">
                    {/* Mistral badge */}
                    <span className="text-xs px-2.5 py-1 rounded-md mistral-badge font-semibold hidden md:inline-flex items-center gap-1">
                        🤖 Mistral
                    </span>

                    {/* Permission badge */}
                    {result && (
                        <span className="text-xs px-2 py-1 rounded-md"
                            style={{ background: "rgba(168,85,247,0.08)", color: "var(--accent-purple)", border: "1px solid rgba(168,85,247,0.2)" }}>
                            {permLabel[result.permission] || result.permission}
                        </span>
                    )}

                    {/* Status */}
                    {result ? (
                        <span className="text-xs px-2.5 py-1 rounded-md font-bold"
                            style={{
                                background: result.status === "completed" ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
                                color: result.status === "completed" ? "var(--accent-green)" : "var(--accent-red)",
                                border: `1px solid ${result.status === "completed" ? "rgba(16,185,129,0.25)" : "rgba(239,68,68,0.25)"}`,
                            }}>
                            {result.status === "completed" ? "✓ " : ""}{result.status.toUpperCase()}
                        </span>
                    ) : (
                        <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--mistral-orange)" }}>
                            <span className="animate-spin-slow">⚙️</span> Analyzing...
                        </span>
                    )}

                    {/* Download */}
                    {result?.status === "completed" && result.permission !== "read_only" && (
                        <a href={getDownloadUrl(runId)}
                            className="text-xs px-4 py-1.5 rounded-lg font-bold transition-all duration-300 text-white"
                            style={{
                                background: "linear-gradient(135deg, var(--mistral-orange), var(--accent-blue))",
                                boxShadow: "0 2px 10px rgba(255,107,43,0.15)",
                            }}>
                            📥 Download
                        </a>
                    )}
                </div>
            </header>

            {/* Summary bar with stats */}
            {result && (
                <div className="px-5 py-3 border-b animate-fade-in"
                    style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
                    <div className="flex items-center gap-3 flex-wrap">
                        {/* Stat chips */}
                        <div className="stat-chip">
                            <span className="stat-icon">📊</span>
                            <span className="stat-value">{result.total_files_analyzed}</span>
                            <span className="stat-label">files</span>
                        </div>
                        <div className="stat-chip">
                            <span className="stat-icon">🔍</span>
                            <span className="stat-value">{result.findings.length}</span>
                            <span className="stat-label">findings</span>
                        </div>
                        <div className="stat-chip">
                            <span className="stat-icon">🔧</span>
                            <span className="stat-value">{result.findings.filter(f => f.auto_fix).length}</span>
                            <span className="stat-label">auto-fixes</span>
                        </div>
                        <div className="stat-chip">
                            <span className="stat-icon">⏱️</span>
                            <span className="stat-value">{result.duration_seconds}s</span>
                        </div>
                        <div className="stat-chip">
                            <span className="stat-icon">🛠️</span>
                            <span className="stat-label">{result.skills_used.join(", ")}</span>
                        </div>

                        {/* Severity badges */}
                        <div className="flex gap-1.5 ml-auto">
                            {Object.entries(sevCounts).map(([sev, count]) => (
                                <span key={sev} className={`badge-${sev} text-xs px-2 py-0.5 rounded-md font-semibold`}>
                                    {sev}: {count}
                                </span>
                            ))}
                        </div>

                        {/* Health score toggle */}
                        {result.health_scores && (
                            <button
                                onClick={() => setShowHealth(!showHealth)}
                                className="text-xs px-3 py-1 rounded-md font-semibold transition-all duration-200"
                                style={{
                                    background: showHealth ? "rgba(255,107,43,0.12)" : "transparent",
                                    color: showHealth ? "var(--mistral-orange)" : "var(--text-muted)",
                                    border: `1px solid ${showHealth ? "rgba(255,107,43,0.3)" : "var(--border)"}`,
                                }}
                            >
                                {showHealth ? "📊 Health" : "📊 Health"}
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Health Scores Dashboard */}
            {result?.health_scores && showHealth && (
                <div className="px-5 py-4 border-b animate-slide-up"
                    style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}>
                    <HealthScoreCard scores={result.health_scores} />

                    {/* Summaries row */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                        {result.critic_summary && (
                            <div className="rounded-xl p-3 flex flex-col"
                                style={{ background: "var(--bg-card)", border: "1px solid var(--border)", maxHeight: "12rem" }}>
                                <div className="flex items-center gap-2 mb-1.5 flex-shrink-0">
                                    <span className="text-sm">🧠</span>
                                    <span className="text-[10px] font-bold uppercase tracking-wider"
                                        style={{ color: "#f472b6" }}>
                                        Critic Summary
                                    </span>
                                </div>
                                <div className="overflow-y-auto pr-2 custom-scrollbar">
                                    <p className="text-xs leading-relaxed"
                                        style={{ color: "var(--text-secondary)" }}>
                                        {result.critic_summary}
                                    </p>
                                </div>
                            </div>
                        )}
                        {result.dependency_summary && (
                            <div className="rounded-xl p-3 flex flex-col"
                                style={{ background: "var(--bg-card)", border: "1px solid var(--border)", maxHeight: "12rem" }}>
                                <div className="flex items-center gap-2 mb-1.5 flex-shrink-0">
                                    <span className="text-sm">📦</span>
                                    <span className="text-[10px] font-bold uppercase tracking-wider"
                                        style={{ color: "var(--mistral-orange)" }}>
                                        Dependency Summary
                                    </span>
                                </div>
                                <div className="overflow-y-auto pr-2 custom-scrollbar">
                                    <p className="text-xs leading-relaxed"
                                        style={{ color: "var(--text-secondary)" }}>
                                        {result.dependency_summary}
                                    </p>
                                </div>
                            </div>
                        )}
                        {result.remediation_summary && (
                            <div className="rounded-xl p-3 flex flex-col"
                                style={{ background: "var(--bg-card)", border: "1px solid rgba(16,185,129,0.2)", maxHeight: "12rem" }}>
                                <div className="flex items-center gap-2 mb-1.5 flex-shrink-0">
                                    <span className="text-sm">🔧</span>
                                    <span className="text-[10px] font-bold uppercase tracking-wider"
                                        style={{ color: "var(--accent-green)" }}>
                                        Remediation Summary
                                    </span>
                                </div>
                                <div className="overflow-y-auto pr-2 custom-scrollbar">
                                    <p className="text-xs leading-relaxed"
                                        style={{ color: "var(--text-secondary)" }}>
                                        {result.remediation_summary}
                                    </p>
                                </div>
                            </div>
                        )}
                        {result.roadmap && (
                            <div className="rounded-xl p-3 flex flex-col"
                                style={{ background: "var(--bg-card)", border: "1px solid rgba(99,102,241,0.2)", maxHeight: "16rem" }}>
                                <div className="flex items-center gap-2 mb-1.5 flex-shrink-0">
                                    <span className="text-sm">📊</span>
                                    <span className="text-[10px] font-bold uppercase tracking-wider"
                                        style={{ color: "var(--accent-blue)" }}>
                                        Strategic Roadmap
                                    </span>
                                </div>
                                <div className="overflow-y-auto pr-2 custom-scrollbar space-y-2">
                                    <p className="text-xs font-semibold"
                                        style={{ color: "var(--text-primary)" }}>
                                        {result.roadmap.executive_summary}
                                    </p>
                                    <div className="flex gap-2 flex-wrap">
                                        <span className="text-[10px] px-2 py-0.5 rounded-full"
                                            style={{ background: "rgba(99,102,241,0.1)", color: "var(--accent-blue)" }}>
                                            {result.roadmap.total_clusters} clusters
                                        </span>
                                        <span className="text-[10px] px-2 py-0.5 rounded-full"
                                            style={{ background: "rgba(16,185,129,0.1)", color: "var(--accent-green)" }}>
                                            {result.roadmap.rollout_phases.length} phases
                                        </span>
                                        <span className="text-[10px] px-2 py-0.5 rounded-full"
                                            style={{ background: "rgba(251,191,36,0.1)", color: "var(--accent-amber)" }}>
                                            {result.roadmap.quick_wins.length} quick wins
                                        </span>
                                        <span className="text-[10px] px-2 py-0.5 rounded-full"
                                            style={{ background: "rgba(168,85,247,0.1)", color: "var(--accent-purple)" }}>
                                            Est: {result.roadmap.estimated_total_effort}
                                        </span>
                                    </div>
                                    {result.roadmap.clusters.slice(0, 4).map((cluster) => (
                                        <div key={cluster.cluster_id} className="flex items-center gap-2 text-[11px]"
                                            style={{ color: "var(--text-secondary)" }}>
                                            <span className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                                                style={{
                                                    background: cluster.risk_score >= 80 ? "rgba(239,68,68,0.15)"
                                                        : cluster.risk_score >= 50 ? "rgba(251,191,36,0.15)"
                                                            : "rgba(16,185,129,0.15)",
                                                    color: cluster.risk_score >= 80 ? "#f87171"
                                                        : cluster.risk_score >= 50 ? "#fbbf24"
                                                            : "var(--accent-green)",
                                                }}>
                                                {cluster.risk_score}
                                            </span>
                                            <span className="truncate">{cluster.cluster_name}</span>
                                            <span style={{ color: "var(--text-muted)" }}>
                                                ({cluster.finding_ids.length} findings, {cluster.effort_estimate})
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 3-Panel Layout — Fixed height so internal scrolling works, but page scrolls to reach it */}
            <div className="flex border-t" style={{ height: "800px", borderColor: "var(--border)" }}>
                {/* Left: File Manifest */}
                <div className="w-64 border-r flex-shrink-0 overflow-y-auto"
                    style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}>
                    {manifest ? (
                        <FileManifest files={manifest.files} />
                    ) : (
                        <div className="flex items-center justify-center h-full" style={{ color: "var(--text-muted)" }}>
                            <span className="animate-spin-slow text-2xl">⏳</span>
                        </div>
                    )}
                </div>

                {/* Middle: Agent Timeline */}
                <div className="flex-1 min-w-0 border-r overflow-y-auto"
                    style={{ background: "var(--bg-primary)", borderColor: "var(--border)" }}>
                    <AgentTimeline events={events} isConnected={isConnected} />
                </div>

                {/* Right: Findings */}
                <div className="w-96 flex-shrink-0 overflow-y-auto"
                    style={{ background: "var(--bg-secondary)" }}>
                    <FindingsPanel findings={result?.findings || []} />
                </div>
            </div>

        </div>
    );
}
