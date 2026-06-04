'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import Header from './Header'
import ChatMessage from './ChatMessage'
import PillChatInput, { ChatInputRef } from './PillChatInput'
import MemoryInspector from './MemoryInspector'
import ChatHistory from './ChatHistory'
import Settings from './Settings'
import Sidebar from './Sidebar'
import { useToast } from '@/hooks/use-toast'

interface Memory {
  id: string
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

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || 'http://127.0.0.1:8000'
const SESSION_STORAGE_KEY = 'ethio_claw_session_id'

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [memories, setMemories] = useState<Memory[]>([])
  const [sidebarTab, setSidebarTab] = useState<'history' | 'memory' | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sessionId, setSessionId] = useState('default')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatInputRef = useRef<ChatInputRef>(null)
  const { toast } = useToast()

  const loadMemories = useCallback(async () => {
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
  }, [])

  const handleSessionSelect = useCallback(async (id: string) => {
    setSessionId(id)
    window.localStorage.setItem(SESSION_STORAGE_KEY, id)
    setIsLoading(true)
    try {
      const res = await fetch(`${BACKEND_URL}/sessions/${id}/history`)
      if (res.ok) {
        const data = await res.json()
        setMessages(data.history || [])
      }
    } catch (error) {
      console.error('[ChatPage] Failed to load history:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleNewChat = () => {
    const newId = `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    setSessionId(newId)
    window.localStorage.setItem(SESSION_STORAGE_KEY, newId)
    setMessages([])
  }

  const handleDeleteSession = async (id: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/sessions/${id}`, { method: 'DELETE' })
      if (res.ok && id === sessionId) handleNewChat()
    } catch (error) {
      console.error('[ChatPage] Failed to delete session:', error)
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    loadMemories()
    let stored = window.localStorage.getItem(SESSION_STORAGE_KEY)
    if (!stored) {
      stored = `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
      window.localStorage.setItem(SESSION_STORAGE_KEY, stored)
    }
    setSessionId(stored)
    handleSessionSelect(stored)
  }, [loadMemories, handleSessionSelect])

  const handleFilesSelected = async (files: File[]) => {
    if (!files.length || isUploading) return
    setIsUploading(true)
    try {
      const formData = new FormData()
      files.forEach(file => formData.append('files', file))
      formData.append('session_id', sessionId)
      const res = await fetch(`${BACKEND_URL}/documents/upload`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      const fileSummary = data.files.map((file: any) => `${file.filename} (${file.chunks_indexed} chunks)`).join(', ')
      setMessages((prev) => [...prev, { role: 'assistant', content: `Indexed uploaded files into RAG: ${fileSummary || 'no readable content found'}.` }])
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `⚠️ Upload failed: ${error}` }])
    } finally {
      setIsUploading(false)
    }
  }

  const handleSendMessage = async (message: string) => {
    const trimmed = message.trim()
    if (!trimmed || isLoading) return
    
    chatInputRef.current?.clearInput()
    
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    setIsLoading(true)
    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, session_id: sessionId }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response }])
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'assistant', content: '⚠️ Backend error.' }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuote = (text: string) => {
    chatInputRef.current?.appendQuote(text)
  }

  return (
    <div className="flex h-dvh bg-background overflow-hidden">
      <Sidebar 
        onTabChange={setSidebarTab} 
        onSettingsClick={() => setSettingsOpen(true)}
        onClearChat={() => setMessages([])}
        activeTab={sidebarTab || 'history'}
      />
      
      <div className="flex-1 flex flex-col min-w-0 bg-background">
        <Header />
        
        <div className={`flex-1 overflow-y-auto p-6 space-y-4 pb-32 ${messages.length === 0 ? 'flex flex-col items-center justify-center' : ''}`}>
          {messages.length === 0 ? (
            <div className="text-center">
              <h2 className="text-3xl font-bold text-foreground mb-2">Welcome to EthioClaw</h2>
              <p className="text-muted-foreground">Ask anything to start a conversation.</p>
            </div>
          ) : (
            messages.map((message, index) => (
              <ChatMessage
                key={index}
                role={message.role as any}
                content={message.content}
                isNew={index === messages.length - 1 && message.role === 'assistant'}
                onQuote={handleQuote}
              />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <PillChatInput 
          ref={chatInputRef}
          onSubmit={handleSendMessage} 
          onFilesSelected={handleFilesSelected}
          isLoading={isLoading} 
        />

      </div>

      {sidebarTab && (
        <div className="w-80 border-l border-border overflow-hidden bg-card animate-in slide-in-from-right duration-300">
          <div className="flex border-b border-border/30">
            <button onClick={() => setSidebarTab('history')} className={`flex-1 p-3 text-xs font-bold uppercase ${sidebarTab === 'history' ? 'text-primary bg-primary/5' : 'text-muted-foreground'}`}>History</button>
            <button onClick={() => setSidebarTab('memory')} className={`flex-1 p-3 text-xs font-bold uppercase ${sidebarTab === 'memory' ? 'text-primary bg-primary/5' : 'text-muted-foreground'}`}>Memory</button>
            <button onClick={() => setSidebarTab(null)} className="p-3 text-muted-foreground hover:text-destructive">✕</button>
          </div>
          <div className="flex-1 overflow-hidden p-4">
            {sidebarTab === 'history' ? (
              <ChatHistory 
                currentSessionId={sessionId} 
                onSessionSelect={handleSessionSelect} 
                onNewChat={handleNewChat} 
                onDeleteSession={handleDeleteSession} 
                backendUrl={BACKEND_URL} 
              />
            ) : (
              <MemoryInspector memories={memories} />
            )}
          </div>
        </div>
      )}

      <Settings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
