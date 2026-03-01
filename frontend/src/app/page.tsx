"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { uploadRepo, startRun } from "@/lib/api";
import type { SkillType, PermissionLevel, RunMode } from "@/types/schemas";

const SKILLS: { id: SkillType; label: string; icon: string; desc: string; slash: string }[] = [
  { id: "security", label: "Security", icon: "🛡️", desc: "OWASP defensive vulnerability scan", slash: "/security" },
  { id: "tests", label: "Tests", icon: "🧪", desc: "Framework-aware test generation", slash: "/tests" },
  { id: "speedup", label: "Algorithmic Opt", icon: "🔬", desc: "Big-O complexity & data structure optimization", slash: "/perf" },
  { id: "architecture", label: "Architecture", icon: "🏗️", desc: "Design review + migration plan", slash: "/arch" },
  { id: "prompt_quality", label: "Prompt Quality", icon: "✨", desc: "Meta-agent prompt optimization", slash: "/prompts" },
];

const PERMISSIONS: { id: PermissionLevel; label: string; icon: string; desc: string }[] = [
  { id: "read_only", label: "Read Only", icon: "👁️", desc: "Analyze and report only" },
  { id: "propose", label: "Propose Changes", icon: "📝", desc: "Generate patches & tests" },
  { id: "apply", label: "Apply & Check", icon: "🚀", desc: "Apply patches + run checks (future)" },
];

