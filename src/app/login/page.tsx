"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { 
  ShieldCheck, Mail, Lock, RefreshCw, AlertCircle, ArrowLeft
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  
  // Auth view: "signin" | "signup"
  const [view, setView] = useState<"signin" | "signup">("signin");
  
  // Form fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Check if user is already logged in
  useEffect(() => {
    const checkUser = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        router.replace("/dashboard");
      }
    };
    checkUser();
  }, [router]);

  // Handle standard email/password Auth
  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;

    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      if (view === "signin") {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        router.push("/dashboard");
      } else {
        const { error, data } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: typeof window !== "undefined" ? window.location.origin + "/login" : undefined,
          }
        });
        if (error) throw error;
        
        if (data?.user && data.user.identities?.length === 0) {
          setSuccessMsg("This email is already registered. Please sign in instead.");
        } else {
          setSuccessMsg("Registration successful! Please check your email inbox to verify your account.");
        }
        setEmail("");
        setPassword("");
      }
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "An authentication error occurred.");
    } finally {
      setLoading(false);
    }
  };

  // Handle Google OAuth Sign In
  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: typeof window !== "undefined" ? window.location.origin + "/dashboard" : undefined,
        }
      });
      if (error) throw error;
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Failed to initialize Google sign in.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#030303] text-zinc-150 flex flex-col justify-between relative overflow-hidden font-sans selection:bg-[#45A29E]/30 selection:text-white">
      
      {/* Background ambient lighting */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-[#45A29E]/[0.02] blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-500/[0.01] blur-[120px] pointer-events-none" />

      {/* Header */}
      <header className="h-16 px-6 border-b border-white/[0.04] bg-[#030303]/60 backdrop-blur-md flex items-center justify-between z-10 shrink-0">
        <Link href="/" className="flex items-center gap-2 group">
          <span className="text-white font-semibold text-lg tracking-tight">Cited.AI</span>
        </Link>
        <Link href="/" className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-colors font-semibold">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Home
        </Link>
      </header>

      {/* Main card box */}
      <main className="flex-1 flex items-center justify-center p-6 relative z-10">
        <div className="w-full max-w-md bg-[#08080c] border border-white/[0.06] rounded-3xl p-8 shadow-[0_20px_50px_rgba(0,0,0,0.8),0_0_80px_rgba(69,162,158,0.01)] relative overflow-hidden">
          {/* Card ambient blur */}
          <div className="absolute top-0 right-0 w-24 h-24 bg-[#45A29E]/[0.01] rounded-bl-full pointer-events-none" />
          
          <div className="flex flex-col items-center mb-6">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.04] flex items-center justify-center text-[#45A29E] mb-4">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-serif text-white tracking-tight leading-snug">
              {view === "signin" ? "Welcome back" : "Create your account"}
            </h1>
            <p className="text-zinc-400 text-xs font-normal mt-1 text-center max-w-[280px]">
              {view === "signin" 
                ? "Enter your credentials to access your grounding sandbox." 
                : "Get started with grounded document-level Q&A instantly."}
            </p>
          </div>

          {/* Error and Success Alerts */}
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-red-500/[0.02] border border-red-500/20 text-xs text-red-400 flex items-start gap-2.5 mb-5 text-left font-sans leading-relaxed">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3.5 rounded-xl bg-emerald-500/[0.02] border border-emerald-500/20 text-xs text-emerald-400 flex items-start gap-2.5 mb-5 text-left font-sans leading-relaxed">
              <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Auth Tab Switcher */}
          <div className="grid grid-cols-2 gap-1 p-1 bg-zinc-950 rounded-xl border border-white/[0.03] mb-6">
            <button
              onClick={() => {
                setView("signin");
                setErrorMsg(null);
                setSuccessMsg(null);
              }}
              className={`py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                view === "signin" 
                  ? "bg-zinc-900 text-white border border-white/[0.04] shadow-inner" 
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => {
                setView("signup");
                setErrorMsg(null);
                setSuccessMsg(null);
              }}
              className={`py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                view === "signup" 
                  ? "bg-zinc-900 text-white border border-white/[0.04] shadow-inner" 
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* Google OAuth Option */}
          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-zinc-950 hover:bg-zinc-900 border border-white/[0.04] text-zinc-300 hover:text-white py-3 px-4 rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50 mb-4"
          >
            <svg className="w-4 h-4 mr-1 text-zinc-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 h-px bg-white/[0.02]" />
            <span className="text-[10px] font-mono text-zinc-550 uppercase tracking-widest">or</span>
            <div className="flex-1 h-px bg-white/[0.02]" />
          </div>

          {/* Email Password Form */}
          <form onSubmit={handleAuth} className="space-y-4">
            <div className="space-y-1.5 text-left">
              <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider ml-1">Email address</label>
              <div className="relative flex items-center">
                <Mail className="w-4 h-4 text-zinc-500 absolute left-3.5 pointer-events-none" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full bg-zinc-950 border border-white/[0.04] rounded-xl pl-10 pr-4 py-3 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-[#45A29E]/30 transition-all font-normal"
                />
              </div>
            </div>

            <div className="space-y-1.5 text-left">
              <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider ml-1">Password</label>
              <div className="relative flex items-center">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3.5 pointer-events-none" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-zinc-950 border border-white/[0.04] rounded-xl pl-10 pr-4 py-3 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-[#45A29E]/30 transition-all font-normal"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#45A29E] hover:bg-[#398a87] text-black py-3 px-4 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 mt-6 shadow-[0_4px_12px_rgba(69,162,158,0.15)]"
            >
              {loading ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <span>{view === "signin" ? "Sign In" : "Sign Up"}</span>
              )}
            </button>
          </form>

        </div>
      </main>

      {/* Footer */}
      <footer className="h-12 border-t border-white/[0.02] flex items-center justify-center shrink-0">
        <span className="text-[10px] text-zinc-400 font-normal">
          © 2026 Cited.AI • Secure Authentication Sandbox
        </span>
      </footer>

    </div>
  );
}
