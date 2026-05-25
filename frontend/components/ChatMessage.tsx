'use client'

import { useState } from 'react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { MessageSquareQuote } from 'lucide-react'
import RichText from './RichText'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  onQuote?: (text: string) => void
}

export default function ChatMessage({ role, content, onQuote }: ChatMessageProps) {
  const isAI = role === 'assistant'
  const [selection, setSelection] = useState('')
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })

  const handleSelection = () => {
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed) {
      setSelection('')
      return
    }

    const text = sel.toString().trim()
    if (!text) {
      setSelection('')
      return
    }

    try {
      const range = sel.getRangeAt(0)
      const rect = range.getBoundingClientRect()
      // Position fixed coordinates slightly above the selection middle
      setTooltipPos({
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
      })
      setSelection(text)
    } catch {
      setSelection('')
    }
  }

  const handleQuoteClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (onQuote) {
      onQuote(selection)
    }
    // Clear selection
    window.getSelection()?.removeAllRanges()
    setSelection('')
  }

  return (
    <div 
      className={`flex gap-4 mb-6 animate-in fade-in slide-in-from-bottom-3 duration-500 relative ${isAI ? '' : 'justify-end'}`}
      onMouseUp={handleSelection}
      onKeyUp={handleSelection}
    >
      {isAI && (
        <div className="flex-shrink-0">
          <Avatar className="rick-avatar size-12">
            <AvatarImage src="/rick-avatar.jpg" alt="Rick the AI" className="object-cover" />
            <AvatarFallback>R</AvatarFallback>
          </Avatar>
        </div>
      )}

      <div className={`flex flex-col ${isAI ? 'items-start' : 'items-end'} max-w-[85%] sm:max-w-[75%]`}>
        {isAI && <p className="text-cyan-300 text-xs mb-2 font-semibold">RICK (AI Agent)</p>}

        <div
          className={`message-bubble ${isAI ? 'message-bubble-ai' : 'message-bubble-user'}`}
        >
          <RichText content={content} />
        </div>

        {isAI && (
          <p className="text-xs text-green-400 mt-1 opacity-70">
            [burp] Portal engaged...
          </p>
        )}
      </div>

      {!isAI && (
        <div className="flex-shrink-0">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center border-2 border-cyan-400 text-white font-bold text-lg">
            M
          </div>
        </div>
      )}

      {/* Floating Quote Reply Button */}
      {selection && onQuote && (
        <button
          onMouseDown={(e) => e.preventDefault()} // Prevents selection loss
          onClick={handleQuoteClick}
          style={{
            position: 'fixed',
            left: `${tooltipPos.x}px`,
            top: `${tooltipPos.y}px`,
            transform: 'translate(-50%, -100%)',
            zIndex: 9999,
          }}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 border border-cyan-300 text-white text-xs font-bold shadow-lg shadow-cyan-500/30 transition-all duration-200 animate-in fade-in zoom-in-95 duration-100"
        >
          <MessageSquareQuote className="size-3.5" />
          <span>Quote Reply</span>
        </button>
      )}
    </div>
  )
}
