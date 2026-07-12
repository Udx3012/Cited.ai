"use client";

import React, { useState } from "react";
import { 
  Shield, CheckCircle2, AlertTriangle, AlertCircle, 
  HelpCircle, Sparkles, TrendingUp, Play, History, RefreshCw, BarChart2
} from "lucide-react";

export default function RAGEvaluation() {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("Idle");

  // Dynamic metrics state
  const [faithfulness, setFaithfulness] = useState("92.4%");
  const [accuracy, setAccuracy] = useState("95.0%");
  const [precision, setPrecision] = useState("89.5%");
  const [hallucinations, setHallucinations] = useState("2.8%");

  // Chart data heights state
  const [barHeights, setBarHeights] = useState(["80%", "45%", "25%", "10%", "10%"]);
  const [runCount, setRunCount] = useState([28, 12, 6, 2, 2]);

  const runEvaluationSuite = () => {
    if (isRunning) return;
    setIsRunning(true);
    setProgress(0);
    setStatusText("Initializing Golden dataset...");

    // Stage progression
    const intervals = [
      { t: 800, p: 25, txt: "Feeding test questions to retrieval stream..." },
      { t: 1600, p: 55, txt: "Running BM25 lexical & dense similarity checks..." },
      { t: 2400, p: 80, txt: "Verifying LLM grounded responses via judge..." },
      { t: 3200, p: 100, txt: "Compiling statistical indexes..." }
    ];

    intervals.forEach(step => {
      setTimeout(() => {
        setProgress(step.p);
        setStatusText(step.txt);

        if (step.p === 100) {
          setTimeout(() => {
            setIsRunning(false);
            setStatusText("Completed");

            // Slightly randomize metrics to simulate a live evaluation run
            setFaithfulness((91 + Math.random() * 6).toFixed(1) + "%");
            setAccuracy((93 + Math.random() * 5).toFixed(1) + "%");
            setPrecision((88 + Math.random() * 7).toFixed(1) + "%");
            setHallucinations((1.5 + Math.random() * 2).toFixed(1) + "%");
            
            // Randomize charts
            const newCounts = [
              Math.floor(25 + Math.random() * 10),
              Math.floor(10 + Math.random() * 6),
              Math.floor(4 + Math.random() * 5),
              Math.floor(1 + Math.random() * 3),
              Math.floor(1 + Math.random() * 2)
            ];
            const maxCount = Math.max(...newCounts);
            setRunCount(newCounts);
            setBarHeights(newCounts.map(c => `${(c / maxCount * 90).toFixed(0)}%`));

          }, 400);
        }
      }, step.t);
    });
  };

  const evalMetrics = [
    { title: "Avg Faithfulness", value: faithfulness, status: "Passed", color: "text-emerald-400" },
    { title: "Retrieval Precision", value: precision, status: "Passed", color: "text-emerald-400" },
    { title: "Context Recall", value: accuracy, status: "Optimal", color: "text-[#45A29E]" },
    { title: "Hallucination Rate", value: hallucinations, status: "Attention", color: "text-amber-400" }
  ];

  const failures = [
    {
      q: "Explain EMEA yield margins under negative rate stress.",
      faithfulness: "72%",
      reason: "Hallucination detected. AI mentioned 'yield compression of 4.2%' which was not grounded in Q4-Report.pdf.",
      file: "Q4-Report.pdf"
    },
    {
      q: "Who is responsible for auditing under GDPR Article 4 guidelines?",
      faithfulness: "76%",
      reason: "Recall gap. AI omitted the 'Data Protection Officer' segment from GDPR-Handbook.pdf.",
      file: "GDPR-Handbook.pdf"
    }
  ];

  return (
    <div className="space-y-6 text-left">
      
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-serif text-white tracking-tight">Evaluation Dashboard</h1>
          <p className="text-zinc-400 text-xs font-normal mt-1">
            Analyze RAG pipeline synthesis correctness, citation overlaps, and hallucination rates.
          </p>
        </div>
        
        {/* Run evaluation button */}
        <button 
          onClick={runEvaluationSuite}
          disabled={isRunning}
          className="flex items-center gap-2 bg-[#45A29E] hover:bg-[#398a87] text-black px-5 py-2.5 rounded-full text-xs font-bold transition-all hover:scale-[1.02] shadow-[0_4px_15px_rgba(69,162,158,0.12)] cursor-pointer disabled:opacity-50"
        >
          {isRunning ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 fill-black" />
          )}
          Run Evaluation Suite
        </button>
      </div>

      {/* Progress banner */}
      {isRunning && (
        <div className="glass-card p-4 rounded-2xl border border-[#45A29E]/30 bg-[#45A29E]/[0.01] space-y-2">
          <div className="flex justify-between text-xs text-zinc-300 font-semibold font-mono">
            <span>{statusText}</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full h-1.5 bg-zinc-950 rounded-full overflow-hidden">
            <div className="h-full bg-[#45A29E] transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {/* Evaluation Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {evalMetrics.map((item, idx) => (
          <div key={idx} className="glass-card p-5 rounded-2xl relative overflow-hidden flex flex-col justify-between h-32">
            <div className="absolute top-0 right-0 w-16 h-16 bg-[#45A29E]/[0.005] rounded-bl-full pointer-events-none" />
            <div>
              <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">{item.title}</span>
              <h3 className={`text-2xl font-semibold tracking-tight ${item.color}`}>{item.value}</h3>
            </div>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/[0.02] text-[9px] font-mono">
              <span className="text-zinc-400">Test size: 50 cases</span>
              <span className={`font-bold ${
                item.status === "Attention" ? "text-amber-400" : "text-zinc-400"
              }`}>{item.status}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Visual Distributions Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Score Distribution Chart */}
        <div className="lg:col-span-2 glass-card rounded-2xl p-5 flex flex-col justify-between">
          <div className="mb-6">
            <div className="flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-[#45A29E]" />
              <h3 className="text-sm font-semibold text-white">Score Distribution</h3>
            </div>
            <span className="text-[10px] text-zinc-400 font-normal mt-0.5 block">Faithfulness spread across 50 simulated tests</span>
          </div>

          <div className="h-48 flex items-end justify-between gap-6 px-4">
            {[
              { label: "1.00", idx: 0 },
              { label: "0.90", idx: 1 },
              { label: "0.80", idx: 2 },
              { label: "0.70", idx: 3 },
              { label: "< 0.70", idx: 4 }
            ].map((bar) => (
              <div key={bar.idx} className="flex-1 flex flex-col items-center gap-3 h-full justify-end">
                <span className="text-[9px] font-mono text-zinc-400">{runCount[bar.idx]} runs</span>
                <div className="w-full relative rounded-t-lg bg-zinc-950 border border-white/[0.04] overflow-hidden flex items-end" style={{ height: "70%" }}>
                  <div 
                    className="w-full bg-gradient-to-t from-[#45A29E]/30 to-[#45A29E] rounded-t-md transition-all duration-500 shadow-[0_0_15px_rgba(69,162,158,0.15)]"
                    style={{ height: barHeights[bar.idx] }}
                  />
                </div>
                <span className="text-[10px] font-semibold text-zinc-400 font-mono">{bar.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Evaluation Summary card */}
        <div className="glass-card rounded-2xl p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white mb-1">Golden Dataset</h3>
            <span className="text-[10px] text-zinc-400 font-normal block mb-4">Ground-truth validation configurations</span>

            <div className="space-y-3 font-mono text-xs">
              <div className="flex justify-between border-b border-white/[0.02] pb-2">
                <span className="text-zinc-400">Evaluator LLM:</span>
                <span className="text-zinc-200 font-semibold">Judge-Model-70B</span>
              </div>
              <div className="flex justify-between border-b border-white/[0.02] pb-2">
                <span className="text-zinc-400">Validation Mode:</span>
                <span className="text-zinc-200">Strict assertion</span>
              </div>
              <div className="flex justify-between border-b border-white/[0.02] pb-2">
                <span className="text-zinc-400">Total assertions:</span>
                <span className="text-zinc-200">150 checks</span>
              </div>
              <div className="flex justify-between pb-1">
                <span className="text-zinc-400">Target precision:</span>
                <span className="text-[#45A29E] font-semibold">&gt; 95%</span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-zinc-950 border border-white/[0.03] rounded-xl flex items-start gap-2.5 mt-6 text-left">
            <Sparkles className="w-4 h-4 text-[#45A29E] shrink-0 mt-0.5" />
            <p className="text-[10px] text-zinc-400 leading-relaxed font-normal">
              We recommend using strict validation on release branches to block index pollution from hall-prone responses.
            </p>
          </div>
        </div>
      </div>

      {/* Evaluated Queries Table list */}
      <div className="glass-card rounded-2xl p-5">
        <h3 className="text-xs font-bold text-zinc-350 uppercase tracking-wider mb-4 pb-2 border-b border-white/[0.03]">Golden Dataset Runs</h3>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-400 font-normal">
            <thead>
              <tr className="text-[9px] text-zinc-550 font-bold uppercase tracking-wider border-b border-white/[0.02]">
                <th className="pb-3 font-semibold">Target Query</th>
                <th className="pb-3 font-semibold">Matched Source</th>
                <th className="pb-3 font-semibold">Precision</th>
                <th className="pb-3 font-semibold">Recall</th>
                <th className="pb-3 font-semibold text-right">Judge Assessment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.01]">
              {[
                { q: "What does the Q4 report say about regulatory risk?", src: "Q4-Report.pdf", p: "94%", r: "98%", status: "Passed" },
                { q: "Who must comply with GDPR guidelines under Article 3?", src: "GDPR-Handbook.pdf", p: "92%", r: "95%", status: "Passed" },
                { q: "Audits on high-risk foundation models under AI Act", src: "AI-Act-Brief.pdf", p: "96%", r: "92%", status: "Passed" }
              ].map((row, idx) => (
                <tr key={idx} className="hover:bg-zinc-900/10 transition-colors">
                  <td className="py-3 font-medium text-zinc-200 truncate max-w-xs">{row.q}</td>
                  <td className="py-3 font-mono text-zinc-400 text-[11px]">{row.src}</td>
                  <td className="py-3 font-mono text-zinc-350">{row.p}</td>
                  <td className="py-3 font-mono text-zinc-350">{row.r}</td>
                  <td className="py-3 text-right">
                    <span className="text-[9px] font-mono font-bold text-emerald-400 bg-emerald-500/5 px-2 py-0.5 rounded border border-emerald-500/10">
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Discrepancy report failures list */}
      <div className="glass-card rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.03]">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">Discrepancy Report (Failed Runs)</h3>
          </div>
          <span className="text-[10px] text-zinc-400 font-mono">2 failures to trace</span>
        </div>

        <div className="space-y-4">
          {failures.map((f, idx) => (
            <div key={idx} className="p-4 bg-zinc-950 rounded-xl border border-white/[0.03] space-y-3 text-left">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.02] pb-2">
                <span className="text-xs font-semibold text-zinc-200 truncate max-w-md">Query: &ldquo;{f.q}&rdquo;</span>
                <div className="flex gap-2 text-[10px] font-mono shrink-0">
                  <span className="px-2 py-0.5 bg-red-500/5 border border-red-500/10 text-red-400 rounded">
                    Score: {f.faithfulness}
                  </span>
                  <span className="px-2 py-0.5 bg-zinc-900 border border-white/[0.06] text-zinc-400 rounded">
                    Source: {f.file}
                  </span>
                </div>
              </div>

              <div className="flex gap-2.5 items-start text-xs text-zinc-400 leading-relaxed font-normal">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <p>
                  <span className="font-semibold text-zinc-300">Failure reason: </span>
                  {f.reason}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