export default function HomePage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [selectedSkills, setSelectedSkills] = useState<SkillType[]>(["security"]);
  const [permission, setPermission] = useState<PermissionLevel>("propose");
  const [mode, setMode] = useState<RunMode>("manual");
  const [userRequest, setUserRequest] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);

  const toggleSkill = (skill: SkillType) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  const handleFile = (f: File) => {
    if (f.name.endsWith(".zip")) {
      setFile(f);
      setError("");
    } else {
      setError("Please upload a .zip file");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  };

  const handleAutoInput = (value: string) => {
    setUserRequest(value);
    const slashMap: Record<string, SkillType> = {
      "/security": "security",
      "/tests": "tests",
      "/perf": "speedup",
      "/arch": "architecture",
      "/prompts": "prompt_quality",
    };
    for (const [cmd, skill] of Object.entries(slashMap)) {
      if (value.includes(cmd) && !selectedSkills.includes(skill)) {
        setSelectedSkills((prev) => [...prev, skill]);
      }
    }
  };

  const handleRun = async () => {
    if (!file) return setError("Please upload a repo zip file first");
    if (mode === "manual" && selectedSkills.length === 0) return setError("Select at least one skill");
    if (mode === "auto" && !userRequest.trim()) return setError("Tell the AI what you want");

    setLoading(true);
    setError("");

    try {
      const m = await uploadRepo(file);
      const { run_id } = await startRun({
        repo_id: m.repo_id,
        skills: selectedSkills,
        permission,
        mode,
        user_request: userRequest,
      });
      router.push(`/run/${run_id}?repo_id=${m.repo_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full opacity-15"
          style={{ background: "radial-gradient(circle, #ff6b2b, transparent)" }} />
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full opacity-10"
          style={{ background: "radial-gradient(circle, #6366f1, transparent)" }} />
        <div className="absolute top-1/3 right-1/4 w-[300px] h-[300px] rounded-full opacity-8"
          style={{ background: "radial-gradient(circle, #f59e0b, transparent)" }} />
        {/* Grid overlay */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)", backgroundSize: "60px 60px" }} />
      </div>

      <div className="relative z-10 w-full max-w-2xl animate-fade-in">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm mb-5 mistral-badge font-semibold">
            <span className="animate-float inline-block">🤖</span>
            Powered by Mistral AI
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-3 text-gradient-mistral">
            Code Co-Worker
          </h1>
          <p className="text-lg" style={{ color: "var(--text-secondary)" }}>
            Upload your codebase — AI agents analyze security, performance, tests & architecture
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {["Self-Reflection", "Dependency Scan", "Health Scoring", "Critic Agent"].map((f) => (
              <span key={f} className="text-xs px-3 py-1 rounded-full"
                style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)", color: "var(--accent-blue)" }}>
                {f}
              </span>
            ))}
          </div>
        </div>

        {/* Upload Zone */}
        <div
          className={`glass-strong rounded-2xl p-8 mb-5 text-center cursor-pointer transition-all duration-300 glow-card
            ${dragActive ? "ring-2 ring-orange-500/60 scale-[1.01]" : "hover:border-orange-500/30"}`}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
        >
          <input ref={fileRef} type="file" accept=".zip" className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
          {file ? (
            <div className="space-y-2 animate-scale-in">
              <div className="text-5xl animate-float">📦</div>
              <p className="font-bold text-lg">{file.name}</p>
              <p style={{ color: "var(--text-muted)" }}>{(file.size / 1024).toFixed(1)} KB — Click to change</p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-5xl">📁</div>
              <p className="font-bold text-lg">Drop your repo .zip here</p>
              <p style={{ color: "var(--text-muted)" }}>or click to browse</p>
            </div>
          )}
        </div>

        {/* Mode Toggle */}
        <div className="flex gap-2 mb-5">
          {(["manual", "auto"] as RunMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="flex-1 py-3 rounded-xl text-sm font-bold transition-all duration-300"
              style={{
                background: mode === m
                  ? "linear-gradient(135deg, rgba(255,107,43,0.12), rgba(99,102,241,0.12))"
                  : "var(--bg-card)",
                border: `1px solid ${mode === m ? "rgba(255,107,43,0.35)" : "var(--border)"}`,
                color: mode === m ? "var(--mistral-orange)" : "var(--text-secondary)",
                boxShadow: mode === m ? "0 0 20px rgba(255,107,43,0.08)" : "none",
              }}
            >
              {m === "manual" ? "🎯 Manual — Pick Skills" : "🤖 Auto — Describe Intent"}
            </button>
          ))}
        </div>

        {/* Auto Mode: Chat Input */}
        {mode === "auto" && (
          <div className="mb-5 animate-slide-up">
            <textarea
              value={userRequest}
              onChange={(e) => handleAutoInput(e.target.value)}
              placeholder="Tell me what you want... (e.g. 'Review security and generate tests' or use /security /tests /perf /arch /prompts)"
              rows={3}
              className="w-full px-4 py-3.5 rounded-xl text-sm resize-none outline-none transition-all duration-200 focus:ring-1 focus:ring-orange-500/30"
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            />
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {SKILLS.map((s) => (
                <button
                  key={s.slash}
                  onClick={() => handleAutoInput(userRequest + " " + s.slash)}
                  className="text-xs px-2.5 py-1 rounded-lg transition-all duration-200 hover:bg-[var(--bg-card)]"
                  style={{ background: "var(--bg-hover)", color: "var(--text-muted)" }}
                >
                  {s.slash}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Manual Mode: Skills */}
        {mode === "manual" && (
          <div className="mb-5 animate-slide-up">
            <h2 className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--text-muted)" }}>
              Select Analysis Skills
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {SKILLS.map((skill, i) => {
                const active = selectedSkills.includes(skill.id);
                return (
                  <button key={skill.id} onClick={() => toggleSkill(skill.id)}
                    className="glass rounded-xl p-4 text-left transition-all duration-300 glow-card animate-fade-in"
                    style={{
                      animationDelay: `${i * 60}ms`,
                      border: active ? "1px solid rgba(255,107,43,0.4)" : undefined,
                      background: active ? "rgba(255,107,43,0.08)" : undefined,
                      boxShadow: active ? "0 0 20px rgba(255,107,43,0.06)" : undefined,
                    }}
                  >
                    <div className="text-2xl mb-1.5">{skill.icon}</div>
                    <div className="font-bold text-sm">{skill.label}</div>
                    <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{skill.desc}</div>
                    <div className="text-xs mt-1.5 font-mono" style={{ color: active ? "var(--mistral-orange)" : "var(--accent-blue)", opacity: 0.7 }}>
                      {skill.slash}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Permission Level */}
        <div className="mb-5">
          <h2 className="text-xs font-semibold uppercase tracking-wider mb-3"
            style={{ color: "var(--text-muted)" }}>
            Permission Level
          </h2>
          <div className="grid grid-cols-3 gap-2">
            {PERMISSIONS.map((p) => (
              <button key={p.id} onClick={() => setPermission(p.id)}
                className="rounded-xl p-3 text-center transition-all duration-300"
                style={{
                  background: permission === p.id ? "rgba(255,107,43,0.08)" : "var(--bg-card)",
                  border: `1px solid ${permission === p.id ? "rgba(255,107,43,0.35)" : "var(--border)"}`,
                  color: permission === p.id ? "var(--mistral-orange)" : "var(--text-secondary)",
                  opacity: p.id === "apply" ? 0.4 : 1,
                }}
                disabled={p.id === "apply"}
              >
                <div className="text-xl">{p.icon}</div>
                <div className="text-xs font-bold mt-1">{p.label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-xl text-sm animate-fade-in"
            style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", color: "#f87171" }}>
            ⚠️ {error}
          </div>
        )}

        {/* Run Button */}
        <button onClick={handleRun} disabled={loading}
          className="w-full py-4 rounded-xl font-bold text-lg text-white transition-all duration-300 disabled:opacity-50"
          style={{
            backgroundImage: loading
              ? "none"
              : "linear-gradient(135deg, var(--mistral-orange), var(--mistral-gold), var(--accent-blue))",
            backgroundColor: loading ? "var(--bg-card)" : "transparent",
            backgroundSize: "200% 200%",
            animation: loading ? "none" : "gradient-shift 4s ease infinite",
            boxShadow: loading ? "none" : "0 4px 25px rgba(255,107,43,0.2)",
          }}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin-slow">⚙️</span> Uploading & Starting...
            </span>
          ) : (
            "🚀 Run Analysis"
          )}
        </button>

        {/* Footer */}
        <p className="text-center text-xs mt-6" style={{ color: "var(--text-muted)" }}>
          Powered by <span className="font-semibold" style={{ color: "var(--mistral-orange)" }}>Mistral AI</span> • LangGraph Orchestration • Self-Reflection Critic
        </p>
      </div>
    </div>
  );
}
