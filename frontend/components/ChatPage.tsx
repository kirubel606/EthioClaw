'use client'

import Image from 'next/image'
import { useState, useRef, useEffect } from 'react'
import Header from './Header'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import MemoryInspector from './MemoryInspector'
import Settings from './Settings'
import { APP_NAME } from '@/lib/env'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

interface Memory {
  id: string
  fact: string
  timestamp: string
}

interface Message {
  role: 'user' | 'assistant'
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
  const [memoryExpanded, setMemoryExpanded] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sessionId, setSessionId] = useState('default')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatInputRef = useRef<any>(null)

  // Scroll to bottom when new messages arrive or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Load memories on mount
  useEffect(() => {
    const loadMemories = async () => {
      try {
        const res = await fetch('/api/facts')
        if (res.ok) {
          const data = await res.json()
          setMemories(data)
        }
      } catch (error) {
        console.error('[v0] Failed to load memories:', error)
      }
    }
    loadMemories()
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return

    let stored = window.localStorage.getItem(SESSION_STORAGE_KEY)
    if (!stored) {
      stored = `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
      window.localStorage.setItem(SESSION_STORAGE_KEY, stored)
    }
    setSessionId(stored)
  }, [])

  const handleAddMemory = async (fact: string) => {
    try {
      const res = await fetch('/api/facts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fact }),
      })
      if (res.ok) {
        const newMemory = await res.json()
        setMemories((prev) => [...prev, newMemory])
      }
    } catch (error) {
      console.error('[v0] Failed to add memory:', error)
    }
  }

  const handleDeleteMemory = async (id: string) => {
    try {
      await fetch(`/api/facts/${id}`, { method: 'DELETE' })
      setMemories((prev) => prev.filter((m) => m.id !== id))
    } catch (error) {
      console.error('[v0] Failed to delete memory:', error)
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

    // 1. Immediately show the user message
    const userMsg: Message = { role: 'user', content: trimmed }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      // 2. POST directly to the FastAPI backend
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

      // 3. Parse the JSON response — backend returns { "response": "..." }
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
        onMemoryToggle={() => setMemoryExpanded(!memoryExpanded)}
        memoryOpen={memoryExpanded}
        onSettingsToggle={() => setSettingsOpen(true)}
        onClearChat={handleClearChat}
      />

      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-gradient-to-b from-blue-950 via-purple-950 to-blue-950">
          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-hidden">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="portal-effect w-20 h-20 overflow-hidden rounded-full border-4 border-cyan-400 mb-6">
                  <Image
                    src="/rick-avatar.jpg"
                    alt="Rick avatar"
                    width={80}
                    height={80}
                    className="h-full w-full object-cover"
                    priority
                  />
                </div>
                <h2 className="neon-text text-3xl mb-4">Welcome to {APP_NAME}</h2>
                <p className="text-cyan-300 text-lg mb-2">An AI Agent Powered by Rick Sanchez</p>
                <p className="text-gray-400 max-w-sm">
                  Ask me anything! I&apos;ll give you answers with a burp and a portal jump.
                </p>
              </div>
            ) : (
              <>
                {messages.map((message, index) => (
                  <ChatMessage
                    key={index}
                    role={message.role}
                    content={message.content}
                    onQuote={(text) => chatInputRef.current?.appendQuote(text)}
                  />
                ))}
                {isLoading && (
                  <div className="flex gap-4 mb-6 animate-pulse duration-1000">
                    <div className="flex-shrink-0">
                      <Avatar className="rick-avatar size-12">
                        <AvatarImage src="/rick-avatar.jpg" alt="Rick the AI" className="object-cover" />
                        <AvatarFallback>R</AvatarFallback>
                      </Avatar>
                    </div>
                    <div className="flex flex-col items-start">
                      <p className="text-cyan-300 text-xs mb-2 font-semibold">RICK (AI Agent)</p>
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

        {/* Memory Inspector Sidebar - Opens on demand */}
        {memoryExpanded && (
          <div className="hidden lg:flex lg:flex-col lg:w-80 lg:bg-gradient-to-b lg:from-blue-950 lg:to-purple-950 lg:border-l-2 lg:border-cyan-400 lg:border-r-2 animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between p-4 border-b border-cyan-400/30">
              <h3 className="text-green-400 font-bold text-sm">Memory Bank</h3>
              <button
                onClick={() => setMemoryExpanded(false)}
                className="text-cyan-400 hover:text-red-400 transition-colors p-1 hover:bg-cyan-400/10 rounded"
                title="Close"
              >
                ✕
              </button>
            </div>
            <MemoryInspector
              memories={memories}
              onAddMemory={handleAddMemory}
              onDeleteMemory={handleDeleteMemory}
            />
          </div>
        )}
      </div>

      <Settings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
