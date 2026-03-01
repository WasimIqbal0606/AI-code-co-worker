"use client";

import type { Finding } from "@/types/schemas";

interface DetailDrawerProps {
    finding: Finding;
    onClose: () => void;
}

export default function DetailDrawer({ finding, onClose }: DetailDrawerProps) {
    const renderDiff = (diff: string) => {
        return diff.split("\n").map((line, i) => {
            let cls = "";
            if (line.startsWith("+") && !line.startsWith("+++")) cls = "diff-add";
            else if (line.startsWith("-") && !line.startsWith("---")) cls = "diff-remove";
            else if (line.startsWith("@@") || line.startsWith("#")) cls = "diff-header";
            return (
                <div key={i} className={`px-3 py-0.5 ${cls}`}>
                    {line || " "}
                </div>
            );
        });
    };

    return (
        <div className="fixed inset-0 z-50 flex justify-end">
            {/* Overlay */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

            {/* Drawer */}
            <div className="relative w-full max-w-xl h-full overflow-y-auto animate-slide-in"
                style={{ background: "var(--bg-secondary)", borderLeft: "1px solid var(--border)" }}>

                {/* Header */}
                <div className="sticky top-0 z-10 p-4 flex items-start justify-between"
                    style={{ background: "var(--bg-secondary)", borderBottom: "1px solid var(--border)" }}>
                    <div className="flex-1 min-w-0 mr-3">
                        <span className={`badge-${finding.severity} text-xs px-2 py-0.5 rounded font-semibold`}>
                            {finding.severity.toUpperCase()}
                        </span>
                        <h2 className="text-lg font-bold mt-2">{finding.title}</h2>
                        <p className="text-sm mt-0.5" style={{ color: "var(--text-muted)" }}>
                            {finding.agent} • {finding.file_path}
                            {finding.line_range && ` • Lines ${finding.line_range[0]}-${finding.line_range[1]}`}
                        </p>
                    </div>
                    <button onClick={onClose}
                        className="text-xl px-2 py-1 rounded-lg hover:bg-[var(--bg-hover)] transition-colors"
                        style={{ color: "var(--text-muted)" }}>✕</button>
                </div>

                <div className="p-4 space-y-5">

                    {/* Why Slow (SpeedUp agent) */}
                    {finding.why_slow && (
                        <section>
                            <h4 className="section-label">⚡ Why This Is Slow</h4>
                            <p className="text-sm leading-relaxed" style={{ color: "#fbbf24" }}>{finding.why_slow}</p>
                        </section>
                    )}

                    {/* Complexity Delta */}
                    {finding.complexity_delta && (
                        <section>
                            <h4 className="section-label">📊 Complexity Change</h4>
                            <div className="flex items-center gap-3 p-3 rounded-xl"
                                style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
                                <span className="text-lg font-mono font-bold" style={{ color: "var(--accent-green)" }}>
                                    {finding.complexity_delta}
                                </span>
                            </div>
                        </section>
                    )}

                    {/* Description */}
                    <section>
                        <h4 className="section-label">📋 Description</h4>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>
                            {finding.description}
                        </p>
                    </section>

                    {/* Evidence */}
                    {finding.evidence && (
                        <section>
                            <h4 className="section-label">🔍 Evidence</h4>
                            <pre className="code-block">{finding.evidence}</pre>
                        </section>
                    )}

                    {/* Recommendation */}
                    {finding.recommendation && (
                        <section>
                            <h4 className="section-label">✅ Recommendation</h4>
                            <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--accent-green)" }}>
                                {finding.recommendation}
                            </p>
                        </section>
                    )}

                    {/* Architecture Plan */}
                    {finding.architecture_plan && (
                        <section className="space-y-3">
                            <h4 className="section-label">🏗️ Architecture Migration Plan</h4>

                            <div className="plan-section">
                                <h5 className="plan-title">Current Architecture</h5>
                                <p className="plan-text">{finding.architecture_plan.current_summary}</p>
                            </div>

                            <div className="plan-section">
                                <h5 className="plan-title">Proposed Changes</h5>
                                <p className="plan-text">{finding.architecture_plan.proposed_changes}</p>
                            </div>

                            <div className="plan-section">
                                <h5 className="plan-title">Risks & Trade-offs</h5>
                                <p className="plan-text" style={{ color: "var(--accent-amber)" }}>
                                    {finding.architecture_plan.risks_tradeoffs}
                                </p>
                            </div>

                            {finding.architecture_plan.refactor_steps.length > 0 && (
                                <div className="plan-section">
                                    <h5 className="plan-title">Step-by-Step Refactor Plan</h5>
                                    <ol className="space-y-1.5 ml-1">
                                        {finding.architecture_plan.refactor_steps.map((step, i) => (
                                            <li key={i} className="text-sm flex items-start gap-2" style={{ color: "var(--text-secondary)" }}>
                                                <span className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold mt-0.5"
                                                    style={{ background: "rgba(99,102,241,0.15)", color: "var(--accent-blue)" }}>
                                                    {i + 1}
                                                </span>
                                                {step}
                                            </li>
                                        ))}
                                    </ol>
                                </div>
                            )}

                            {finding.architecture_plan.acceptance_criteria.length > 0 && (
                                <div className="plan-section">
                                    <h5 className="plan-title">Acceptance Criteria</h5>
                                    <ul className="space-y-1">
                                        {finding.architecture_plan.acceptance_criteria.map((c, i) => (
                                            <li key={i} className="text-sm flex items-start gap-2" style={{ color: "var(--accent-green)" }}>
                                                <span>✓</span> {c}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {finding.architecture_plan.ascii_diagram && (
                                <div className="plan-section">
                                    <h5 className="plan-title">Architecture Diagram</h5>
                                    <pre className="code-block whitespace-pre text-xs">
                                        {finding.architecture_plan.ascii_diagram}
                                    </pre>
                                </div>
                            )}
                        </section>
                    )}

                    {/* Benchmark Guidance (SpeedUp) */}
                    {finding.benchmark && (
                        <section>
                            <h4 className="section-label">📈 How to Benchmark</h4>
                            <div className="space-y-2 p-3 rounded-xl"
                                style={{ background: "var(--bg-primary)", border: "1px solid var(--border)" }}>
                                <div className="flex gap-4 text-xs">
                                    <span style={{ color: "var(--text-muted)" }}>Tool:</span>
                                    <span className="font-mono" style={{ color: "var(--accent-cyan)" }}>{finding.benchmark.tool}</span>
                                </div>
                                <div className="text-xs">
                                    <span style={{ color: "var(--text-muted)" }}>Command:</span>
                                    <pre className="mt-1 p-2 rounded-lg text-xs font-mono"
                                        style={{ background: "var(--bg-card)", color: "var(--accent-green)" }}>
                                        {finding.benchmark.command}
                                    </pre>
                                </div>
                                <div className="flex gap-4 text-xs">
                                    <span style={{ color: "var(--text-muted)" }}>Expected:</span>
                                    <span style={{ color: "var(--accent-amber)" }}>{finding.benchmark.expected_improvement}</span>
                                </div>
                                <div className="flex gap-4 text-xs">
                                    <span style={{ color: "var(--text-muted)" }}>Complexity:</span>
                                    <span className="font-mono">
                                        <span style={{ color: "#f87171" }}>{finding.benchmark.before_complexity}</span>
                                        {" → "}
                                        <span style={{ color: "var(--accent-green)" }}>{finding.benchmark.after_complexity}</span>
                                    </span>
                                </div>
                            </div>
                        </section>
                    )}

                    {/* Test Run Instructions */}
                    {finding.test_instructions && (
                        <section>
                            <h4 className="section-label">🧪 How to Run Tests</h4>
                            <div className="space-y-2 p-3 rounded-xl"
                                style={{ background: "var(--bg-primary)", border: "1px solid var(--border)" }}>
                                <div className="flex gap-4 text-xs">
                                    <span style={{ color: "var(--text-muted)" }}>Framework:</span>
                                    <span className="font-semibold" style={{ color: "var(--accent-cyan)" }}>
                                        {finding.test_instructions.framework}
                                    </span>
                                </div>
                                {finding.test_instructions.install_command && (
                                    <div className="text-xs">
                                        <span style={{ color: "var(--text-muted)" }}>Install:</span>
                                        <pre className="mt-1 p-2 rounded-lg font-mono"
                                            style={{ background: "var(--bg-card)", color: "var(--accent-amber)" }}>
                                            {finding.test_instructions.install_command}
                                        </pre>
                                    </div>
                                )}
                                <div className="text-xs">
                                    <span style={{ color: "var(--text-muted)" }}>Run:</span>
                                    <pre className="mt-1 p-2 rounded-lg font-mono"
                                        style={{ background: "var(--bg-card)", color: "var(--accent-green)" }}>
                                        {finding.test_instructions.run_command}
                                    </pre>
                                </div>
                                {finding.test_instructions.notes && (
                                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                                        💡 {finding.test_instructions.notes}
                                    </p>
                                )}
                            </div>
                        </section>
                    )}

                    {/* Patch Diff Preview */}
                    {finding.patch && (
                        <section>
                            <h4 className="section-label">
                                📄 {finding.agent === "tests" ? "Generated Test File" : "Suggested Patch"} — {finding.patch.file_path}
                            </h4>
                            <div className="rounded-lg overflow-hidden text-xs"
                                style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", fontFamily: "JetBrains Mono, monospace" }}>
                                {renderDiff(finding.patch.diff)}
                            </div>
                        </section>
                    )}

                    {/* Auto-Fix Result (NEW — Remediation Engine) */}
                    {finding.auto_fix && (
                        <section className="space-y-3">
                            <h4 className="section-label">🔧 Auto-Fix Available</h4>
                            <div className="p-3 rounded-xl" style={{
                                background: "rgba(16,185,129,0.06)",
                                border: "1px solid rgba(16,185,129,0.2)",
                            }}>
                                {/* Fix Type Badge */}
                                <div className="flex items-center gap-2 mb-3">
                                    <span className="text-xs px-2 py-0.5 rounded-full font-bold"
                                        style={{
                                            background: finding.auto_fix.is_safe_to_auto_apply
                                                ? "rgba(16,185,129,0.2)" : "rgba(251,191,36,0.2)",
                                            color: finding.auto_fix.is_safe_to_auto_apply
                                                ? "var(--accent-green)" : "var(--accent-amber)",
                                        }}>
                                        {finding.auto_fix.fix_type.replace(/_/g, ' ').toUpperCase()}
                                    </span>
                                    {finding.auto_fix.is_safe_to_auto_apply && (
                                        <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                                            style={{ background: "rgba(16,185,129,0.15)", color: "var(--accent-green)" }}>
                                            ✅ Safe to auto-apply
                                        </span>
                                    )}
                                </div>

                                {/* Explanation */}
                                <p className="text-sm mb-3" style={{ color: "var(--text-secondary)" }}>
                                    {finding.auto_fix.explanation}
                                </p>

                                {/* Original Code */}
                                {finding.auto_fix.original_code && (
                                    <div className="mb-2">
                                        <span className="text-xs font-bold" style={{ color: "#f87171" }}>❌ BEFORE (vulnerable):</span>
                                        <pre className="code-block mt-1" style={{ borderColor: "rgba(248,113,113,0.3)" }}>
                                            {finding.auto_fix.original_code}
                                        </pre>
                                    </div>
                                )}

                                {/* Fixed Code */}
                                {finding.auto_fix.fixed_code && (
                                    <div className="mb-2">
                                        <span className="text-xs font-bold" style={{ color: "var(--accent-green)" }}>✅ AFTER (fixed):</span>
                                        <pre className="code-block mt-1" style={{ borderColor: "rgba(16,185,129,0.3)" }}>
                                            {finding.auto_fix.fixed_code}
                                        </pre>
                                    </div>
                                )}

                                {/* Dependencies & Imports */}
                                {(finding.auto_fix.imports_needed.length > 0 || finding.auto_fix.dependencies_needed.length > 0) && (
                                    <div className="flex gap-4 mt-3 text-xs">
                                        {finding.auto_fix.imports_needed.length > 0 && (
                                            <div>
                                                <span style={{ color: "var(--text-muted)" }}>Imports:</span>
                                                <pre className="mt-1 p-2 rounded-lg font-mono"
                                                    style={{ background: "var(--bg-card)", color: "var(--accent-cyan)" }}>
                                                    {finding.auto_fix.imports_needed.join('\n')}
                                                </pre>
                                            </div>
                                        )}
                                        {finding.auto_fix.dependencies_needed.length > 0 && (
                                            <div>
                                                <span style={{ color: "var(--text-muted)" }}>Install:</span>
                                                <pre className="mt-1 p-2 rounded-lg font-mono"
                                                    style={{ background: "var(--bg-card)", color: "var(--accent-amber)" }}>
                                                    pip install {finding.auto_fix.dependencies_needed.join(' ')}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Breaking Changes Warning */}
                                {finding.auto_fix.breaking_changes.length > 0 && (
                                    <div className="mt-3 p-2 rounded-lg" style={{
                                        background: "rgba(248,113,113,0.08)",
                                        border: "1px solid rgba(248,113,113,0.2)",
                                    }}>
                                        <span className="text-xs font-bold" style={{ color: "#f87171" }}>⚠️ Breaking Changes:</span>
                                        <ul className="mt-1 space-y-0.5">
                                            {finding.auto_fix.breaking_changes.map((bc, i) => (
                                                <li key={i} className="text-xs" style={{ color: "var(--text-secondary)" }}>• {bc}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Fix Confidence */}
                                <div className="flex items-center gap-2 mt-3">
                                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>Fix confidence:</span>
                                    <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg-primary)" }}>
                                        <div className="h-full rounded-full" style={{
                                            width: `${Math.round(finding.auto_fix.confidence * 100)}%`,
                                            background: "linear-gradient(90deg, var(--accent-green), var(--accent-cyan))",
                                        }} />
                                    </div>
                                    <span className="text-xs font-semibold" style={{ color: "var(--accent-green)" }}>
                                        {Math.round(finding.auto_fix.confidence * 100)}%
                                    </span>
                                </div>
                            </div>
                        </section>
                    )}

                    {/* Explain Steps */}
                    {finding.explain_steps.length > 0 && (
                        <section>
                            <h4 className="section-label">🧠 Reasoning Steps</h4>
                            <ul className="space-y-1">
                                {finding.explain_steps.map((step, i) => (
                                    <li key={i} className="text-sm flex items-start gap-2" style={{ color: "var(--text-secondary)" }}>
                                        <span className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold"
                                            style={{ background: "rgba(99,102,241,0.15)", color: "var(--accent-blue)" }}>
                                            {i + 1}
                                        </span>
                                        {step}
                                    </li>
                                ))}
                            </ul>
                        </section>
                    )}

                    {/* Confidence */}
                    <section>
                        <h4 className="section-label">🎯 Confidence</h4>
                        <div className="flex items-center gap-3">
                            <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-primary)" }}>
                                <div className="h-full rounded-full" style={{
                                    width: `${Math.min(100, Math.max(0, (finding.confidence ?? 0) * 100))}%`,
                                    background: "linear-gradient(90deg, var(--gradient-start), var(--gradient-end))",
                                }} />
                            </div>
                            <span className="text-sm font-semibold">{Math.round((finding.confidence ?? 0) * 100)}%</span>
                        </div>
                    </section>
                </div>
            </div>

        </div>
    );
}
