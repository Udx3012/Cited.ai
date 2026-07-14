"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import * as Dialog from "@radix-ui/react-dialog";
import { 
  Upload, FileText, CheckCircle2, AlertTriangle, Trash2, 
  RefreshCw, Grid, List, Search, ArrowUpDown, Filter,
  X, Database, HelpCircle, File, ChevronDown, Check, AlertCircle
} from "lucide-react";

interface DocumentFile {
  id: string;
  name: string;
  size: string;
  pages: number;
  status: "Indexed" | "Processing" | "Failed";
  progress?: number;
  chunks: number;
  date: string;
}

interface QueueItem {
  id: string;
  name: string;
  size: string;
  progress: number;
  status: "uploading" | "success" | "error";
  errorMsg?: string;
}

export default function DocumentsLibrary() {
  // Skeletons loader state
  const [isLoading, setIsLoading] = useState(true);
  
  // Library states
  const [documents, setDocuments] = useState<DocumentFile[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [layoutMode, setLayoutMode] = useState<"grid" | "list">("grid");
  const [filterStatus, setFilterStatus] = useState<"all" | "Indexed" | "Processing" | "Failed">("all");
  const [sortBy, setSortBy] = useState<"date" | "name" | "chunks" | "pages">("date");
  
  // Upload Queue state
  const [uploadQueue, setUploadQueue] = useState<QueueItem[]>([]);
  const [dragActive, setDragActive] = useState(false);

  // Delete Confirmation Dialog states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedDeleteDoc, setSelectedDeleteDoc] = useState<DocumentFile | null>(null);

  // Retrieve current active config parameters
  const getSettings = () => {
    if (typeof window === "undefined") {
      return { 
        backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1", 
        apiKey: "my_super_secret_cited_ai_key_2026" 
      };
    }
    const url = localStorage.getItem("cited_backend_url") || process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1";
    const key = localStorage.getItem("cited_api_key") || "my_super_secret_cited_ai_key_2026";
    return { backendUrl: url, apiKey: key };
  };

  // Sync documents from localStorage
  const loadDocuments = () => {
    const saved = localStorage.getItem("cited_documents");
    if (saved) {
      setDocuments(JSON.parse(saved));
    } else {
      const defaultDocs: DocumentFile[] = [
        { id: "1", name: "Q4-Report.pdf", size: "124 KB", pages: 12, status: "Indexed", chunks: 145, date: "2026-07-10 14:32" },
        { id: "2", name: "GDPR-Handbook.pdf", size: "842 KB", pages: 48, status: "Indexed", chunks: 212, date: "2026-07-08 09:15" },
        { id: "3", name: "AI-Act-Brief.pdf", size: "98 KB", pages: 6, status: "Indexed", chunks: 55, date: "2026-07-11 11:22" }
      ];
      localStorage.setItem("cited_documents", JSON.stringify(defaultDocs));
      setDocuments(defaultDocs);
    }
  };

  useEffect(() => {
    loadDocuments();
    
    // Listen for custom cross-component uploads event
    window.addEventListener("cited_docs_update", loadDocuments);
    
    // Simulate initial loading skeletons
    const timer = setTimeout(() => setIsLoading(false), 600);
    
    return () => {
      window.removeEventListener("cited_docs_update", loadDocuments);
      clearTimeout(timer);
    };
  }, []);

  // Launch a live upload task targeting the FastAPI backend
  const startLiveUpload = async (queueId: string, file: File, fileSize: string) => {
    const { backendUrl, apiKey } = getSettings();
    const formData = new FormData();
    formData.append("file", file);

    try {
      // 1. Submit POST request to upload endpoint
      const res = await fetch(`${backendUrl}/ingest/upload`, {
        method: "POST",
        headers: {
          "X-API-Key": apiKey
        },
        body: formData
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error?.message || errorData.detail || `Upload failed (HTTP ${res.status})`);
      }

      const uploadData = await res.json();
      const jobId = uploadData.job_id;
      const docId = uploadData.document_id;

      // 2. Poll job status endpoint
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${backendUrl}/ingest/status/${jobId}`, {
            headers: {
              "X-API-Key": apiKey
            }
          });

          if (!statusRes.ok) {
            throw new Error(`Failed to check progress (HTTP ${statusRes.status})`);
          }

          const statusData = await statusRes.json();

          if (statusData.status === "completed") {
            clearInterval(pollInterval);

            // Update queue item to success
            setUploadQueue(prev => 
              prev.map(item => item.id === queueId ? { ...item, progress: 100, status: "success" } : item)
            );

            // Append document record to local store
            const saved = localStorage.getItem("cited_documents");
            const docs = saved ? JSON.parse(saved) : [];
            const newDoc: DocumentFile = {
              id: docId,
              name: file.name,
              size: fileSize,
              pages: statusData.pages || 1,
              status: "Indexed",
              chunks: statusData.chunks || 0,
              date: new Date().toISOString().slice(0, 16).replace("T", " ")
            };

            const updatedDocs = [newDoc, ...docs];
            localStorage.setItem("cited_documents", JSON.stringify(updatedDocs));
            
            // Notify other pages
            window.dispatchEvent(new Event("cited_docs_update"));

            setTimeout(() => {
              setUploadQueue(prev => prev.filter(item => item.id !== queueId));
            }, 1500);

          } else if (statusData.status === "failed") {
            clearInterval(pollInterval);
            setUploadQueue(prev => 
              prev.map(item => item.id === queueId ? { 
                ...item, 
                status: "error", 
                errorMsg: statusData.error_message || "Ingestion parsing error." 
              } : item)
            );
          } else {
            // Update progress percentage
            setUploadQueue(prev => 
              prev.map(item => item.id === queueId ? { ...item, progress: statusData.progress || 30 } : item)
            );
          }

        } catch (pollErr: any) {
          clearInterval(pollInterval);
          setUploadQueue(prev => 
            prev.map(item => item.id === queueId ? { ...item, status: "error", errorMsg: pollErr.message } : item)
          );
        }
      }, 1000);

    } catch (err: any) {
      setUploadQueue(prev => 
        prev.map(item => item.id === queueId ? { 
          ...item, 
          status: "error", 
          errorMsg: err.message || "Connection refused." 
        } : item)
      );
    }
  };

  // Process incoming files
  const processUploadedFiles = (files: FileList) => {
    Array.from(files).forEach(file => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("The ingestion pipeline only supports PDF files.");
        return;
      }

      const sizeStr = file.size > 1024 * 1024 
        ? (file.size / (1024 * 1024)).toFixed(1) + " MB" 
        : (file.size / 1024).toFixed(0) + " KB";
      
      const newId = String(Date.now() + Math.random());
      const newQueueItem: QueueItem = {
        id: newId,
        name: file.name,
        size: sizeStr,
        progress: 0,
        status: "uploading"
      };

      setUploadQueue(prev => [...prev, newQueueItem]);
      startLiveUpload(newId, file, sizeStr);
    });
  };

  // File Select Browse click
  const handleFileBrowse = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processUploadedFiles(e.target.files);
    }
  };

  // Drag handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processUploadedFiles(e.dataTransfer.files);
    }
  };

  // Retry failed upload handler
  const handleRetryUpload = (id: string, name: string, size: string) => {
    // Requires original file reference, so we tell the user to re-browse
    alert("Please re-select or drag the file again to retry uploading.");
    setUploadQueue(prev => prev.filter(item => item.id !== id));
  };

  // Remove item from queue manually
  const handleRemoveFromQueue = (id: string) => {
    setUploadQueue(prev => prev.filter(item => item.id !== id));
  };

  // Re-ingest index
  const handleReingest = async (id: string) => {
    const { backendUrl, apiKey } = getSettings();
    
    setDocuments(prev => 
      prev.map(doc => doc.id === id ? { ...doc, status: "Processing", progress: 10 } : doc)
    );

    try {
      const res = await fetch(`${backendUrl}/ingest/reingest/${id}`, {
        method: "POST",
        headers: {
          "X-API-Key": apiKey
        }
      });

      if (!res.ok) {
        throw new Error(`Re-ingest failed (HTTP ${res.status})`);
      }

      const statusData = await res.json();
      
      setDocuments(prev => 
        prev.map(doc => doc.id === id ? { 
          ...doc, 
          status: "Indexed", 
          progress: undefined,
          chunks: statusData.chunks || doc.chunks,
          pages: statusData.pages || doc.pages
        } : doc)
      );

      // Save changes back to localStorage
      const saved = localStorage.getItem("cited_documents");
      if (saved) {
        const parsed = JSON.parse(saved);
        const updated = parsed.map((d: DocumentFile) => {
          if (d.id === id) {
            return {
              ...d,
              status: "Indexed" as const,
              chunks: statusData.chunks || d.chunks,
              pages: statusData.pages || d.pages
            };
          }
          return d;
        });
        localStorage.setItem("cited_documents", JSON.stringify(updated));
      }
      
      window.dispatchEvent(new Event("cited_docs_update"));
      alert("Document re-indexing triggered successfully.");

    } catch (err: any) {
      alert(err.message || "Failed to re-ingest document.");
      setDocuments(prev => 
        prev.map(doc => doc.id === id ? { ...doc, status: "Failed", progress: undefined } : doc)
      );
    }
  };

  // prompt delete
  const promptDelete = (doc: DocumentFile) => {
    setSelectedDeleteDoc(doc);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (selectedDeleteDoc) {
      const { backendUrl, apiKey } = getSettings();

      try {
        const res = await fetch(`${backendUrl}/ingest/document/${selectedDeleteDoc.id}`, {
          method: "DELETE",
          headers: {
            "X-API-Key": apiKey
          }
        });

        if (!res.ok) {
          throw new Error(`Deletion failed (HTTP ${res.status})`);
        }

        // On successful backend deletion, purge from local library
        const updated = documents.filter(d => d.id !== selectedDeleteDoc.id);
        setDocuments(updated);
        localStorage.setItem("cited_documents", JSON.stringify(updated));
        window.dispatchEvent(new Event("cited_docs_update"));
      } catch (err: any) {
        alert(err.message || "Failed to delete document from database.");
      } finally {
        setDeleteDialogOpen(false);
        setSelectedDeleteDoc(null);
      }
    }
  };

  // Filters & Sorters calculation
  const filteredDocs = documents
    .filter(doc => {
      const matchSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchFilter = filterStatus === "all" || doc.status === filterStatus;
      return matchSearch && matchFilter;
    })
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "chunks") return b.chunks - a.chunks;
      if (sortBy === "pages") return b.pages - a.pages;
      return new Date(b.date).getTime() - new Date(a.date).getTime();
    });

  return (
    <div className="space-y-6 text-left">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-serif text-white tracking-tight">Documents Library</h1>
          <p className="text-zinc-400 text-xs font-normal mt-1">
            Store and manage corpus reference indexes. Query citations map back directly to these records.
          </p>
        </div>

        {/* Upload Trigger button */}
        <div>
          <input 
            type="file" 
            id="lib-file-upload" 
            multiple
            accept="application/pdf"
            onChange={handleFileBrowse}
            className="hidden" 
          />
          <label 
            htmlFor="lib-file-upload" 
            className="flex items-center gap-2 bg-[#45A29E] hover:bg-[#398a87] text-black px-4 py-2.5 rounded-full text-xs font-semibold transition-all hover:scale-[1.02] shadow-[0_4px_15px_rgba(69,162,158,0.12)] cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5" />
            Upload Document
          </label>
        </div>
      </div>

      {/* Drag & Drop Zone */}
      <div 
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`glass-card p-8 rounded-2xl border-2 border-dashed text-center flex flex-col items-center justify-center relative overflow-hidden transition-all ${
          dragActive ? "border-[#45A29E] bg-[#45A29E]/[0.02]" : "border-white/[0.04] hover:border-white/[0.08]"
        }`}
      >
        <div className="w-12 h-12 rounded-xl bg-zinc-950 border border-white/[0.04] flex items-center justify-center mb-4 text-zinc-400">
          <Upload className="w-6 h-6 text-[#45A29E]" />
        </div>

        <h3 className="text-sm font-semibold text-white mb-1">
          Drag & drop your documents here
        </h3>
        <p className="text-zinc-400 text-xs font-normal max-w-sm mb-4 leading-relaxed">
          Supports PDF documents only. Max file size: 50MB.
        </p>

        <label 
          htmlFor="lib-file-upload" 
          className="px-5 py-2 rounded-full bg-zinc-900 border border-white/[0.06] hover:border-[#45A29E]/30 text-xs font-semibold text-zinc-300 hover:text-white cursor-pointer transition-all hover:scale-[1.02]"
        >
          Browse Files
        </label>
      </div>

      {/* Upload Queue Section */}
      <AnimatePresence>
        {uploadQueue.length > 0 && (
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 15 }}
            className="glass-card p-5 rounded-2xl space-y-4"
          >
            <div className="flex items-center justify-between border-b border-white/[0.03] pb-3">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-[#45A29E] animate-spin" />
                <h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider">Ingestion Queue</h3>
              </div>
              <span className="text-xs text-zinc-400 font-mono font-bold bg-zinc-900 px-2 py-0.5 rounded border border-white/[0.04]">
                {uploadQueue.filter(i => i.status === "uploading").length} active
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[300px] overflow-y-auto pr-1">
              {uploadQueue.map((item) => (
                <motion.div 
                  key={item.id}
                  layout
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  className={`p-3.5 rounded-xl border flex flex-col justify-between h-28 relative overflow-hidden transition-all ${
                    item.status === "error" 
                      ? "bg-red-500/[0.02] border-red-500/20" 
                      : item.status === "success"
                        ? "bg-emerald-500/[0.01] border-emerald-500/20"
                        : "bg-zinc-950/80 border-white/[0.02]"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2.5 truncate">
                      <FileText className="w-4 h-4 text-zinc-400 shrink-0" />
                      <div className="truncate text-left">
                        <span className="text-xs font-semibold text-zinc-200 block truncate max-w-[180px]" title={item.name}>
                          {item.name}
                        </span>
                        <span className="text-xs text-zinc-400 font-mono">{item.size}</span>
                      </div>
                    </div>

                    {/* Status triggers */}
                    {item.status === "success" && (
                      <motion.div 
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="w-5 h-5 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0"
                      >
                        <Check className="w-3 h-3" />
                      </motion.div>
                    )}

                    {item.status === "error" && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button 
                          onClick={() => handleRetryUpload(item.id, item.name, item.size)}
                          className="px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-800 border border-white/[0.06] text-xs font-bold text-zinc-300 transition-colors"
                        >
                          Retry
                        </button>
                        <button 
                          onClick={() => handleRemoveFromQueue(item.id)}
                          className="text-zinc-500 hover:text-white"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}

                    {item.status === "uploading" && (
                      <span className="text-xs font-mono font-bold text-[#45A29E] bg-[#45A29E]/5 px-2 py-0.5 rounded border border-[#45A29E]/10 shrink-0">
                        {item.progress}%
                      </span>
                    )}
                  </div>

                  {/* Queue progress details */}
                  <div className="space-y-1">
                    {item.status === "error" ? (
                      <div className="flex items-center gap-1 text-xs text-red-400 font-medium">
                        <AlertCircle className="w-3.5 h-3.5" />
                        <span>{item.errorMsg}</span>
                      </div>
                    ) : (
                      <>
                        <div className="w-full h-1 bg-zinc-900 rounded-full overflow-hidden">
                          <div 
                            className={`h-full transition-all duration-300 ${
                              item.status === "success" ? "bg-emerald-500" : "bg-[#45A29E]"
                            }`} 
                            style={{ width: `${item.progress}%` }} 
                          />
                        </div>
                        <span className="text-xs text-zinc-400 font-medium block text-left">
                          {item.status === "success" ? "Ready" : "Indexing document vectors..."}
                        </span>
                      </>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search, Layout toggles, Filters Controls Bar */}
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between bg-zinc-950 p-4 rounded-2xl border border-white/[0.04] shrink-0">
        
        {/* Search & Sort Dropdown */}
        <div className="flex flex-1 flex-col sm:flex-row gap-3 w-full">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-3" />
            <input 
              type="text" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search document name..."
              className="bg-zinc-900 text-xs pl-9 pr-4 py-2.5 rounded-xl border border-white/[0.04] focus:border-[#45A29E]/30 focus:outline-none w-full text-zinc-200"
            />
          </div>

          <div className="relative min-w-[160px]">
            <ArrowUpDown className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-3" />
            <select 
              value={sortBy}
              onChange={(e: any) => setSortBy(e.target.value)}
              className="bg-zinc-900 text-xs pl-9 pr-8 py-2.5 rounded-xl border border-white/[0.04] focus:outline-none cursor-pointer w-full text-zinc-350 appearance-none font-semibold"
            >
              <option value="date">Upload Date</option>
              <option value="name">File Name</option>
              <option value="chunks">Chunks Count</option>
              <option value="pages">Pages Count</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400 absolute right-3 top-3 pointer-events-none" />
          </div>
        </div>

        {/* Filter chips & Grid/List toggles */}
        <div className="flex items-center justify-between md:justify-end gap-4 w-full md:w-auto border-t md:border-t-0 border-white/[0.04] pt-3 md:pt-0">
          
          {/* Layout Toggles */}
          <div className="flex bg-zinc-900 p-0.5 rounded-lg border border-white/[0.04] shrink-0">
            <button 
              onClick={() => setLayoutMode("grid")}
              className={`p-1.5 rounded-md transition-all ${layoutMode === "grid" ? "bg-zinc-800 text-white" : "text-zinc-455 hover:text-zinc-300"}`}
              title="Grid View"
            >
              <Grid className="w-4 h-4" />
            </button>
            <button 
              onClick={() => setLayoutMode("list")}
              className={`p-1.5 rounded-md transition-all ${layoutMode === "list" ? "bg-zinc-800 text-white" : "text-zinc-455 hover:text-zinc-300"}`}
              title="List View"
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          {/* Filter Status Select */}
          <div className="flex items-center gap-1.5">
            {["all", "Indexed", "Processing", "Failed"].map((status) => (
              <button
                key={status}
                onClick={() => setFilterStatus(status as any)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider transition-all border ${
                  filterStatus === status 
                    ? "bg-[#45A29E]/10 border-[#45A29E]/20 text-[#45A29E]" 
                    : "bg-zinc-900 border-white/[0.04] text-zinc-400 hover:text-zinc-300"
                }`}
              >
                {status === "all" ? "All" : status === "Indexed" ? "Ready" : status}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Skeletons Loader vs Loaded Content */}
      <AnimatePresence mode="wait">
        {isLoading ? (
          /* Loading Skeletons */
          <motion.div 
            key="skeletons"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={layoutMode === "grid" ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" : "space-y-3"}
          >
            {[1, 2, 3].map((s) => (
              <div 
                key={s} 
                className="bg-zinc-950/50 border border-white/[0.03] rounded-2xl p-5 h-44 animate-pulse flex flex-col justify-between"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.04]" />
                    <div className="space-y-2">
                      <div className="w-32 h-3 bg-zinc-900 rounded" />
                      <div className="w-20 h-2 bg-zinc-900 rounded" />
                    </div>
                  </div>
                  <div className="w-16 h-5 bg-zinc-900 rounded" />
                </div>
                
                <div className="space-y-1.5">
                  <div className="w-full h-1 bg-zinc-900 rounded" />
                  <div className="flex justify-between">
                    <div className="w-12 h-2.5 bg-zinc-900 rounded" />
                    <div className="w-16 h-2.5 bg-zinc-900 rounded" />
                  </div>
                </div>
              </div>
            ))}
          </motion.div>
        ) : filteredDocs.length > 0 ? (
          layoutMode === "grid" ? (
            /* Document Card Grid view */
            <motion.div 
              key="grid"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
            >
              {filteredDocs.map((doc) => (
                <motion.div 
                  key={doc.id}
                  layout
                  className="glass-card p-5 rounded-2xl relative overflow-hidden flex flex-col justify-between group"
                >
                  <div className="absolute top-0 right-0 w-16 h-16 bg-[#45A29E]/[0.005] rounded-bl-full pointer-events-none" />
                  
                  {/* Card top */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-zinc-950 border border-white/[0.04] flex items-center justify-center text-zinc-400 group-hover:border-[#45A29E]/30 transition-colors">
                        <FileText className="w-5 h-5 text-[#45A29E]" />
                      </div>
                      <div className="truncate max-w-[140px]">
                        <h4 className="text-xs font-semibold text-zinc-200 truncate group-hover:text-white transition-colors" title={doc.name}>
                          {doc.name}
                        </h4>
                        <span className="text-xs text-zinc-400 font-mono">{doc.size}</span>
                      </div>
                    </div>

                    {/* Status Pill */}
                    {doc.status === "Processing" ? (
                      <span className="text-xs font-mono font-bold text-amber-400 bg-amber-500/5 px-2 py-0.5 rounded border border-amber-500/10 flex items-center gap-1">
                        <RefreshCw className="w-2.5 h-2.5 animate-spin" />
                        Indexing
                      </span>
                    ) : doc.status === "Failed" ? (
                      <span className="text-xs font-mono font-bold text-red-400 bg-red-500/5 px-2 py-0.5 rounded border border-red-500/10 flex items-center gap-0.5">
                        <AlertTriangle className="w-2.5 h-2.5" />
                        Failed
                      </span>
                    ) : (
                      <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/5 px-2 py-0.5 rounded border border-emerald-500/10 flex items-center gap-0.5">
                        <CheckCircle2 className="w-2.5 h-2.5" />
                        Ready
                      </span>
                    )}
                  </div>

                  {/* Chunks & Progress indicator */}
                  <div className="mt-6 pt-3 border-t border-white/[0.02]">
                    {doc.status === "Processing" ? (
                      <div className="space-y-1.5">
                        <div className="w-full h-1 bg-zinc-950 rounded-full overflow-hidden">
                          <div className="h-full bg-[#45A29E]" style={{ width: `${doc.progress ?? 40}%` }} />
                        </div>
                        <div className="flex justify-between text-xs text-zinc-400 font-mono">
                          <span>Ingesting chunks...</span>
                          <span>{doc.progress ?? 40}%</span>
                        </div>
                      </div>
                    ) : (
                      <div className="flex justify-between text-[10px] font-medium text-zinc-350 font-mono">
                        <span>{doc.pages} pages</span>
                        <span>{doc.chunks} chunks</span>
                      </div>
                    )}
                  </div>

                  {/* Footer options */}
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/[0.02]">
                    <span className="text-xs text-zinc-400 font-normal">{doc.date}</span>
                    
                    <div className="flex items-center gap-2">
                      <button 
                        onClick={() => handleReingest(doc.id)}
                        disabled={doc.status === "Processing"}
                        title="Re-ingest document"
                        className="p-1 rounded bg-zinc-950 hover:bg-zinc-900 border border-white/[0.04] text-zinc-500 hover:text-[#45A29E] transition-all disabled:opacity-50"
                      >
                        <RefreshCw className="w-3 h-3" />
                      </button>
                      <button 
                        onClick={() => promptDelete(doc)}
                        disabled={doc.status === "Processing"}
                        title="Delete document"
                        className="p-1 rounded bg-zinc-950 hover:bg-zinc-900 border border-white/[0.04] text-zinc-500 hover:text-red-400 transition-all disabled:opacity-50"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                </motion.div>
              ))}
            </motion.div>
          ) : (
            /* Document List Row view */
            <motion.div 
              key="list"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="glass-card rounded-2xl p-5"
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-zinc-400">
                  <thead>
                    <tr className="text-xs text-zinc-400 font-bold uppercase tracking-wider border-b border-white/[0.02] pb-2">
                      <th className="pb-3 font-semibold">Document Name</th>
                      <th className="pb-3 font-semibold">Size</th>
                      <th className="pb-3 font-semibold">Pages</th>
                      <th className="pb-3 font-semibold">Status</th>
                      <th className="pb-3 font-semibold text-right">Extracted Chunks</th>
                      <th className="pb-3 font-semibold text-right">Uploaded Date</th>
                      <th className="pb-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.01]">
                    {filteredDocs.map((doc) => (
                      <tr key={doc.id} className="hover:bg-zinc-900/10 transition-colors">
                        <td className="py-3 font-medium text-zinc-200 flex items-center gap-3">
                          <FileText className="w-4 h-4 text-zinc-400" />
                          <span>{doc.name}</span>
                        </td>
                        <td className="py-3 font-mono text-zinc-400">{doc.size}</td>
                        <td className="py-3 font-mono text-zinc-350">{doc.pages} p.</td>
                        <td className="py-3">
                          {doc.status === "Processing" ? (
                            <span className="text-xs font-mono font-bold text-amber-400 bg-amber-500/5 px-2 py-0.5 rounded border border-amber-500/10 flex items-center gap-1">
                              <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400" />
                              Indexing ({doc.progress}%)
                            </span>
                          ) : doc.status === "Failed" ? (
                            <span className="text-xs font-mono font-bold text-red-400 bg-red-500/5 px-2 py-0.5 rounded border border-red-500/10 flex items-center gap-1">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              Failed
                            </span>
                          ) : (
                            <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/5 px-2 py-0.5 rounded border border-emerald-500/10 flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              Ready
                            </span>
                          )}
                        </td>
                        <td className="py-3 text-right font-mono font-medium text-zinc-300">
                          {doc.status === "Processing" ? "Processing..." : `${doc.chunks} chunks`}
                        </td>
                        <td className="py-3 text-right text-zinc-400 font-normal">{doc.date}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button 
                              onClick={() => handleReingest(doc.id)}
                              disabled={doc.status === "Processing"}
                              className="p-1.5 rounded-lg bg-zinc-950 border border-white/[0.03] hover:border-[#45A29E]/30 text-zinc-500 hover:text-[#45A29E] disabled:opacity-50 transition-colors"
                            >
                              <RefreshCw className="w-3.5 h-3.5" />
                            </button>
                            <button 
                              onClick={() => promptDelete(doc)}
                              disabled={doc.status === "Processing"}
                              className="p-1.5 rounded-lg bg-zinc-950 border border-white/[0.03] hover:border-red-500/30 text-zinc-500 hover:text-red-400 disabled:opacity-50 transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )
        ) : (
          /* Empty State */
          <motion.div 
            key="empty"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            className="glass-card py-16 text-center text-zinc-400 flex flex-col items-center justify-center gap-4 rounded-2xl"
          >
            <div className="w-12 h-12 rounded-full bg-zinc-950 border border-white/[0.04] flex items-center justify-center text-zinc-400 mb-1">
              <Database className="w-6 h-6 text-zinc-650" />
            </div>
            <h4 className="text-sm font-semibold text-zinc-300">No matching files found</h4>
            <p className="text-xs font-normal max-w-xs leading-relaxed">
              No index matched your search keyword or active status filters. Clear filters or upload a file.
            </p>
            <button 
              onClick={() => {
                setSearchQuery("");
                setFilterStatus("all");
              }}
              className="px-4 py-2 rounded-full bg-zinc-900 border border-white/[0.06] hover:border-[#45A29E]/30 text-xs font-semibold text-zinc-300 transition-colors"
            >
              Clear filters
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Radix Dialog Delete Confirmation Modal */}
      <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <Dialog.Portal>
          {/* Overlay background */}
          <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200" />
          
          {/* Modal Content */}
          <Dialog.Content className="fixed top-[30%] left-1/2 -translate-x-1/2 w-full max-w-sm bg-zinc-950 border border-white/[0.08] p-6 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.8)] z-50 focus:outline-none animate-in fade-in zoom-in-95 duration-200 text-left">
            <Dialog.Title className="text-sm font-semibold text-white mb-2">
              Delete Permanently?
            </Dialog.Title>
            <Dialog.Description className="text-xs text-zinc-400 font-normal leading-relaxed mb-6">
              Are you sure you want to delete <strong className="text-zinc-300">{selectedDeleteDoc?.name}</strong>? This operation is permanent and will purge all vector chunks from the database.
            </Dialog.Description>
            
            {/* Action buttons */}
            <div className="flex justify-end gap-3">
              <Dialog.Close asChild>
                <button className="px-4 py-2 rounded-full bg-zinc-900 border border-white/[0.06] hover:border-white/[0.1] text-xs font-semibold text-zinc-350 hover:text-white transition-colors">
                  Cancel
                </button>
              </Dialog.Close>
              <button 
                onClick={confirmDelete}
                className="px-4 py-2 rounded-full bg-red-500 hover:bg-red-600 text-xs font-semibold text-white transition-all shadow-[0_4px_12px_rgba(239,68,68,0.15)]"
              >
                Delete permanently
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

    </div>
  );
}
