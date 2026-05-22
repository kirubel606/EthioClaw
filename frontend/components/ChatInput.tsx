'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'

interface ChatInputProps {
  onSubmit: (message: string) => void | Promise<void>
  isLoading?: boolean
}

export default function ChatInput({ onSubmit, isLoading }: ChatInputProps) {
  const [input, setInput] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isLoading) {
      try {
        await onSubmit(input)
        setInput('')
      } catch (error) {
        console.error('[v0] Failed to submit chat input:', error)
      }
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t-2 border-cyan-400 bg-gradient-to-r from-blue-950 to-purple-950 p-6 shadow-lg"
    >
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Rick anything... (or just burp)"
            disabled={isLoading}
            className="w-full bg-gray-900 border-2 border-cyan-400 rounded-lg px-4 py-3 text-green-400 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:border-transparent transition-all duration-200 hover:border-green-400"
          />
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-cyan-400 text-xs">
            ▶
          </div>
        </div>

        <Button
          type="submit"
          disabled={isLoading || !input.trim()}
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
        </Button>
      </div>

      <div className="mt-3 text-xs text-gray-500 flex justify-between items-center">
        <p>💬 Press Enter or click Send</p>
        <p className="text-green-400">█ Connected</p>
      </div>
    </form>
  )
}
