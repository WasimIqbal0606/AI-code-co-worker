"use client";

import { useState } from "react";
import type { FileEntry } from "@/types/schemas";

interface FileManifestProps {
    files: FileEntry[];
}

export default function FileManifest({ files }: FileManifestProps) {
    const [search, setSearch] = useState("");

    const filtered = files.filter((f) =>
        f.path.toLowerCase().includes(search.toLowerCase())
    );

    const langColor: Record<string, string> = {
        python: "#3b82f6",
        javascript: "#eab308",
        typescript: "#2563eb",
        html: "#f97316",
        css: "#a855f7",
        json: "#22d3ee",
        markdown: "#6b7280",
    };

    return (
        <div className="h-full flex flex-col">
            <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-2"
                    style={{ color: "var(--text-muted)" }}>
                    Files ({files.length})
                </h3>
                <input
                    type="text"
                    placeholder="Search files..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full px-3 py-1.5 text-sm rounded-lg outline-none"
                    style={{
                        background: "var(--bg-primary)",
                        border: "1px solid var(--border)",
                        color: "var(--text-primary)",
                    }}
                />
            </div>
            <div className="flex-1 overflow-y-auto p-2">
                {filtered.map((f) => (
                    <div
                        key={f.path}
                        className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-colors cursor-default hover:bg-[var(--bg-hover)]"
                    >
                        <span
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ background: langColor[f.language] || "#6b7280" }}
                        />
                        <span className="truncate flex-1" style={{ fontFamily: "JetBrains Mono, monospace" }}>
                            {f.path}
                        </span>
                        <span style={{ color: "var(--text-muted)" }}>
                            {f.size_bytes > 1024
                                ? `${(f.size_bytes / 1024).toFixed(1)}K`
                                : `${f.size_bytes}B`}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
