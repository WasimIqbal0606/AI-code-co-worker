"use client";

import { useState } from "react";
import type { Finding, Severity } from "@/types/schemas";
import DetailDrawer from "./DetailDrawer";

interface FindingsPanelProps {
    findings: Finding[];
}

const severityOrder: Severity[] = ["critical", "high", "medium", "low", "info"];

export default function FindingsPanel({ findings }: FindingsPanelProps) {
    const [filter, setFilter] = useState<Severity | "all">("all");
    const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
    const [showExplain, setShowExplain] = useState(false);

    const filtered =
        filter === "all"
            ? findings
            : findings.filter((f) => f.severity === filter);

    const sorted = [...filtered].sort(
        (a, b) =>
            severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
    );

    const counts: Record<string, number> = {};
    findings.forEach((f) => {
        counts[f.severity] = (counts[f.severity] || 0) + 1;
    });

    return (
        <>
            <div className="h-full flex flex-col">
                <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-center justify-between mb-2">
                        <h3
                            className="text-xs font-semibold uppercase tracking-wider"
                            style={{ color: "var(--text-muted)" }}
                        >
                            Findings ({findings.length})
                        </h3>
                        <button
                            onClick={() => setShowExplain(!showExplain)}
                            className="text-xs px-2 py-1 rounded-md transition-colors"
                            style={{
                                background: showExplain
                                    ? "rgba(99,102,241,0.15)"
                                    : "transparent",
                                color: showExplain
                                    ? "var(--accent-blue)"
                                    : "var(--text-muted)",
                                border: `1px solid ${showExplain
                                    ? "rgba(99,102,241,0.3)"
                                    : "var(--border)"
                                    }`,
                            }}
                        >
                            💡 Explain
                        </button>
                    </div>
                    {/* Filter buttons */}
                    <div className="flex flex-wrap gap-1">
                        <button
                            onClick={() => setFilter("all")}
                            className={`text-xs px-2 py-1 rounded-md transition-colors ${filter === "all" ? "bg-indigo-500/20 text-indigo-400" : ""
                                }`}
                            style={{
                                color: filter === "all" ? undefined : "var(--text-muted)",
                            }}
                        >
                            All
                        </button>
                        {severityOrder.map((s) => (
                            <button
                                key={s}
                                onClick={() => setFilter(s)}
                                className={`text-xs px-2 py-1 rounded-md badge-${s} transition-colors ${filter === s ? "ring-1 ring-current" : "opacity-60"
                                    }`}
                            >
                                {s} {counts[s] ? `(${counts[s]})` : ""}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                    {sorted.length === 0 ? (
                        <div
                            className="flex items-center justify-center h-full"
                            style={{ color: "var(--text-muted)" }}
                        >
                            <p className="text-sm">No findings yet</p>
                        </div>
                    ) : (
                        sorted.map((f, i) => (
                            <div
                                key={`${f.id}-${i}`}
                                onClick={() => setSelectedFinding(f)}
                                className="p-3 rounded-xl cursor-pointer transition-all duration-200 animate-fade-in hover:bg-[var(--bg-hover)]"
                                style={{
                                    background: "var(--bg-card)",
                                    border: "1px solid var(--border)",
                                    animationDelay: `${i * 50}ms`,
                                }}
                            >
                                <div className="flex items-start gap-2">
                                    <span className={`badge-${f.severity} text-xs px-1.5 py-0.5 rounded font-semibold`}>
                                        {f.severity.toUpperCase()}
                                    </span>
                                    {f.auto_fix && (
                                        <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold flex-shrink-0"
                                            style={{
                                                background: f.auto_fix.is_safe_to_auto_apply
                                                    ? "rgba(16,185,129,0.15)" : "rgba(251,191,36,0.15)",
                                                color: f.auto_fix.is_safe_to_auto_apply
                                                    ? "var(--accent-green)" : "var(--accent-amber)",
                                            }}>
                                            🔧 Fix
                                        </span>
                                    )}
                                    <div className="flex-1 min-w-0">
                                        <p className="font-semibold text-sm truncate">{f.title}</p>
                                        <p className="text-xs mt-0.5 truncate"
                                            style={{ color: "var(--text-muted)" }}>
                                            {f.file_path}
                                            {f.line_range && ` (L${f.line_range[0]}-${f.line_range[1]})`}
                                        </p>
                                        {/* Explain toggle */}
                                        {showExplain && f.explain_steps.length > 0 && (
                                            <ul className="mt-2 space-y-0.5">
                                                {f.explain_steps.map((step, j) => (
                                                    <li
                                                        key={j}
                                                        className="text-xs flex items-start gap-1"
                                                        style={{ color: "var(--text-secondary)" }}
                                                    >
                                                        <span style={{ color: "var(--accent-blue)" }}>•</span>
                                                        {step}
                                                    </li>
                                                ))}
                                            </ul>
                                        )}
                                    </div>
                                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                                        {Math.round((f.confidence ?? 0) * 100)}%
                                    </span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Detail Drawer */}
            {selectedFinding && (
                <DetailDrawer
                    finding={selectedFinding}
                    onClose={() => setSelectedFinding(null)}
                />
            )}
        </>
    );
}
