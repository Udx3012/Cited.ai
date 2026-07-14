"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { 
  Layers, FileText, Zap, Shield, Sparkles, HelpCircle, 
  ArrowUpRight, ArrowDownRight, TrendingUp, Cpu, Server, History
} from "lucide-react";

export default function DashboardOverview() {
  const [metricTab, setMetricTab] = useState("latency");

  // Mock KPI Cards
  const kpis = [
    { title: "Chunks Indexed", value: "412", subtitle: "Across 3 documents", icon: Layers, trend: "+12.4%", trendType: "up" },
    { title: "Average Latency", value: "842 ms", subtitle: "P95 response time", icon: Zap, trend: "-4.2%", trendType: "up" }, // lower latency is good
    { title: "Faithfulness", value: "94.6%", subtitle: "LLM-as-judge metric", icon: Shield, trend: "+1.8%", trendType: "up" },
    { title: "Hallucination Rate", value: "0.00%", subtitle: "Strict ground checks", icon: Sparkles, trend: "0.00%", trendType: "neutral" }
  ];

  // Mock recent queries log
  const recentQueries = [
    { q: "What does the Q4 report say about regulatory risk?", time: "2 min ago", status: "Faithful", score: "96%", latency: "842ms", cites: 3 },
    { q: "Who must comply with GDPR guidelines under Article 3?", time: "15 min ago", status: "Faithful", score: "94%", latency: "790ms", cites: 2 },
    { q: "What are the audit thresholds for structural engineering standards?", time: "1 hr ago", status: "Faithful", score: "93%", latency: "910ms", cites: 3 },
    { q: "Explain the safety factor rules in Eurocode 3.", time: "3 hr ago", status: "Faithful", score: "95%", latency: "812ms", cites: 4 }
  ];

  return (
    <div className="space-y-6">
      
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-serif text-white tracking-tight">Overview</h1>
        <p className="text-zinc-400 text-sm font-normal mt-1">
          Monitor your document-grounded RAG pipeline ingestion and search performance.
        </p>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div 
              key={idx}
              className="glass-card p-5 rounded-2xl relative overflow-hidden flex flex-col justify-between"
            >
              {/* Card ambient blur glow */}
              <div className="absolute top-0 right-0 w-16 h-16 bg-[#45A29E]/[0.01] rounded-bl-full pointer-events-none" />
              
              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs text-zinc-400 font-bold uppercase tracking-wider block">{kpi.title}</span>
                  <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-white/[0.04] flex items-center justify-center">
                    <Icon className="w-4 h-4 text-[#45A29E]" />
                  </div>
                </div>

                <h3 className="text-2xl font-semibold text-white tracking-tight mb-1">{kpi.value}</h3>
              </div>

              <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/[0.02]">
                <span className="text-xs text-zinc-400 font-medium">{kpi.subtitle}</span>
                <span className={`text-xs font-mono font-bold flex items-center gap-0.5 ${
                  kpi.trendType === "up" 
                    ? kpi.title.includes("Latency") ? "text-green-400" : "text-green-400" 
                    : "text-zinc-400"
                }`}>
                  {kpi.trendType === "up" && <TrendingUp className="w-3 h-3" />}
                  {kpi.trend}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Charts & Analytics Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* SVG Performance Chart (2 cols) */}
        <div className="lg:col-span-2 glass-card rounded-2xl p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-sm font-semibold text-white">System Performance</h3>
              <span className="text-xs text-zinc-400 font-normal mt-1 block">Faithfulness and response latency over the last 24 hours</span>
            </div>
            
            {/* Chart toggle controls */}
            <div className="flex gap-1.5 bg-zinc-950 p-1 rounded-lg border border-white/[0.03]">
              <button 
                onClick={() => setMetricTab("latency")}
                className={`text-xs font-semibold px-2.5 py-1 rounded-md transition-all ${
                  metricTab === "latency" ? "bg-zinc-905 text-white border border-white/[0.03]" : "text-zinc-400 hover:text-zinc-300"
                }`}
              >
                Latency
              </button>
              <button 
                onClick={() => setMetricTab("faithfulness")}
                className={`text-xs font-semibold px-2.5 py-1 rounded-md transition-all ${
                  metricTab === "faithfulness" ? "bg-zinc-905 text-white border border-white/[0.03]" : "text-zinc-400 hover:text-zinc-300"
                }`}
              >
                Faithfulness
              </button>
            </div>
          </div>

          {/* Glowing Neon Line SVG Chart */}
          <div className="h-64 relative w-full flex items-end">
            <svg className="w-full h-full overflow-visible" viewBox="0 0 500 200">
              <defs>
                {/* Neon teal shadow glow */}
                <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                {/* Background area gradient fill */}
                <linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#45A29E" stopOpacity="0.12" />
                  <stop offset="100%" stopColor="#45A29E" stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              <line x1="0" y1="50" x2="500" y2="50" stroke="rgba(255,255,255,0.02)" strokeDasharray="3 3" />
              <line x1="0" y1="100" x2="500" y2="100" stroke="rgba(255,255,255,0.02)" strokeDasharray="3 3" />
              <line x1="0" y1="150" x2="500" y2="150" stroke="rgba(255,255,255,0.02)" strokeDasharray="3 3" />

              {/* Dynamic Path Plots based on state */}
              {metricTab === "latency" ? (
                <>
                  {/* Area fill path */}
                  <path 
                    d="M 0,200 L 0,110 L 80,135 L 160,82 L 240,95 L 320,118 L 400,68 L 500,74 L 500,200 Z" 
                    fill="url(#area-gradient)" 
                  />
                  {/* Line path */}
                  <path 
                    d="M 0,110 L 80,135 L 160,82 L 240,95 L 320,118 L 400,68 L 500,74" 
                    fill="none" 
                    stroke="#45A29E" 
                    strokeWidth="2.5" 
                    filter="url(#neon-glow)"
                  />
                  {/* Joint points */}
                  <circle cx="80" cy="135" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="160" cy="82" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="240" cy="95" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="320" cy="118" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="400" cy="68" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                </>
              ) : (
                <>
                  {/* Area fill path */}
                  <path 
                    d="M 0,200 L 0,65 L 80,50 L 160,55 L 240,40 L 320,45 L 400,32 L 500,35 L 500,200 Z" 
                    fill="url(#area-gradient)" 
                  />
                  {/* Line path */}
                  <path 
                    d="M 0,65 L 80,50 L 160,55 L 240,40 L 320,45 L 400,32 L 500,35" 
                    fill="none" 
                    stroke="#45A29E" 
                    strokeWidth="2.5" 
                    filter="url(#neon-glow)"
                  />
                  {/* Joint points */}
                  <circle cx="80" cy="50" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="160" cy="55" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="240" cy="40" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="320" cy="45" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                  <circle cx="400" cy="32" r="3.5" fill="#45A29E" stroke="#030303" strokeWidth="1" />
                </>
              )}
            </svg>

            {/* Y axis legend */}
            <div className="absolute left-2 top-2 text-xs font-mono text-zinc-400 flex flex-col justify-between h-48 pointer-events-none">
              <span>{metricTab === "latency" ? "1200ms" : "100%"}</span>
              <span>{metricTab === "latency" ? "800ms" : "95%"}</span>
              <span>{metricTab === "latency" ? "400ms" : "90%"}</span>
              <span>0</span>
            </div>
          </div>
          
          {/* X axis legend */}
          <div className="flex justify-between px-8 text-xs font-mono text-zinc-400 border-t border-white/[0.02] pt-3 mt-3">
            <span>24h ago</span>
            <span>18h ago</span>
            <span>12h ago</span>
            <span>6h ago</span>
            <span>Present</span>
          </div>
        </div>

        {/* Server & Node Status Cards (1 col) */}
        <div className="glass-card rounded-2xl p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white mb-1">RAG Pipeline Status</h3>
            <span className="text-xs text-zinc-400 font-normal block mb-4">Integrations health metrics</span>
            
            <div className="space-y-4">
              {[
                { name: "FastAPI Node Process", desc: "Render Web Service", status: "Healthy", active: true, icon: Server },
                { name: "Qdrant Vector Cluster", desc: "Managed Qdrant Cloud", status: "Connected", active: true, icon: Cpu },
                { name: "In-Memory BM25 Index", desc: "In-memory cache pool", status: "Synchronized", active: true, icon: Layers }
              ].map((node, idx) => {
                const Icon = node.icon;
                return (
                  <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-zinc-950/80 border border-white/[0.02]">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-white/[0.04] flex items-center justify-center text-zinc-400">
                        <Icon className="w-4 h-4 text-zinc-400" />
                      </div>
                      <div>
                        <span className="text-xs font-semibold text-zinc-200 block">{node.name}</span>
                        <span className="text-xs text-zinc-400 block font-normal">{node.desc}</span>
                      </div>
                    </div>
                    
                    <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/5 px-2 py-0.5 rounded border border-emerald-500/10">
                      {node.status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-white/[0.02] flex items-center justify-between text-zinc-400 text-xs font-mono">
            <span>Server version: v2.4</span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
              uptime: 99.98%
            </span>
          </div>
        </div>
      </div>

      {/* Recent Request Logs */}
      <div className="glass-card rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.03]">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-[#45A29E]" />
            <h3 className="text-sm font-semibold text-white">Recent Query Logs</h3>
          </div>
          <span className="text-xs text-zinc-400 font-mono">Real-time update</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-400 font-sans">
            <thead>
              <tr className="text-xs text-zinc-400 font-bold uppercase tracking-wider border-b border-white/[0.02] pb-2">
                <th className="pb-3 font-semibold">User Question</th>
                <th className="pb-3 font-semibold">Faithfulness</th>
                <th className="pb-3 font-semibold text-right">Latency</th>
                <th className="pb-3 font-semibold text-right">Citations</th>
                <th className="pb-3 font-semibold text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.01]">
              {recentQueries.map((item, idx) => (
                <tr key={idx} className="hover:bg-zinc-900/10 transition-colors">
                  <td className="py-3 font-medium text-zinc-200 truncate max-w-sm">{item.q}</td>
                  <td className="py-3">
                    <span className="font-bold text-green-400 bg-green-500/5 px-2 py-0.5 rounded border border-green-500/10 text-xs font-mono">
                      {item.score}
                    </span>
                  </td>
                  <td className="py-3 text-right font-mono font-medium text-zinc-300">{item.latency}</td>
                  <td className="py-3 text-right font-mono text-zinc-400">{item.cites} verified</td>
                  <td className="py-3 text-right text-zinc-400 font-normal">{item.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
