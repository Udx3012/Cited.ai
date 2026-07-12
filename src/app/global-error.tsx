"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-[#0b0c10] text-white font-sans flex items-center justify-center min-h-screen p-6">
        <div className="max-w-md p-8 rounded-2xl bg-zinc-950 border border-white/[0.06] flex flex-col items-center gap-5 text-center">
          <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-white/[0.04] flex items-center justify-center text-amber-500">
            <AlertTriangle className="w-6 h-6" />
          </div>
          
          <div className="space-y-2">
            <h1 className="text-lg font-bold text-white">System Error</h1>
            <p className="text-zinc-400 text-xs font-normal leading-relaxed">
              A fatal rendering exception occurred at the root level of the application.
            </p>
            {error.message && (
              <div className="p-3 bg-zinc-900 rounded-lg border border-white/[0.03] text-[10px] font-mono text-amber-400 break-all select-all">
                {error.message}
              </div>
            )}
          </div>

          <button 
            onClick={reset}
            className="flex items-center gap-1.5 bg-[#45A29E] hover:bg-[#398a87] text-black px-6 py-2.5 rounded-full text-xs font-bold transition-all cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Restart Application
          </button>
        </div>
      </body>
    </html>
  );
}
