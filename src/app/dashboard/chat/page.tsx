"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Send, MessageSquare, FileText, Check, ShieldAlert, Cpu, 
  HelpCircle, Sparkles, ChevronRight, Zap, RefreshCw, X, Paperclip
} from "lucide-react";

interface Message {
  id: string;
  sender: "user" | "ai";
  text: string;
  isStreaming?: boolean;
  citations?: number[];
  latency?: string;
  score?: string;
  insufficientContext?: boolean;
}

interface Citation {
  id: number;
  source: string;
  page: number;
  chunk: number;
  score: string;
  bm25: string;
  rerank: string;
  text: string;
}

export default function ChatSandbox() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      sender: "ai",
      text: "Hello! I am Cited.AI. Ask me anything grounded in your uploaded documents. Answers will arrive with verifiable page-level citations.",
      citations: []
    }
  ]);

  const [inputVal, setInputVal] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Citations side panel state
  const [selectedCitationId, setSelectedCitationId] = useState<number | null>(null);
  const [citationMap, setCitationMap] = useState<Record<number, Citation>>({});

  // In-chat file upload states
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadFileName, setUploadFileName] = useState("");

  // Retrieve current active config parameters
  const getSettings = () => {
    if (typeof window === "undefined") {
      return { 
        backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1", 
        apiKey: "ca_live_dev_test_key",
        modelType: "high",
        temperature: 0.0
      };
    }
    const url = localStorage.getItem("cited_backend_url") || process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1";
    const key = localStorage.getItem("cited_api_key") || "ca_live_dev_test_key";
    const model = localStorage.getItem("cited_model_type") || "high";
    const temp = parseFloat(localStorage.getItem("cited_temperature") || "0.0");
    return { backendUrl: url, apiKey: key, modelType: model, temperature: temp };
  };

  // Chat scroll anchor
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle in-chat file upload via live backend API
  const handleChatFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("The ingestion pipeline only supports PDF files.");
        return;
      }

      const { backendUrl, apiKey } = getSettings();
      setUploadFileName(file.name);
      setUploadProgress(10);
      setIsGenerating(true);

      const sizeStr = file.size > 1024 * 1024 
        ? (file.size / (1024 * 1024)).toFixed(1) + " MB" 
        : (file.size / 1024).toFixed(0) + " KB";

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
          throw new Error(errorData.error?.message || errorData.detail || "Upload failed");
        }

        const data = await res.json();
        const jobId = data.job_id;
        const docId = data.document_id;

        // 2. Poll job status endpoint
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await fetch(`${backendUrl}/ingest/status/${jobId}`, {
              headers: {
                "X-API-Key": apiKey
              }
            });

            if (!statusRes.ok) {
              throw new Error("Failed to check indexing progress.");
            }

            const statusData = await statusRes.json();

            if (statusData.status === "completed") {
              clearInterval(pollInterval);
              setUploadProgress(null);
              setIsGenerating(false);

              // Add file to local storage library
              const savedDocs = localStorage.getItem("cited_documents");
              const docs = savedDocs ? JSON.parse(savedDocs) : [];
              const newDoc = {
                id: docId,
                name: file.name,
                size: sizeStr,
                pages: statusData.pages || 1,
                status: "Indexed",
                chunks: statusData.chunks || 0,
                date: new Date().toISOString().slice(0, 16).replace("T", " ")
              };

              localStorage.setItem("cited_documents", JSON.stringify([newDoc, ...docs]));
              
              // Notify active list listeners
              window.dispatchEvent(new Event("cited_docs_update"));

              // Push system chat message
              setMessages(prev => [
                ...prev,
                {
                  id: String(Date.now()),
                  sender: "ai",
                  text: `System: "${file.name}" has been successfully parsed and indexed into Qdrant Cloud. ${newDoc.chunks} chunks extracted, ${newDoc.pages} pages mapped. You can now query against it.`,
                  citations: []
                }
              ]);

            } else if (statusData.status === "failed") {
              clearInterval(pollInterval);
              setUploadProgress(null);
              setIsGenerating(false);
              alert(statusData.error_message || "Ingestion task failed.");
            } else {
              setUploadProgress(statusData.progress || 30);
            }

          } catch (pollErr: any) {
            clearInterval(pollInterval);
            setUploadProgress(null);
            setIsGenerating(false);
            alert(pollErr.message);
          }
        }, 1000);

      } catch (err: any) {
        setUploadProgress(null);
        setIsGenerating(false);
        alert(err.message || "Failed to establish upload connection to backend.");
      }
    }
  };

  // Handle sending a message with live streaming completions
  const handleSend = async () => {
    if (!inputVal.trim() || isGenerating) return;

    const userMsgId = String(Date.now());
    const userMsg: Message = {
      id: userMsgId,
      sender: "user",
      text: inputVal
    };

    setMessages(prev => [...prev, userMsg]);
    setInputVal("");
    setIsGenerating(true);

    const aiMsgId = String(Date.now() + 1);
    
    // Add temporary loading AI response message
    setMessages(prev => [
      ...prev,
      {
        id: aiMsgId,
        sender: "ai",
        text: "",
        isStreaming: true,
        citations: []
      }
    ]);

    const { backendUrl, apiKey, modelType, temperature } = getSettings();
    const startTime = Date.now();

    try {
      // Submit POST request to stream completions
      const res = await fetch(`${backendUrl}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey
        },
        body: JSON.stringify({
          query: userMsg.text,
          model_type: modelType,
          temperature: temperature,
          stream: true
        })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.error?.message || `API error (HTTP ${res.status})`);
      }

      if (!res.body) {
        throw new Error("No response streaming body returned by the API.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      
      let aiText = "";
      let finalCitations: Citation[] = [];
      let confidenceScore = 0;
      let sufficientContext = true;
      let streamBuffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        streamBuffer += decoder.decode(value, { stream: true });
        const lines = streamBuffer.split("\n");
        // Save the incomplete line back to the buffer
        streamBuffer = lines.pop() || "";

        for (const line of lines) {
          const cleanLine = line.trim();
          if (!cleanLine || !cleanLine.startsWith("data: ")) continue;

          const jsonPayload = cleanLine.substring(6);
          try {
            const eventData = JSON.parse(jsonPayload);
            
            if (eventData.type === "content") {
              aiText += eventData.delta;
              // Update text stream in real time
              setMessages(prev => 
                prev.map(m => m.id === aiMsgId ? { ...m, text: aiText } : m)
              );
            } else if (eventData.type === "metadata") {
              confidenceScore = eventData.confidence_score;
              sufficientContext = eventData.sufficient_context;
              
              // Process and map citations to state
              const metaCitations: Citation[] = (eventData.citations || []).map((c: any) => ({
                id: c.id,
                source: c.source,
                page: c.page,
                chunk: c.chunk,
                score: c.vector_score.toFixed(3),
                bm25: c.bm25_score.toFixed(2),
                rerank: c.rerank_score.toFixed(3),
                text: c.matched_text
              }));
              
              finalCitations = metaCitations;
            }
          } catch (e) {
            console.error("Failed to parse JSON stream block:", e);
          }
        }
      }

      const totalLatency = ((Date.now() - startTime) / 1000).toFixed(2) + "s";

      // Finish streaming, attach final metadata metrics
      setMessages(prev => 
        prev.map(m => m.id === aiMsgId ? { 
          ...m, 
          isStreaming: false, 
          text: aiText,
          citations: finalCitations.map(c => c.id),
          latency: totalLatency,
          score: `${(confidenceScore * 100).toFixed(1)}%`,
          insufficientContext: !sufficientContext
        } : m)
      );

      // Populate citations mapping for right side details panel drawer
      setCitationMap(prev => {
        const next = { ...prev };
        finalCitations.forEach(c => {
          next[c.id] = c;
        });
        return next;
      });

    } catch (err: any) {
      console.error(err);
      setMessages(prev => 
        prev.map(m => m.id === aiMsgId ? { 
          ...m, 
          isStreaming: false, 
          text: `Error connecting to grounding synthesis backend: ${err.message || "Unknown Connection Error"}. Please verify your FastAPI backend is running and Settings API endpoints are configured correctly.` 
        } : m)
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-6 relative">
      
      {/* Left Chat Area */}
      <div className="flex-1 flex flex-col justify-between bg-[#060608] border border-white/[0.04] rounded-2xl overflow-hidden relative">
        
        {/* Chat Header Status */}
        <div className="px-4 py-3 bg-[#08080a] border-b border-white/[0.04] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-semibold text-zinc-300">RAG Agent Ready</span>
          </div>
          <span className="text-xs text-zinc-400 font-mono">Model: 70B AI judge enabled</span>
        </div>

        {/* Messages viewport */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((m) => {
            const isAi = m.sender === "ai";
            return (
              <div 
                key={m.id}
                className={`flex flex-col ${isAi ? "items-start text-left" : "items-end text-right"}`}
              >
                <div 
                  className={`px-4 py-3.5 rounded-2xl text-sm leading-relaxed max-w-xl ${
                    isAi 
                      ? "bg-zinc-950/80 border border-white/[0.03] text-zinc-200 rounded-tl-none font-normal" 
                      : "bg-[#45A29E]/10 border border-[#45A29E]/20 text-[#45A29E] rounded-tr-none font-medium"
                  }`}
                >
                  {/* Text parser for citation numbers [1] etc. to make them interactive buttons */}
                  <p>
                    {isAi 
                      ? m.text.split(/(\[\d+\])/g).map((chunk, i) => {
                          const match = chunk.match(/\[(\d+)\]/);
                          if (match) {
                            const citId = parseInt(match[1]);
                            const isHighlighted = selectedCitationId === citId;
                            return (
                              <button
                                key={i}
                                onClick={() => setSelectedCitationId(selectedCitationId === citId ? null : citId)}
                                className={`inline-flex items-center justify-center w-5 h-5 mx-0.5 text-[9px] font-bold rounded ${
                                  isHighlighted ? "bg-[#45A29E] text-black font-extrabold" : "bg-zinc-800 text-[#45A29E] hover:bg-zinc-700"
                                } transition-all duration-200 cursor-pointer`}
                              >
                                {citId}
                              </button>
                            );
                          }
                          return chunk;
                        })
                      : m.text
                    }
                  </p>

                  {/* Streaming pulse dot */}
                  {m.isStreaming && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#45A29E] animate-ping ml-1" />
                  )}
                </div>

                {/* Sub-text details (Latency, Faithfulness) */}
                {isAi && m.latency && !m.isStreaming && (
                  <div className="flex items-center gap-3 text-xs text-zinc-400 font-mono mt-2 ml-2">
                    <span className="flex items-center gap-1">
                      <Zap className="w-3 h-3 text-[#45A29E]" />
                      Latency: {m.latency}
                    </span>
                    <span className="flex items-center gap-1">
                      {m.insufficientContext ? (
                        <>
                          <ShieldAlert className="w-3 h-3 text-red-400" />
                          <span className="text-red-400 font-medium">Insufficient Context</span>
                        </>
                      ) : (
                        <>
                          <Check className="w-3 h-3 text-green-400" />
                          Confidence: {m.score}
                        </>
                      )}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
          <div ref={scrollRef} />
        </div>

        {uploadProgress !== null && (
          <div className="px-4 py-2.5 bg-zinc-950/80 border-t border-white/[0.04] flex items-center justify-between text-xs text-zinc-400 shrink-0">
            <div className="flex items-center gap-2">
              <RefreshCw className="w-3.5 h-3.5 text-[#45A29E] animate-spin" />
              <span>Parsing and indexing <strong>{uploadFileName}</strong>...</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="w-24 h-1.5 bg-zinc-900 rounded-full overflow-hidden hidden sm:block">
                <div className="h-full bg-[#45A29E]" style={{ width: `${uploadProgress}%` }} />
              </div>
              <span className="font-mono text-[#45A29E] font-bold">{uploadProgress}%</span>
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="p-4 border-t border-white/[0.04] bg-[#08080a] flex items-center gap-3 shrink-0">
          <input 
            type="file"
            id="chat-file-upload"
            accept="application/pdf"
            onChange={handleChatFileUpload}
            disabled={isGenerating}
            className="hidden"
          />
          <label 
            htmlFor="chat-file-upload"
            className="w-10 h-10 rounded-full bg-zinc-900 border border-white/[0.04] hover:border-[#45A29E]/30 flex items-center justify-center text-zinc-400 hover:text-white cursor-pointer transition-colors shrink-0"
          >
            <Paperclip className="w-4 h-4" />
          </label>

          <input 
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            disabled={isGenerating}
            placeholder="Type your question or attach a document..."
            className="flex-1 bg-zinc-950 text-xs px-4 py-3.5 rounded-full border border-white/[0.04] focus:outline-none focus:border-[#45A29E]/30 text-zinc-200 placeholder-zinc-500 transition-all font-normal"
          />
          <button 
            onClick={handleSend}
            disabled={isGenerating || !inputVal.trim()}
            className="w-10 h-10 rounded-full bg-[#45A29E] disabled:bg-zinc-900 border border-transparent disabled:border-white/[0.04] flex items-center justify-center text-black disabled:text-zinc-400 transition-all hover:scale-105 active:scale-95 shrink-0 cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Right Citations panel (collapsible based on selectedCitationId) */}
      <AnimatePresence>
        {selectedCitationId && citationMap[selectedCitationId] && (
          <motion.div 
            initial={{ opacity: 0, x: 20, width: 0 }}
            animate={{ opacity: 1, x: 0, width: 340 }}
            exit={{ opacity: 0, x: 20, width: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="hidden lg:flex flex-col bg-[#060608] border border-white/[0.04] rounded-2xl overflow-hidden shrink-0"
          >
            {/* Header */}
            <div className="px-4 py-3 bg-[#08080a] border-b border-white/[0.04] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#45A29E]" />
                <span className="text-xs font-semibold text-zinc-200">Citation segment [{selectedCitationId}]</span>
              </div>
              <button 
                onClick={() => setSelectedCitationId(null)}
                className="text-zinc-400 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Citation Details Card */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 text-left">
              {/* Document location pills */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider block">Source Details</span>
                <div className="flex flex-wrap gap-2 text-xs font-mono text-[#45A29E]">
                  <span className="px-2.5 py-1 bg-[#45A29E]/5 border border-[#45A29E]/10 rounded-md font-semibold max-w-[200px] truncate" title={citationMap[selectedCitationId]?.source}>
                    {citationMap[selectedCitationId]?.source}
                  </span>
                  <span className="px-2.5 py-1 bg-zinc-950 border border-white/[0.06] rounded-md text-zinc-300 font-medium">
                    Page {citationMap[selectedCitationId]?.page}
                  </span>
                  <span className="px-2.5 py-1 bg-zinc-950 border border-white/[0.06] rounded-md text-zinc-300 font-medium">
                    Chunk {citationMap[selectedCitationId]?.chunk}
                  </span>
                </div>
              </div>

              {/* RAG pipeline Scores */}
              <div className="space-y-2.5 pt-3 border-t border-white/[0.04]">
                <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider block">Matching Scores</span>
                
                <div className="grid grid-cols-3 gap-2 text-center font-mono">
                  <div className="p-2.5 bg-zinc-950 rounded-lg border border-white/[0.04]">
                    <span className="text-xs text-zinc-400 block mb-1">Vector</span>
                    <span className="text-sm font-bold text-zinc-200">{citationMap[selectedCitationId]?.score}</span>
                  </div>
                  <div className="p-2.5 bg-zinc-950 rounded-lg border border-white/[0.04]">
                    <span className="text-xs text-zinc-400 block mb-1">BM25</span>
                    <span className="text-sm font-bold text-zinc-200">{citationMap[selectedCitationId]?.bm25}</span>
                  </div>
                  <div className="p-2.5 bg-zinc-950 rounded-lg border border-white/[0.04]">
                    <span className="text-xs text-zinc-400 block mb-1">Reranker</span>
                    <span className="text-sm font-bold text-zinc-200">{citationMap[selectedCitationId]?.rerank}</span>
                  </div>
                </div>
              </div>

              {/* Matched text snippet */}
              <div className="space-y-2 pt-3 border-t border-white/[0.04]">
                <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider block">Context Payload</span>
                <div className="p-3.5 bg-zinc-950 border border-white/[0.04] rounded-xl text-sm text-zinc-300 leading-relaxed font-normal font-sans">
                  &ldquo;{citationMap[selectedCitationId]?.text}&rdquo;
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
