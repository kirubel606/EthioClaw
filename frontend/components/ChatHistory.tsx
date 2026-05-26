'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Plus, MessageSquare, Trash2, Clock } from 'lucide-react'

interface Session {
  id: string
  title: string
  updated_at: string
}

interface ChatHistoryProps {
  currentSessionId: string
  onSessionSelect: (sessionId: string) => void
  onNewChat: () => void
  onDeleteSession: (sessionId: string) => void
  backendUrl: string
}

export default function ChatHistory({
  currentSessionId,
  onSessionSelect,
  onNewChat,
  onDeleteSession,
  backendUrl,
}: ChatHistoryProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const loadSessions = async () => {
    setIsLoading(true)
    try {
      const res = await fetch(`${backendUrl}/sessions`)
      if (res.ok) {
        const data = await res.json()
        setSessions(data.sessions || [])
      }
    } catch (error) {
      console.error('[ChatHistory] Failed to load sessions:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadSessions()
    // Refresh sessions periodically or when backend might have updated
    const interval = setInterval(loadSessions, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="h-full flex flex-col bg-card border-l border-border/30">
      <div className="p-4 border-b border-border/30">
        <Button
          onClick={onNewChat}
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground gap-2 font-bold"
        >
          <Plus className="size-4" />
          New Chat
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2 scrollbar-hidden">
        {isLoading && sessions.length === 0 ? (
          <div className="flex justify-center p-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-muted-foreground text-xs text-center py-8">
            No previous chats found.
          </p>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => onSessionSelect(session.id)}
              className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all duration-200 border ${
                currentSessionId === session.id
                  ? 'bg-primary/20 border-primary text-primary-foreground'
                  : 'bg-transparent border-transparent hover:bg-muted/50 text-muted-foreground hover:text-foreground'
              }`}
            >
              <div className="flex items-center gap-3 overflow-hidden">
                <MessageSquare className={`size-4 flex-shrink-0 ${currentSessionId === session.id ? 'text-primary' : 'text-muted-foreground'}`} />
                <div className="flex flex-col overflow-hidden">
                  <span className="text-sm font-medium truncate">
                    {session.title || 'Untitled Chat'}
                  </span>
                  <span className="text-[10px] opacity-60 flex items-center gap-1">
                    <Clock className="size-3" />
                    {new Date(session.updated_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteSession(session.id)
                }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-all"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="p-4 border-t border-border/30 text-center">
        <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">
          Chat History
        </p>
      </div>
    </div>
  )
}
