"use client";

import { useRef, useEffect } from "react";
import type { AgentEvent } from "@/types/schemas";

interface AgentTimelineProps {
    events: AgentEvent[];
    isConnected: boolean;
}

const iconMap: Record<string, string> = {
    supervisor_started: "🎯",
    agent_started: "🚀",
    agent_progress: "⏳",
    agent_done: "✅",
    supervisor_done: "🏁",
    error: "❌",
};

const agentColorMap: Record<string, string> = {
    supervisor: "var(--accent-blue)",
    dependency: "var(--mistral-orange)",
    security: "var(--accent-red)",
    tests: "var(--accent-green)",
    algorithmic_opt: "var(--accent-amber)",
    speedup: "var(--accent-amber)",  // backward compat
    architecture: "var(--accent-cyan)",
    prompt_quality: "var(--accent-purple)",
    critic: "#f472b6",
};

const agentIconMap: Record<string, string> = {
    supervisor: "🎯",
    dependency: "📦",
    security: "🛡️",
    tests: "🧪",
    algorithmic_opt: "🔬",
    speedup: "🔬",  // backward compat
    architecture: "🏗️",
    prompt_quality: "✨",
    critic: "🧠",
};

export default function AgentTimeline({
    events,
    isConnected,
}: AgentTimelineProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new events
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [events.length]);

    // Determine if event is a "highlight" (started/done/error/important progress)
    const isHighlight = (evt: AgentEvent) =>
        evt.event_type === "agent_started" ||
        evt.event_type === "agent_done" ||
        evt.event_type === "supervisor_started" ||
        evt.event_type === "supervisor_done" ||
        evt.event_type === "error" ||
        evt.message.includes("Found:") ||
        evt.message.includes("⚠️") ||
        evt.message.includes("🔴") ||
        evt.message.includes("🔥");

    return (
        <div className="h-full flex flex-col">
            <div className="p-3 border-b flex items-center justify-between"
                style={{ borderColor: "var(--border)" }}>
                <div className="flex items-center gap-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider"
                        style={{ color: "var(--text-muted)" }}>
                        Agent Timeline
                    </h3>
                    <span className="text-xs px-1.5 py-0.5 rounded-md tabular-nums"
                        style={{ background: "var(--bg-primary)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                        {events.length}
                    </span>
                </div>
                {isConnected && (
                    <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--accent-green)" }}>
                        <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                        Live
                    </span>
                )}
            </div>
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-0.5">
                {events.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3"
                        style={{ color: "var(--text-muted)" }}>
                        <span className="text-3xl animate-float">⏳</span>
                        <p className="text-sm font-medium">Waiting for events...</p>
                    </div>
                ) : (
                    events.map((evt, i) => {
                        const highlight = isHighlight(evt);
                        const color = agentColorMap[evt.agent] || "var(--accent-blue)";
                        const agentIcon = agentIconMap[evt.agent] || "📌";

                        return (
                            <div
                                key={i}
                                className={`flex items-start gap-2.5 py-1.5 px-2.5 rounded-lg animate-fade-in transition-all duration-200
                                    ${highlight ? "" : "opacity-75"}`}
                                style={{
                                    animationDelay: `${Math.min(i * 20, 300)}ms`,
                                    background: highlight ? `${color}08` : "transparent",
                                    borderLeft: highlight ? `2px solid ${color}` : "2px solid transparent",
                                }}
                            >
                                {/* Event icon */}
                                <span className="text-sm flex-shrink-0 mt-0.5"
                                    style={{ minWidth: "1.2rem", textAlign: "center" }}>
                                    {evt.event_type === "agent_started" || evt.event_type === "supervisor_started"
                                        ? agentIcon
                                        : iconMap[evt.event_type] || "📌"}
                                </span>

                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        {/* Agent badge */}
                                        {evt.agent && (
                                            <span
                                                className="text-[10px] font-bold px-1.5 py-0.5 rounded-md uppercase tracking-wider"
                                                style={{
                                                    background: `${color}15`,
                                                    color: color,
                                                    border: `1px solid ${color}25`,
                                                }}
                                            >
                                                {evt.agent}
                                            </span>
                                        )}

                                        {/* Event type badge for started/done */}
                                        {(evt.event_type === "agent_started" || evt.event_type === "agent_done") && (
                                            <span className="text-[10px] font-semibold px-1 py-0.5 rounded"
                                                style={{
                                                    background: evt.event_type === "agent_done" ? "rgba(16,185,129,0.1)" : "rgba(99,102,241,0.1)",
                                                    color: evt.event_type === "agent_done" ? "var(--accent-green)" : "var(--accent-blue)",
                                                }}>
                                                {evt.event_type === "agent_started" ? "STARTED" : "DONE"}
                                            </span>
                                        )}

                                        {/* Findings count */}
                                        {evt.findings_count > 0 && (
                                            <span className="text-[10px] font-bold px-1 py-0.5 rounded"
                                                style={{ background: "rgba(245,158,11,0.1)", color: "var(--accent-amber)" }}>
                                                {evt.findings_count} findings
                                            </span>
                                        )}

                                        {/* Timestamp */}
                                        {evt.timestamp && (
                                            <span className="text-[10px] ml-auto tabular-nums" style={{ color: "var(--text-muted)" }}>
                                                {new Date(evt.timestamp).toLocaleTimeString()}
                                            </span>
                                        )}
                                    </div>

                                    {/* Message */}
                                    <p className="text-xs mt-0.5 leading-relaxed"
                                        style={{ color: highlight ? "var(--text-primary)" : "var(--text-secondary)" }}>
                                        {evt.message}
                                    </p>

                                    {/* Progress bar for in-progress events */}
                                    {evt.progress > 0 && evt.progress < 1 && (
                                        <div className="mt-1.5 h-1 rounded-full overflow-hidden"
                                            style={{ background: "var(--bg-primary)" }}>
                                            <div
                                                className="h-full rounded-full transition-all duration-700 ease-out"
                                                style={{
                                                    width: `${evt.progress * 100}%`,
                                                    background: `linear-gradient(90deg, ${color}, ${color}cc)`,
                                                    boxShadow: `0 0 6px ${color}40`,
                                                }}
                                            />
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
