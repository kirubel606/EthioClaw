'use client'

import Image from 'next/image'
import { useState, useRef, useEffect } from 'react'
import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'
import Header from './Header'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import MemoryInspector from './MemoryInspector'
import Settings from './Settings'
import { APP_NAME } from '@/lib/env'

interface Memory {
  id: string
  fact: string
  timestamp: string
}

const chatTransport = new DefaultChatTransport({
  api: '/api/chat',
})

function getMessageText(message: { content?: string; parts?: Array<{ type: string; text?: string }> }) {
  if (typeof message.content === 'string' && message.content.trim()) {
    return message.content
  }

  return message.parts
    ?.filter((part): part is { type: 'text'; text: string } => part.type === 'text' && typeof part.text === 'string')
    .map((part) => part.text)
    .join('')
    .trim()
}

export default function ChatPage() {
  const { messages, setMessages, sendMessage, status } = useChat({
    transport: chatTransport,
  })
  const [memories, setMemories] = useState<Memory[]>([])
  const [memoryExpanded, setMemoryExpanded] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const isLoading = status === 'submitted' || status === 'streaming'

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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

  const handleSendMessage = async (message: string) => {
    const trimmed = message.trim()
    if (!trimmed || isLoading) {
      return
    }

    try {
      await sendMessage({ text: trimmed })
    } catch (error) {
      console.error('[v0] Failed to send chat message:', error)
      throw error
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
              messages.map((message, index) => (
                <ChatMessage
                  key={index}
                  role={message.role as 'user' | 'assistant'}
                  content={getMessageText(message) || '[No text content]'}
                />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <ChatInput onSubmit={handleSendMessage} isLoading={isLoading} />
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
