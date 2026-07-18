"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import { supabase } from "@/lib/supabase";
import { 
  Layers, FileCode, MessageSquare, Compass, Shield, Settings,
  Menu, X, Bell, Search, User, LogOut, ChevronLeft, ChevronRight,
  Sparkles, FileText, CheckCircle2, AlertCircle, HelpCircle, ArrowRight, RefreshCw
} from "lucide-react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  
  // Auth state protection
  const [loadingUser, setLoadingUser] = useState(true);
  const [user, setUser] = useState<any>(null);

  // Sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  
  // Command palette state
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const checkUser = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.replace("/login");
      } else {
        setUser(session.user);
        setLoadingUser(false);
      }
    };
    checkUser();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.replace("/login");
      } else {
        setUser(session.user);
        setLoadingUser(false);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [router]);

  if (loadingUser) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#030303]">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-[#45A29E] animate-spin" />
          <span className="text-xs text-zinc-400 font-mono uppercase tracking-wider font-semibold">Verifying session...</span>
        </div>
      </div>
    );
  }
  
  // Keyboard shortcut listener for command palette (Ctrl+K or Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Navigation items
  const navItems = [
    { label: "Overview", href: "/dashboard", icon: Layers },
    { label: "Documents", href: "/dashboard/documents", icon: FileCode },
    { label: "Chat Sandbox", href: "/dashboard/chat", icon: MessageSquare },
    { label: "AI Inspector", href: "/dashboard/inspector", icon: Compass },
    { label: "Evaluation", href: "/dashboard/evaluation", icon: Shield },
    { label: "Settings", href: "/dashboard/settings", icon: Settings }
  ];

  // Mock Notifications
  const notifications = [
    { id: 1, title: "Ingestion Successful", desc: "Q4-Report.pdf has been parsed and indexed.", time: "2 min ago", type: "success" },
    { id: 2, title: "Latency Spike P95", desc: "Response latency exceeded 1200ms on standard model.", time: "10 min ago", type: "warning" },
    { id: 3, title: "Evaluation Complete", desc: "Golden dataset run (n=50) completed with 92.4% accuracy.", time: "1 hr ago", type: "info" }
  ];

  // Mock Command Palette items
  const cmdItems = [
    { title: "Dashboard Overview", category: "Navigation", href: "/dashboard" },
    { title: "Upload New Documents", category: "Navigation", href: "/dashboard/documents" },
    { title: "Start AI Chat Session", category: "Navigation", href: "/dashboard/chat" },
    { title: "RAG Stage Inspector", category: "Navigation", href: "/dashboard/inspector" },
    { title: "System Configurations", category: "Navigation", href: "/dashboard/settings" },
    { title: "Q4-Report.pdf", category: "Documents", href: "/dashboard/documents" },
    { title: "GDPR-Handbook.pdf", category: "Documents", href: "/dashboard/documents" }
  ];

  const filteredCmdItems = cmdItems.filter(item => 
    item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Auto-generate breadcrumb details
  const getBreadcrumbs = () => {
    const segments = pathname.split("/").filter(item => item !== "");
    return segments.map((seg, idx) => {
      const href = "/" + segments.slice(0, idx + 1).join("/");
      const label = seg.charAt(0).toUpperCase() + seg.slice(1);
      return { label: label === "Dashboard" ? "Workspace" : label, href };
    });
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <div className="flex h-screen bg-[#030303] text-zinc-100 overflow-hidden font-sans">
      
      {/* Background ambient lighting */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-[#45A29E]/[0.01] rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-500/[0.005] rounded-full blur-[100px] pointer-events-none" />

      {/* Desktop Sidebar */}
      <aside 
        className={`hidden md:flex flex-col shrink-0 bg-[#060608] border-r border-white/[0.04] transition-all duration-300 relative ${
          sidebarCollapsed ? "w-16" : "w-64"
        }`}
      >
        {/* Sidebar Header */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-white/[0.04]">
          <Link href="/" className="flex items-center gap-2 group overflow-hidden">
            {!sidebarCollapsed && (
              <motion.span 
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-white font-semibold text-base tracking-tight truncate"
              >
                Cited.AI
              </motion.span>
            )}
          </Link>
        </div>

        {/* Sidebar Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link 
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive 
                    ? "bg-[#45A29E]/10 border border-[#45A29E]/20 text-[#45A29E] shadow-[0_0_15px_rgba(69,162,158,0.03)]" 
                    : "text-zinc-400 hover:text-zinc-300 hover:bg-zinc-900/40"
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-[#45A29E]" : "text-zinc-400 group-hover:text-zinc-300"}`} />
                {!sidebarCollapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Sidebar Collapse Toggle */}
        <button 
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="absolute bottom-8 -right-3.5 w-7 h-7 rounded-full bg-[#060608] hover:bg-zinc-900 border border-white/[0.08] hover:border-[#45A29E]/40 flex items-center justify-center text-zinc-400 hover:text-zinc-300 transition-all shadow-[0_2px_8px_rgba(0,0,0,0.8)] cursor-pointer z-40 hover:scale-110 active:scale-95"
        >
          {sidebarCollapsed ? <ChevronRight className="w-4 h-4 text-[#45A29E]" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </aside>

      {/* Mobile Sidebar Overlay */}
      <AnimatePresence>
        {mobileSidebarOpen && (
          <>
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileSidebarOpen(false)}
              className="fixed inset-0 bg-black z-40 md:hidden"
            />
            <motion.aside 
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", bounce: 0, duration: 0.4 }}
              className="fixed inset-y-0 left-0 w-64 bg-[#060608] border-r border-white/[0.04] p-4 flex flex-col z-50 md:hidden"
            >
              <div className="flex items-center justify-between pb-6 border-b border-white/[0.04] mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-white font-semibold text-base">Cited.AI</span>
                </div>
                <button onClick={() => setMobileSidebarOpen(false)} className="text-zinc-400 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <nav className="flex-1 space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
                  return (
                    <Link 
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileSidebarOpen(false)}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                        isActive 
                          ? "bg-[#45A29E]/10 border border-[#45A29E]/20 text-[#45A29E]" 
                          : "text-zinc-400 hover:text-zinc-300 hover:bg-zinc-900/40"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main Panel */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        
        {/* Sticky Top Header Navigation */}
        <header className="h-16 px-6 bg-[#030303]/60 backdrop-blur-md border-b border-white/[0.04] flex items-center justify-between z-30 shrink-0">
          
          {/* Breadcrumbs and Menu Toggle */}
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setMobileSidebarOpen(true)}
              className="text-zinc-400 hover:text-white md:hidden transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Breadcrumb Support */}
            <div className="hidden sm:flex items-center gap-2 text-xs font-medium text-zinc-400">
              <Link href="/" className="hover:text-zinc-300 transition-colors">Cited.AI</Link>
              {breadcrumbs.map((crumb, idx) => (
                <React.Fragment key={crumb.href}>
                  <span>/</span>
                  <Link 
                    href={crumb.href} 
                    className={`transition-colors ${idx === breadcrumbs.length - 1 ? "text-zinc-300 font-semibold cursor-default" : "hover:text-zinc-300"}`}
                    onClick={(e) => idx === breadcrumbs.length - 1 && e.preventDefault()}
                  >
                    {crumb.label}
                  </Link>
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Action Items */}
          <div className="flex items-center gap-4">
            
            {/* Search command shortcut button */}
            <button 
              onClick={() => setCommandPaletteOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-950 hover:bg-zinc-900 border border-white/[0.04] hover:border-white/[0.08] text-xs text-zinc-400 hover:text-zinc-400 transition-all font-normal"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Search...</span>
              <kbd className="hidden lg:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-white/[0.06] bg-zinc-900 font-mono text-[9px] text-zinc-400 uppercase">
                <span>ctrl</span>
                <span>+</span>
                <span>k</span>
              </kbd>
            </button>

            {/* Notifications Popover */}
            <Popover.Root>
              <Popover.Trigger asChild>
                <button className="relative p-2 rounded-full bg-zinc-950 border border-white/[0.04] hover:bg-zinc-900 transition-colors text-zinc-400 hover:text-white">
                  <Bell className="w-4 h-4" />
                  <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-[#45A29E] animate-pulse" />
                </button>
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content 
                  className="w-80 rounded-xl bg-zinc-950 border border-white/[0.06] shadow-[0_10px_30px_rgba(0,0,0,0.8)] p-4 text-zinc-300 z-50 focus:outline-none animate-in fade-in zoom-in-95 duration-150"
                  sideOffset={8}
                  align="end"
                >
                  <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/[0.03]">
                    <span className="text-xs font-semibold text-white">Notifications</span>
                    <button className="text-[10px] text-[#45A29E] hover:underline">Mark all read</button>
                  </div>
                  <div className="space-y-3">
                    {notifications.map((item) => (
                      <div key={item.id} className="text-left pb-3 border-b border-white/[0.03] last:border-0 last:pb-0">
                        <div className="flex justify-between font-medium text-zinc-200 text-xs">
                          <span>{item.title}</span>
                          <span className="text-xs text-zinc-400 font-normal">{item.time}</span>
                        </div>
                        <p className="text-zinc-400 mt-1.5 text-xs leading-relaxed">{item.desc}</p>
                      </div>
                    ))}
                  </div>
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>

            {/* User Dropdown Profile Menu */}
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="w-8 h-8 rounded-full bg-zinc-900 border border-white/[0.08] hover:border-[#45A29E]/30 flex items-center justify-center overflow-hidden transition-colors">
                  <div className="w-full h-full bg-gradient-to-tr from-[#45A29E]/30 to-[#45A29E]/10 flex items-center justify-center">
                    <User className="w-4 h-4 text-[#45A29E]" />
                  </div>
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content 
                  className="min-w-[180px] bg-zinc-950 border border-white/[0.06] rounded-xl p-1.5 shadow-[0_10px_30px_rgba(0,0,0,0.8)] z-50 animate-in fade-in zoom-in-95 duration-150"
                  sideOffset={8}
                  align="end"
                >
                  <DropdownMenu.Item className="flex items-center gap-2 px-2.5 py-2 text-xs text-zinc-300 font-medium hover:bg-zinc-900/60 rounded-lg cursor-pointer focus:outline-none focus:bg-zinc-900/60 transition-colors">
                    <User className="w-3.5 h-3.5 text-zinc-400" />
                    <span>My Profile</span>
                  </DropdownMenu.Item>
                  <DropdownMenu.Item className="flex items-center gap-2 px-2.5 py-2 text-xs text-zinc-300 font-medium hover:bg-zinc-900/60 rounded-lg cursor-pointer focus:outline-none focus:bg-zinc-900/60 transition-colors">
                    <Settings className="w-3.5 h-3.5 text-zinc-400" />
                    <span>Profile Settings</span>
                  </DropdownMenu.Item>
                  <DropdownMenu.Separator className="h-px bg-white/[0.03] my-1" />
                  <DropdownMenu.Item 
                    onClick={async () => {
                      await supabase.auth.signOut();
                      router.push("/login");
                    }}
                    className="flex items-center gap-2 px-2.5 py-2 text-xs text-red-400 font-medium hover:bg-red-500/10 rounded-lg cursor-pointer focus:outline-none focus:bg-red-500/10 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Log Out</span>
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>

          </div>
        </header>

        {/* Dashboard Pages Content viewport */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-6 relative">
          {children}
        </main>
      </div>

      {/* Command Palette (Dialog Overlay) */}
      <Dialog.Root open={commandPaletteOpen} onOpenChange={setCommandPaletteOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200" />
          <Dialog.Content className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-xl bg-zinc-950 border border-white/[0.08] rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.8),0_0_80px_rgba(69,162,158,0.03)] z-50 focus:outline-none overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Input search */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.04]">
              <Search className="w-4 h-4 text-zinc-400 shrink-0" />
              <input 
                type="text" 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Type a command or file name to search..." 
                className="bg-transparent text-sm w-full text-zinc-200 placeholder-zinc-500 focus:outline-none"
                autoFocus
              />
              <button 
                onClick={() => setCommandPaletteOpen(false)}
                className="text-[10px] text-zinc-400 border border-white/[0.08] px-1.5 py-0.5 rounded bg-zinc-900 hover:text-white"
              >
                ESC
              </button>
            </div>

            {/* Suggestions list */}
            <div className="max-h-[300px] overflow-y-auto p-2">
              {filteredCmdItems.length > 0 ? (
                <div className="space-y-1">
                  {/* Categorized rendering */}
                  {Array.from(new Set(filteredCmdItems.map(i => i.category))).map(cat => (
                    <div key={cat} className="space-y-1">
                      <span className="text-[10px] font-bold text-zinc-400 tracking-widest block px-3 pt-2 uppercase">
                        {cat}
                      </span>
                      {filteredCmdItems.filter(i => i.category === cat).map((item, idx) => (
                        <div
                          key={idx}
                          onClick={() => {
                            router.push(item.href);
                            setCommandPaletteOpen(false);
                          }}
                          className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-zinc-900/60 cursor-pointer transition-colors group"
                        >
                          <div className="flex items-center gap-3">
                            {item.category === "Navigation" ? (
                              <ArrowRight className="w-3.5 h-3.5 text-zinc-400 group-hover:text-[#45A29E]" />
                            ) : (
                              <FileText className="w-3.5 h-3.5 text-zinc-400 group-hover:text-[#45A29E]" />
                            )}
                            <span className="text-xs text-zinc-300 font-medium group-hover:text-white">{item.title}</span>
                          </div>
                          <span className="text-[10px] text-zinc-400 group-hover:text-zinc-400">Go</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 px-4 text-center text-xs text-zinc-400 flex flex-col items-center justify-center gap-2">
                  <AlertCircle className="w-6 h-6 text-zinc-400" />
                  <span>No matches found for &quot;{searchQuery}&quot;</span>
                </div>
              )}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

    </div>
  );
}
