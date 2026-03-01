"use client";

import type { HealthScores } from "@/types/schemas";

interface HealthScoreCardProps {
    scores: HealthScores;
}

interface GaugeProps {
    value: number;
    label: string;
    icon: string;
    color: string;
    size?: number;
    delay?: number;
}

function getScoreColor(value: number): string {
    if (value >= 80) return "#10b981";    // green
    if (value >= 60) return "#f59e0b";    // amber
    if (value >= 40) return "#f97316";    // orange
    return "#ef4444";                     // red
}

function getGradeLabel(value: number): string {
    if (value >= 90) return "A+";
    if (value >= 80) return "A";
    if (value >= 70) return "B";
    if (value >= 60) return "C";
    if (value >= 50) return "D";
    return "F";
}

function RadialGauge({ value, label, icon, color, size = 100, delay = 0 }: GaugeProps) {
    const radius = (size - 10) / 2;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (value / 100) * circumference;
    const scoreColor = color || getScoreColor(value);

    return (
        <div
            className="flex flex-col items-center gap-1.5 animate-fade-in"
            style={{ animationDelay: `${delay}ms` }}
        >
            <div className="relative" style={{ width: size, height: size }}>
                {/* Background ring */}
                <svg
                    width={size}
                    height={size}
                    className="transform -rotate-90"
                >
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        stroke="var(--border)"
                        strokeWidth="5"
                    />
                    {/* Animated fill ring */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        stroke={scoreColor}
                        strokeWidth="5"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="gauge-ring"
                        style={{
                            filter: `drop-shadow(0 0 6px ${scoreColor}50)`,
                            transition: "stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
                        }}
                    />
                </svg>
                {/* Center content */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-lg">{icon}</span>
                    <span
                        className="text-lg font-extrabold tabular-nums"
                        style={{ color: scoreColor }}
                    >
                        {value}
                    </span>
                </div>
            </div>
            <span
                className="text-xs font-semibold uppercase tracking-wider"
                style={{ color: "var(--text-muted)" }}
            >
                {label}
            </span>
        </div>
    );
}

export default function HealthScoreCard({ scores }: HealthScoreCardProps) {
    const overallColor = getScoreColor(scores.overall);
    const grade = getGradeLabel(scores.overall);

    const categories = [
        { key: "security", label: "Security", icon: "🛡️", color: "#ef4444" },
        { key: "performance", label: "Performance", icon: "⚡", color: "#f59e0b" },
        { key: "architecture", label: "Architecture", icon: "🏗️", color: "#22d3ee" },
        { key: "tests", label: "Tests", icon: "🧪", color: "#a855f7" },
    ] as const;

    return (
        <div className="animate-fade-in">
            {/* Overall score hero */}
            <div
                className="relative rounded-2xl p-5 mb-4 overflow-hidden"
                style={{
                    background: `linear-gradient(135deg, ${overallColor}08, ${overallColor}15)`,
                    border: `1px solid ${overallColor}30`,
                }}
            >
                {/* Subtle glow */}
                <div
                    className="absolute -top-20 -right-20 w-40 h-40 rounded-full opacity-20"
                    style={{
                        background: `radial-gradient(circle, ${overallColor}, transparent)`,
                    }}
                />

                <div className="relative flex items-center justify-between">
                    <div>
                        <p
                            className="text-xs font-semibold uppercase tracking-wider mb-1"
                            style={{ color: "var(--text-muted)" }}
                        >
                            Repository Health
                        </p>
                        <div className="flex items-baseline gap-2">
                            <span
                                className="text-4xl font-extrabold tabular-nums"
                                style={{ color: overallColor }}
                            >
                                {scores.overall}
                            </span>
                            <span
                                className="text-lg font-bold"
                                style={{ color: "var(--text-muted)" }}
                            >
                                / 100
                            </span>
                        </div>
                        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
                            {scores.overall >= 80
                                ? "Your codebase is in great shape! 🎉"
                                : scores.overall >= 60
                                    ? "Some improvements needed for production readiness."
                                    : scores.overall >= 40
                                        ? "Significant issues detected — review findings carefully."
                                        : "Critical issues found — immediate action recommended."}
                        </p>
                    </div>

                    {/* Grade badge */}
                    <div
                        className="flex flex-col items-center justify-center w-16 h-16 rounded-xl"
                        style={{
                            background: `${overallColor}15`,
                            border: `2px solid ${overallColor}40`,
                        }}
                    >
                        <span
                            className="text-2xl font-black"
                            style={{ color: overallColor }}
                        >
                            {grade}
                        </span>
                    </div>
                </div>
            </div>

            {/* Category gauges */}
            <div className="grid grid-cols-4 gap-3">
                {categories.map((cat, i) => (
                    <div
                        key={cat.key}
                        className="rounded-xl p-3 flex flex-col items-center"
                        style={{
                            background: "var(--bg-card)",
                            border: "1px solid var(--border)",
                        }}
                    >
                        <RadialGauge
                            value={scores[cat.key]}
                            label={cat.label}
                            icon={cat.icon}
                            color={getScoreColor(scores[cat.key])}
                            size={80}
                            delay={i * 100}
                        />
                    </div>
                ))}
            </div>
        </div>
    );
}
