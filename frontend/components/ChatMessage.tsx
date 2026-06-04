'use client'

import { useState } from 'react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { MessageSquareQuote } from 'lucide-react'
import RichText from './RichText'
import { useTypingEffect } from '@/hooks/use-typing-effect'

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'system'
  content: string
  onQuote?: (text: string) => void
  isNew?: boolean
}

export default function ChatMessage({ role, content, onQuote, isNew = false }: ChatMessageProps) {
  const isUser = role === 'user'
  const isAI = role === 'assistant'
  const isSystem = role === 'system'

  // Use typing effect only for NEW AI messages
  const { displayedText } = useTypingEffect(
    isAI && isNew ? content : content,
    isAI && isNew ? 15 : 0 // 0 speed means no delay if not typing
  )

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
    window.getSelection()?.removeAllRanges()
    setSelection('')
  }

  if (isSystem) {
    return (
      <div className="flex justify-center my-4 animate-in fade-in slide-in-from-top-2 duration-500">
        <div className="bg-muted/30 border border-border/50 rounded-full px-4 py-1.5 text-[10px] text-muted-foreground uppercase tracking-widest font-bold flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-primary/50 animate-pulse" />
          {content}
        </div>
      </div>
    )
  }

  return (
    <div
      className={`flex gap-4 mb-6 animate-in fade-in slide-in-from-bottom-3 duration-500 relative ${isAI ? '' : 'justify-end'}`}
      onMouseUp={handleSelection}
      onKeyUp={handleSelection}
    >
      {isAI && (
        <div className="flex-shrink-0">
          <Avatar className="size-12 border border-border">
            <AvatarFallback className="bg-card text-foreground font-bold">AI</AvatarFallback>
          </Avatar>
        </div>
      )}
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        {isAI && <p className="text-muted-foreground text-xs mb-2 font-semibold">AI Assistant</p>}

        <div
          className={`message-bubble ${isAI ? 'message-bubble-ai' : 'message-bubble-user'}`}
        >
          <RichText content={isAI && isNew ? displayedText : content} />
        </div>
      </div>
      {!isAI && (
        <div className="flex-shrink-0">
          <div className="w-12 h-12 rounded-full bg-accent flex items-center justify-center border border-border text-accent-foreground font-bold text-lg">
            U
          </div>
        </div>
      )}

      {/* Floating Quote Reply Button */}
      {selection && onQuote && (
        <button
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleQuoteClick}
          style={{
            position: 'fixed',
            left: `${tooltipPos.x}px`,
            top: `${tooltipPos.y}px`,
            transform: 'translate(-50%, -100%)',
            zIndex: 9999,
          }}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-card hover:bg-muted border border-border text-foreground text-xs font-bold shadow-lg transition-all duration-200 animate-in fade-in zoom-in-95 duration-100"
        >
          <MessageSquareQuote className="size-3.5" />
          <span>Quote Reply</span>
        </button>
      )}
    </div>
  )
}
