'use client'

import Image from 'next/image'
import { useState, useRef, useEffect } from 'react'
import Header from './Header'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import MemoryInspector from './MemoryInspector'
import ChatHistory from './ChatHistory'
import Settings from './Settings'
import { APP_NAME } from '@/lib/env'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { useToast } from '@/hooks/use-toast'

interface Memory {
  id: string // This will be the key
  key: string
  value: string
  memory_type: 'identity' | 'preference' | 'general'
  confidence: number
  source: string
  timestamp: string
}

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

interface UploadedFile {
  filename: string
  file_type: string
  chunks_indexed: number
  characters: number
}

// Backend URL — reads the public env var baked in at build time,
// falls back to localhost for local dev.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || 'http://127.0.0.1:8000'
const SESSION_STORAGE_KEY = 'ethio_claw_session_id'

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [memories, setMemories] = useState<Memory[]>([])
  const [sidebarExpanded, setSidebarExpanded] = useState(false)
  const [sidebarTab, setSidebarTab] = useState<'history' | 'memory'>('history')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sessionId, setSessionId] = useState('default')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatInputRef = useRef<any>(null)
  const { toast } = useToast()

  const loadMemories = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/facts`)
      if (res.ok) {
        const data = await res.json()
        const mappedMemories = (data.facts || []).map((f: any) => ({
          id: f.key,
          key: f.key,
          value: f.value,
          memory_type: f.memory_type,
          confidence: f.confidence,
          source: f.source,
          timestamp: new Date().toISOString(),
        }))
        setMemories(mappedMemories)
      }
    } catch (error: any) {
      console.error('[ChatPage] Failed to load memories:', error)
    }
  }

  const handleSessionSelect = async (id: string) => {
    setSessionId(id)
    window.localStorage.setItem(SESSION_STORAGE_KEY, id)
    setIsLoading(true)
    try {
      const res = await fetch(`${BACKEND_URL}/sessions/${id}/history`)
      if (res.ok) {
        const data = await res.json()
        setMessages(data.history || [])
        toast({
          title: 'Chat Loaded',
          description: `Switched to session ${id.slice(0, 8)}...`,
        })
      }
    } catch (error) {
      console.error('[ChatPage] Failed to load history:', error)
      toast({
        title: 'Error',
        description: 'Failed to load chat history.',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    const newId = `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    setSessionId(newId)
    window.localStorage.setItem(SESSION_STORAGE_KEY, newId)
    setMessages([])
    toast({
      title: 'New Chat Started',
      description: 'Ready for a fresh conversation.',
    })
  }

  const handleDeleteSession = async (id: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/sessions/${id}`, { method: 'DELETE' })
      if (res.ok) {
        toast({
          title: 'Session Deleted',
          description: 'The chat history has been removed.',
        })
        if (id === sessionId) {
          handleNewChat()
        }
      }
    } catch (error) {
      console.error('[ChatPage] Failed to delete session:', error)
    }
  }

  // Scroll to bottom when new messages arrive or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Load memories on mount
  useEffect(() => {
    loadMemories()
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return

    let stored = window.localStorage.getItem(SESSION_STORAGE_KEY)
    if (!stored) {
      stored = `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
      window.localStorage.setItem(SESSION_STORAGE_KEY, stored)
    } else {
      handleSessionSelect(stored)
    }
    setSessionId(stored)
  }, [])

  const handleAddMemory = async (factStr: string) => {
    try {
      let key = `manual-${Date.now()}`
      let value = factStr
      if (factStr.includes(':')) {
        const parts = factStr.split(':')
        key = parts[0].trim()
        value = parts.slice(1).join(':').trim()
      }

      const res = await fetch(`${BACKEND_URL}/facts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key,
          value,
          memory_type: 'general',
          confidence: 1.0,
          source: 'user'
        }),
      })
      if (res.ok) {
        toast({
          title: 'Memory Added',
          description: `Fact "${key}: ${value}" added successfully.`,
        })
        loadMemories()
      }
    } catch (error: any) {
      console.error('[ChatPage] Failed to add memory:', error)
    }
  }

  const handleDeleteMemory = async (id: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/facts/${id}`, { method: 'DELETE' })
      if (res.ok) {
        toast({
          title: 'Memory Deleted',
          description: 'Memory removed successfully.',
        })
        loadMemories()
      }
    } catch (error: any) {
      console.error('[ChatPage] Failed to delete memory:', error)
    }
  }

  const handleEditMemory = async (id: string, newFactValue: string) => {
    try {
      const existingMemory = memories.find(m => m.id === id)
      if (!existingMemory) return

      const res = await fetch(`${BACKEND_URL}/facts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: existingMemory.key,
          value: newFactValue,
          memory_type: existingMemory.memory_type,
          confidence: existingMemory.confidence,
          source: existingMemory.source,
        }),
      })

      if (res.ok) {
        toast({
          title: 'Memory Updated',
          description: 'Memory updated successfully.',
        })
        loadMemories()
      }
    } catch (error: any) {
      console.error('[ChatPage] Failed to edit memory:', error)
    }
  }

  const handleClearChat = () => {
    setMessages([])
  }

  const handleFilesSelected = async (files: File[]) => {
    if (!files.length || isUploading) return

    setIsUploading(true)
    try {
      const formData = new FormData()
      files.forEach((file) => {
        formData.append('files', file)
      })
      formData.append('session_id', sessionId)

      const res = await fetch(`${BACKEND_URL}/documents/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText || `Upload failed with status ${res.status}`)
      }

      const data = (await res.json()) as {
        status: string
        session_id: string
        files: UploadedFile[]
      }

      const fileSummary = data.files
        .map((file) => `${file.filename} (${file.chunks_indexed} chunks)`)
        .join(', ')

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Indexed uploaded files into RAG: ${fileSummary || 'no readable content found'}.`,
        },
      ])
    } catch (error) {
      console.error('[ChatPage] File upload failed:', error)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Could not index uploaded files: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ])
    } finally {
      setIsUploading(false)
      chatInputRef.current?.clearFiles()
    }
  }

  const handleSendMessage = async (message: string) => {
    const trimmed = message.trim()
    if (!trimmed || isLoading) return

    const userMsg: Message = { role: 'user', content: trimmed }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, session_id: sessionId }),
      })

      if (!res.ok) {
        const errText = await res.text()
        console.error('[ChatPage] Backend error:', res.status, errText)
        const errorMsg: Message = {
          role: 'assistant',
          content: `⚠️ Backend error (${res.status}): ${errText}`,
        }
        setMessages((prev) => [...prev, errorMsg])
        return
      }

      const data = await res.json()
      const assistantText = data.response || data.message || JSON.stringify(data)

      const assistantMsg: Message = { role: 'assistant', content: assistantText }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (error) {
      console.error('[ChatPage] Fetch error:', error)
      const errorMsg: Message = {
        role: 'assistant',
        content: '⚠️ Could not reach the backend. Is it running?',
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-dvh bg-background overflow-hidden">
      <Header
        onMemoryToggle={() => {
          if (sidebarExpanded && sidebarTab === 'memory') {
            setSidebarExpanded(false)
          } else {
            setSidebarExpanded(true)
            setSidebarTab('memory')
          }
        }}
        memoryOpen={sidebarExpanded && sidebarTab === 'memory'}
        onHistoryToggle={() => {
          if (sidebarExpanded && sidebarTab === 'history') {
            setSidebarExpanded(false)
          } else {
            setSidebarExpanded(true)
            setSidebarTab('history')
          }
        }}
        historyOpen={sidebarExpanded && sidebarTab === 'history'}
        onSettingsToggle={() => setSettingsOpen(true)}
        onClearChat={handleClearChat}
      />

      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-background border-r border-border/30">
          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-hidden">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-20 h-20 overflow-hidden rounded-full border-4 border-primary mb-6 flex items-center justify-center bg-card shadow-[0_0_20px_rgba(var(--primary-rgb),0.5)]">
                  <span className="text-primary text-4xl font-bold">AI</span>
                </div>
                <h2 className="neon-text text-3xl mb-4 text-foreground">Welcome to {APP_NAME}</h2>
                <p className="text-muted-foreground text-lg mb-2">Your Advanced Cognitive AI Assistant</p>
                <p className="text-muted-foreground/60 max-w-sm">
                  Ask me anything! I&apos;ll provide intelligent responses powered by a layered memory system.
                </p>
              </div>
            ) : (
              <>
                {messages.map((message, index) => (
                  <ChatMessage
                    key={index}
                    role={message.role as any}
                    content={message.content}
                    onQuote={(text) => chatInputRef.current?.appendQuote(text)}
                  />
                ))}
                {isLoading && (
                  <div className="flex gap-4 mb-6 animate-pulse duration-1000">
                    <div className="flex-shrink-0">
                      <Avatar className="size-12 border-2 border-cyan-400">
                        <AvatarFallback className="bg-gray-800 text-cyan-400 font-bold">AI</AvatarFallback>
                      </Avatar>
                    </div>
                    <div className="flex flex-col items-start">
                      <p className="text-cyan-300 text-xs mb-2 font-semibold">AI Assistant</p>
                      <div className="message-bubble message-bubble-ai flex items-center gap-2">
                        <span className="text-sm">Thinking</span>
                        <span className="flex gap-1 items-center">
                          <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                          <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                          <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-bounce"></span>
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <ChatInput
            ref={chatInputRef}
            onSubmit={handleSendMessage}
            onFilesSelected={handleFilesSelected}
            isLoading={isLoading}
            isUploading={isUploading}
          />
        </div>

        {/* Right Sidebar - Collapsible with Tabs */}
        {sidebarExpanded && (
          <div className="hidden lg:flex lg:flex-col lg:w-80 bg-card border-l-2 border-border animate-in slide-in-from-right duration-300">
            {/* Tabs Header */}
            <div className="flex border-b border-border/30">
              <button
                onClick={() => setSidebarTab('history')}
                className={`flex-1 p-3 text-[10px] font-bold uppercase tracking-wider transition-colors ${
                  sidebarTab === 'history'
                    ? 'text-primary border-b-2 border-primary bg-primary/5'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                History
              </button>
              <button
                onClick={() => setSidebarTab('memory')}
                className={`flex-1 p-3 text-[10px] font-bold uppercase tracking-wider transition-colors ${
                  sidebarTab === 'memory'
                    ? 'text-primary border-b-2 border-primary bg-primary/5'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Memory
              </button>
              <button
                onClick={() => setSidebarExpanded(false)}
                className="p-3 text-muted-foreground hover:text-destructive transition-colors"
                title="Close Sidebar"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-hidden">
              {sidebarTab === 'history' ? (
                <ChatHistory
                  currentSessionId={sessionId}
                  onSessionSelect={handleSessionSelect}
                  onNewChat={handleNewChat}
                  onDeleteSession={handleDeleteSession}
                  backendUrl={BACKEND_URL}
                />
              ) : (
                <MemoryInspector
                  memories={memories}
                  onAddMemory={handleAddMemory}
                  onDeleteMemory={handleDeleteMemory}
                  onEditMemory={handleEditMemory}
                />
              )}
            </div>
          </div>
        )}
      </div>

      <Settings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
