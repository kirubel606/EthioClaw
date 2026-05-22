'use client'

import { useState, useRef, useEffect, FormEvent } from 'react'
import { useChat } from '@ai-sdk/react'
import Header from './Header'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import MemoryInspector from './MemoryInspector'

interface Memory {
  id: string
  fact: string
  timestamp: string
}

export default function ChatPage() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',
  })
  const [memories, setMemories] = useState<Memory[]>([])
  const [memoryExpanded, setMemoryExpanded] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

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

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden">
      <Header onMemoryToggle={() => setMemoryExpanded(!memoryExpanded)} memoryOpen={memoryExpanded} />

      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-gradient-to-b from-blue-950 via-purple-950 to-blue-950">
          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin scrollbar-thumb-cyan-400 scrollbar-track-gray-900">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="portal-effect w-20 h-20 border-4 border-cyan-400 rounded-full mb-6 flex items-center justify-center">
                  <span className="text-3xl text-green-400">◇</span>
                </div>
                <h2 className="neon-text text-3xl mb-4">Welcome to EthioClaw</h2>
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
                  content={message.content}
                />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form onSubmit={handleSubmit} className="border-t-2 border-cyan-400 bg-gradient-to-r from-blue-950 to-purple-950 p-6 shadow-lg">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={input || ''}
                  onChange={handleInputChange}
                  placeholder="Ask Rick anything... (or just burp)"
                  disabled={isLoading}
                  className="w-full bg-gray-900 border-2 border-cyan-400 rounded-lg px-4 py-3 text-green-400 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:border-transparent transition-all duration-200 hover:border-green-400"
                />
                <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-cyan-400 text-xs">
                  ▶
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading || !input || !input.trim()}
                className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold px-6 py-3 rounded-lg border-2 border-cyan-300 transition-all duration-200 hover:shadow-lg hover:shadow-cyan-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="animate-spin">⟳</span>
                    Thinking...
                  </span>
                ) : (
                  'Send'
                )}
              </button>
            </div>

            <div className="mt-3 text-xs text-gray-500 flex justify-between items-center">
              <p>💬 Press Enter or click Send</p>
              <p className="text-green-400">█ Connected</p>
            </div>
          </form>
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
    </div>
  )
}
