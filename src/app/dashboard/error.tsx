"use client";

import React, { useEffect } from "react";
import { AlertOctagon, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function DashboardErrorBoundary({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log the error to console or telemetry providers
    console.error("Dashboard error caught by React Boundary:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-10rem)] text-center p-6 text-left">
      <div className="glass-card max-w-md p-8 rounded-2xl border border-red-500/20 bg-red-500/[0.01] flex flex-col items-center gap-5">
        <div className="w-12 h-12 rounded-xl bg-zinc-950 border border-red-500/20 flex items-center justify-center text-red-400">
          <AlertOctagon className="w-6 h-6" />
        </div>
        
        <div className="space-y-2">
          <h2 className="text-base font-bold text-white">Application Error</h2>
          <p className="text-zinc-400 text-xs font-normal leading-relaxed">
            An unexpected error occurred in this workspace segment. We have logged the issue and isolated the rendering thread.
          </p>
          {error.message && (
            <div className="p-3 bg-zinc-950 rounded-lg border border-white/[0.03] text-[10px] font-mono text-red-400 break-all select-all">
              {error.message}
            </div>
          )}
        </div>

        <div className="flex gap-3 w-full justify-center">
          <button 
            onClick={reset}
            className="flex items-center gap-1.5 bg-[#45A29E] hover:bg-[#398a87] text-black px-5 py-2.5 rounded-full text-xs font-semibold transition-all hover:scale-[1.02] shadow-[0_4px_12px_rgba(69,162,158,0.15)] cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reload Segment
          </button>
          <Link 
            href="/dashboard"
            className="flex items-center gap-1.5 bg-zinc-900 border border-white/[0.06] hover:border-white/[0.1] text-zinc-300 hover:text-white px-5 py-2.5 rounded-full text-xs font-semibold transition-all"
          >
            <Home className="w-3.5 h-3.5" />
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
