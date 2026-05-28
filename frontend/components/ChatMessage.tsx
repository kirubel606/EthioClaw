'use client'

import { useState } from 'react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { MessageSquareQuote } from 'lucide-react'
import RichText from './RichText'

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'system'
  content: string
  onQuote?: (text: string) => void
  mode?: 'agent' | 'trading'
}

export default function ChatMessage({ role, content, onQuote, mode = 'agent' }: ChatMessageProps) {
  const isUser = role === 'user'
  const isAI = role === 'assistant'
  const isSystem = role === 'system'
  const isTrading = mode === 'trading'
  
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
        <div className={`bg-muted/30 border border-border/50 rounded-full px-4 py-1.5 text-[10px] uppercase tracking-widest font-bold flex items-center gap-2 ${isTrading ? 'text-amber-500' : 'text-muted-foreground'}`}>
          <span className={`size-1.5 rounded-full animate-pulse ${isTrading ? 'bg-amber-500' : 'bg-primary/50'}`} />
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
          <Avatar className={`size-12 border-2 ${isTrading ? 'border-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.3)]' : 'border-primary'}`}>
            <AvatarFallback className={`${isTrading ? 'bg-black text-amber-500' : 'bg-muted text-primary'} font-black uppercase text-xs`}>
              {isTrading ? 'TD' : 'AI'}
            </AvatarFallback>
          </Avatar>
        </div>
      )}
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} ${isTrading && isAI ? 'flex-1' : ''}`}>
        {isAI && (
          <p className={`${isTrading ? 'text-amber-500 font-black tracking-widest uppercase text-[10px]' : 'text-primary font-semibold text-xs'} mb-2`}>
            {isTrading ? 'Trading Desk :: Analysis' : 'AI Assistant'}
          </p>
        )}

        <div
          className={`message-bubble ${
            isAI 
              ? (isTrading ? 'message-bubble-trading !max-w-none w-full border-l-4 border-l-amber-500' : 'message-bubble-ai') 
              : 'message-bubble-user'
          }`}
        >
          <RichText content={content} />
        </div>
      </div>
      {!isAI && (
        <div className="flex-shrink-0">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 font-bold text-lg ${
            isTrading 
              ? 'bg-black border-amber-500/50 text-amber-500' 
              : 'bg-primary border-border text-primary-foreground'
          }`}>
            U
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
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 border border-border text-primary-foreground text-xs font-bold shadow-lg transition-all duration-200 animate-in fade-in zoom-in-95 duration-100"
        >
          <MessageSquareQuote className="size-3.5" />
          <span>Quote Reply</span>
        </button>
      )}
    </div>
  )
}
