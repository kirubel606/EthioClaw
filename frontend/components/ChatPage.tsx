'use client'

import Image from 'next/image'
import { useState, useRef, useEffect } from 'react'
import Header from './Header'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import MemoryInspector from './MemoryInspector'
import ChatHistory from './ChatHistory'
import TradingSignalCard, { type TradingSignal } from './TradingSignalCard'
import TradingSetupModal, { type TradingSessionConfig } from './TradingSetupModal'
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
  signal?: TradingSignal
  signalActionState?: 'idle' | 'taking' | 'rejecting' | 'taken' | 'rejected'
}

interface UploadedFile {
  filename: string
  file_type: string
  chunks_indexed: number
  characters: number
}

type AppMode = 'agent' | 'trading'

// Backend URL — reads the public env var baked in at build time,
// falls back to localhost for local dev.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || 'http://127.0.0.1:8000'
const MODE_STORAGE_KEY = 'ethio_claw_mode'
const AGENT_SESSION_STORAGE_KEY = 'ethio_claw_agent_session_id'
const TRADING_SESSION_STORAGE_KEY = 'ethio_claw_trading_session_id'
const TRADING_SESSION_CONFIGS_KEY = 'ethio_claw_trading_session_configs'

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [memories, setMemories] = useState<Memory[]>([])
  const [sidebarExpanded, setSidebarExpanded] = useState(false)
  const [sidebarTab, setSidebarTab] = useState<'history' | 'memory'>('history')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [mode, setMode] = useState<AppMode>('agent')
  const [sessionId, setSessionId] = useState('default')
  const [isTradingSetupOpen, setIsTradingSetupOpen] = useState(false)
  const [pendingTradingSessionId, setPendingTradingSessionId] = useState<string | null>(null)
  const [tradingSessions, setTradingSessions] = useState<Record<string, TradingSessionConfig>>({})
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

  const handleSessionSelect = async (id: string, forceMode?: AppMode) => {
    // Detect mode from session ID prefix OR existing trading config
    const isTradingPrefix = id.startsWith('trading-') || id.startsWith('trading:')
    const hasTradingConfig = !!loadTradingSessionConfigs()[id]
    const detectedMode: AppMode = (isTradingPrefix || hasTradingConfig) ? 'trading' : 'agent'
    
    // Use forceMode if provided (e.g. during a toggle), otherwise use detected
    const targetMode = forceMode || detectedMode
    
    if (targetMode !== mode) {
      setMode(targetMode)
      window.localStorage.setItem(MODE_STORAGE_KEY, targetMode)
    }

    setSessionId(id)
    persistSessionForMode(targetMode, id)
    setIsLoading(true)
    try {
      const res = await fetch(`${BACKEND_URL}/sessions/${id}/history`)
      if (res.ok) {
        const data = await res.json()
        // Map backend metadata to signal property
        const history = (data.history || []).map((msg: any) => ({
          ...msg,
          signal: msg.metadata || msg.signal, // Restore persisted signal data
        }))
        setMessages(history)
        toast({
          title: targetMode === 'trading' ? 'Trading Chat Loaded' : 'Chat Loaded',
          description: `Switched to session ${id.slice(0, 8)}...`,
        })
      }
      // Note: We NO LONGER pop the modal here. 
      // We only pop it if they try to perform a trading action (Get Signal) on a session with no config.
      if (targetMode === 'agent') {
        setIsTradingSetupOpen(false)
        setPendingTradingSessionId(null)
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
    const newId = createSessionId(mode)
    setSessionId(newId)
    persistSessionForMode(mode, newId)
    setMessages([])
    setIsLoading(false)
    chatInputRef.current?.clearFiles()

    if (mode === 'trading') {
      setPendingTradingSessionId(newId)
      setIsTradingSetupOpen(true)
    } else {
      toast({
        title: 'New Chat Started',
        description: 'Ready for a fresh conversation.',
      })
    }
  }

  const handleDeleteSession = async (id: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/sessions/${id}`, { method: 'DELETE' })
      if (res.ok) {
        if (mode === 'trading') {
          const next = { ...tradingSessions }
          delete next[id]
          saveTradingSessionConfigs(next)
        }
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

  const createSessionId = (currentMode: AppMode) =>
    `${currentMode}-session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

  const getModeStorageKey = (currentMode: AppMode) =>
    currentMode === 'trading' ? TRADING_SESSION_STORAGE_KEY : AGENT_SESSION_STORAGE_KEY

  const persistSessionForMode = (currentMode: AppMode, id: string) => {
    window.localStorage.setItem(getModeStorageKey(currentMode), id)
  }

  const loadTradingSessionConfigs = () => {
    if (typeof window === 'undefined') return {}
    const raw = window.localStorage.getItem(TRADING_SESSION_CONFIGS_KEY)
    if (!raw) return {}
    try {
      return JSON.parse(raw) as Record<string, TradingSessionConfig>
    } catch {
      return {}
    }
  }

  const saveTradingSessionConfigs = (configs: Record<string, TradingSessionConfig>) => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(TRADING_SESSION_CONFIGS_KEY, JSON.stringify(configs))
    setTradingSessions(configs)
  }

  const getTradingSessionConfig = (id: string) => tradingSessions[id]

  const upsertTradingSessionConfig = (id: string, config: TradingSessionConfig) => {
    const next = { ...tradingSessions, [id]: config }
    saveTradingSessionConfigs(next)
  }

  const initializeSessionForMode = (currentMode: AppMode) => {
    const storageKey = getModeStorageKey(currentMode)
    let stored = window.localStorage.getItem(storageKey)
    
    // Validation: Ensure the stored session ID matches the mode prefix
    const isTradingPrefix = stored?.startsWith('trading-') || stored?.startsWith('trading:')
    const isValidForMode = currentMode === 'trading' ? isTradingPrefix : !isTradingPrefix

    if (!stored || !isValidForMode) {
      stored = createSessionId(currentMode)
      window.localStorage.setItem(storageKey, stored)
    }
    setSessionId(stored)
    return stored
  }

  const handleTradingSetupSave = async (config: TradingSessionConfig) => {
    const nextSessionId = pendingTradingSessionId || createSessionId('trading')
    upsertTradingSessionConfig(nextSessionId, config)
    persistSessionForMode('trading', nextSessionId)
    setSessionId(nextSessionId)
    setMode('trading')
    window.localStorage.setItem(MODE_STORAGE_KEY, 'trading')
    setIsLoading(false)
    setIsTradingSetupOpen(false)
    setPendingTradingSessionId(null)
    chatInputRef.current?.clearFiles()

    try {
      await fetch(`${BACKEND_URL}/trading/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default',
          balance: config.balance,
          preferred_pair: config.pair,
          preferred_timeframe: config.timeframe,
          style: 'intraday',
          risk_percent: 1,
          max_daily_loss: 3,
          max_open_trades: 1,
          preferred_sessions: [],
        }),
      })
    } catch (error) {
      console.error('[ChatPage] Failed to save trading profile:', error)
    }

    toast({
      title: 'Trading Chat Ready',
      description: `Session created for ${config.pair} with balance ${config.balance}.`,
    })
  }

  const handleTradingSetupCancel = () => {
    setIsTradingSetupOpen(false)
    setPendingTradingSessionId(null)
    
    // If we already have a valid trading session for the CURRENT sessionId, just stay there.
    const existingConfig = getTradingSessionConfig(sessionId)
    if (existingConfig) {
      return
    }

    // Otherwise, try to find ANY previous valid trading session to load.
    const configs = loadTradingSessionConfigs()
    const sessionIds = Object.keys(configs)
    if (sessionIds.length > 0) {
      const lastSessionId = sessionIds[sessionIds.length - 1]
      void handleSessionSelect(lastSessionId)
      return
    }

    // If absolutely no configured trading sessions exist, fall back to agent mode.
    setMode('agent')
    window.localStorage.setItem(MODE_STORAGE_KEY, 'agent')
    const agentSession = initializeSessionForMode('agent')
    void handleSessionSelect(agentSession)
  }

  const formatTradingSignal = (data: any) => {
    if (!data || typeof data !== 'object') {
      return String(data || 'Trading signal generated.')
    }

    const reasons = Array.isArray(data.reasons) ? data.reasons : []
    const lines = [
      `${data.direction || 'HOLD'} ${data.pair || 'Unknown pair'} on ${data.timeframe || 'Unknown timeframe'}`,
      `Confidence: ${data.confidence ?? 'n/a'}%`,
      `Entry: ${data.entry ?? 'n/a'}`,
      `Stop Loss: ${data.stop_loss ?? 'n/a'}`,
      `Take Profit: ${data.take_profit ?? 'n/a'}`,
      `Risk: ${data.risk_amount ?? 'n/a'}`,
      `Lot Size: ${data.lot_size ?? 'n/a'}`,
      `Balance: ${data.balance ?? 'n/a'}`,
      `RR Ratio: ${data.rr_ratio ?? 'n/a'}`,
    ]

    if (reasons.length > 0) {
      lines.push('Reasons:')
      reasons.forEach((reason: string) => lines.push(`- ${reason}`))
    }

    if (data.summary) {
      lines.push('')
      lines.push(data.summary)
    }

    return lines.join('\n')
  }

  const handleModeToggle = () => {
    const nextMode: AppMode = mode === 'agent' ? 'trading' : 'agent'
    
    // Explicitly reset trading modal states when switching modes
    setIsTradingSetupOpen(false)
    setPendingTradingSessionId(null)
    
    setMode(nextMode)
    window.localStorage.setItem(MODE_STORAGE_KEY, nextMode)
    setMessages([])
    setIsLoading(false)
    chatInputRef.current?.clearFiles()

    const nextSessionId = initializeSessionForMode(nextMode)
    
    // We just load the session. If it's a trading session with no config,
    // the UI will show '---' in the status bar, and the modal will pop 
    // ONLY when they click 'Get Signal'.
    void handleSessionSelect(nextSessionId, nextMode)
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

    setTradingSessions(loadTradingSessionConfigs())

    const storedMode = window.localStorage.getItem(MODE_STORAGE_KEY)
    const initialMode: AppMode = storedMode === 'trading' ? 'trading' : 'agent'
    setMode(initialMode)

    const storedSession = initializeSessionForMode(initialMode)
    void handleSessionSelect(storedSession, initialMode)
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
    setIsLoading(false)
    chatInputRef.current?.clearFiles()
  }

  const handleFilesSelected = async (files: File[]) => {
    if (mode === 'trading') {
      toast({
        title: 'Trading Mode',
        description: 'Strategy uploads are handled through the trading upload flow.',
      })
      return
    }

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

  const handleTradingFilesSelected = async (files: File[]) => {
    if (!files.length || isUploading) return

    setIsUploading(true)
    try {
      const formData = new FormData()
      files.forEach((file) => {
        formData.append('files', file)
      })
      formData.append('session_id', sessionId)

      const res = await fetch(`${BACKEND_URL}/trading/strategies/upload`, {
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
          content: `Indexed strategy files into trading RAG: ${fileSummary || 'no readable content found'}.`,
        },
      ])
      toast({
        title: 'Strategy Uploaded',
        description: 'The trading strategy RAG collection has been updated.',
      })
    } catch (error) {
      console.error('[ChatPage] Strategy upload failed:', error)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Could not index trading strategy files: ${error instanceof Error ? error.message : 'Unknown error'}`,
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

    if (mode === 'trading') {
      const config = getTradingSessionConfig(sessionId)
      if (!config) {
        setPendingTradingSessionId(sessionId)
        setIsTradingSetupOpen(true)
        toast({
          title: 'Trading Setup Required',
          description: 'Enter a pair and balance before generating a signal.',
          variant: 'destructive',
        })
        return
      }
    }

    const userMsg: Message = { role: 'user', content: trimmed }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      const endpoint =
        mode === 'trading'
          ? `${BACKEND_URL}/trading/signals/generate`
          : `${BACKEND_URL}/chat`

      const payload =
        mode === 'trading'
          ? {
              message: trimmed,
              session_id: sessionId,
              user_id: 'default',
              pair: getTradingSessionConfig(sessionId)?.pair,
              balance: getTradingSessionConfig(sessionId)?.balance,
              timeframe: getTradingSessionConfig(sessionId)?.timeframe,
            }
          : { message: trimmed, session_id: sessionId }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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
      const assistantText =
        mode === 'trading'
          ? formatTradingSignal(data)
          : data.response || data.message || JSON.stringify(data)

      const assistantMsg: Message =
        mode === 'trading'
          ? {
              role: 'assistant',
              content: assistantText,
              signal: data,
              signalActionState: 'idle',
            }
          : { role: 'assistant', content: assistantText }
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

  const updateSignalMessage = (
    signalId: string,
    updater: (message: Message) => Message,
  ) => {
    setMessages((prev) =>
      prev.map((message) => {
        if (message.signal?.signal_id !== signalId) return message
        return updater(message)
      }),
    )
  }

  const handleTakeSignal = async (signal_id: string) => {
    updateSignalMessage(signal_id, (message) => ({
      ...message,
      signalActionState: 'taking',
    }))

    try {
      const res = await fetch(`${BACKEND_URL}/trading/trades/take`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id, user_id: 'default' }),
      })

      if (!res.ok) {
        throw new Error(await res.text())
      }

      const data = await res.json()
      updateSignalMessage(signal_id, (message) => ({
        ...message,
        signalActionState: 'taken',
        // Update status but keep the summary clean
      }))
      toast({
        title: 'Execution Confirmed',
        description: `Trade ID: ${data.trade_id?.slice(0, 8) || 'unknown'}`,
      })
    } catch (error) {
      console.error('[ChatPage] Failed to take signal:', error)
      updateSignalMessage(signal_id, (message) => ({
        ...message,
        signalActionState: 'idle',
      }))
      toast({
        title: 'Execution Failed',
        description: 'Check connectivity or market status.',
        variant: 'destructive',
      })
    }
  }

  const handleRejectSignal = async (signal_id: string) => {
    updateSignalMessage(signal_id, (message) => ({
      ...message,
      signalActionState: 'rejecting',
    }))

    try {
      const res = await fetch(`${BACKEND_URL}/trading/trades/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signal_id, user_id: 'default' }),
      })

      if (!res.ok) {
        throw new Error(await res.text())
      }

      updateSignalMessage(signal_id, (message) => ({
        ...message,
        signalActionState: 'rejected',
      }))
      toast({
        title: 'Signal Discarded',
        description: 'Preference recorded in journal.',
      })
    } catch (error) {
      console.error('[ChatPage] Failed to reject signal:', error)
      updateSignalMessage(signal_id, (message) => ({
        ...message,
        signalActionState: 'idle',
      }))
      toast({
        title: 'Action Failed',
        variant: 'destructive',
      })
    }
  }

  const handleInitiateTradingSignal = () => {
    const config = getTradingSessionConfig(sessionId)
    if (!config) {
      setPendingTradingSessionId(sessionId)
      setIsTradingSetupOpen(true)
      toast({
        title: 'Configuration Required',
        description: 'Please set a pair and balance before scanning.',
      })
      return
    }
    void handleSendMessage(`Initiate a trading signal for ${config.pair} on ${config.timeframe} with balance ${config.balance}.`)
  }

  const activeTradingConfig = mode === 'trading' ? getTradingSessionConfig(sessionId) : undefined

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
        mode={mode}
        onModeToggle={handleModeToggle}
      />

      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-background border-r border-border/30">
          {mode === 'trading' && (
            <div className="border-b-2 border-amber-400/20 bg-black/60 px-6 py-3 backdrop-blur-md">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-6">
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase tracking-[0.2em] text-amber-400/70 font-bold">Instrument</span>
                    <span className="text-sm font-black text-foreground">{activeTradingConfig?.pair || '---'}</span>
                  </div>
                  <div className="w-px h-8 bg-border/40" />
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase tracking-[0.2em] text-amber-400/70 font-bold">Balance</span>
                    <span className="text-sm font-black text-foreground">${activeTradingConfig?.balance ?? '---'}</span>
                  </div>
                  <div className="w-px h-8 bg-border/40" />
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase tracking-[0.2em] text-amber-400/70 font-bold">Timeframe</span>
                    <span className="text-sm font-black text-foreground">{activeTradingConfig?.timeframe || '---'}</span>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleInitiateTradingSignal}
                    className="flex items-center gap-2 rounded border border-amber-400/50 bg-amber-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-amber-400 transition-all hover:bg-amber-400/20 active:scale-95"
                  >
                    Get Signal
                  </button>
                  <button
                    type="button"
                    onClick={handleNewChat}
                    className="flex items-center gap-2 rounded border border-border bg-muted/20 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground transition-all hover:bg-muted/30 active:scale-95"
                  >
                    New Setup
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-hidden">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-20 h-20 overflow-hidden rounded-full border-4 border-primary mb-6 flex items-center justify-center bg-card shadow-[0_0_20px_rgba(var(--primary-rgb),0.5)]">
                  <span className="text-primary text-4xl font-bold">AI</span>
                </div>
                <h2 className="neon-text text-3xl mb-4 text-foreground">
                  {mode === 'trading' ? `Trading Desk — ${APP_NAME}` : `Welcome to ${APP_NAME}`}
                </h2>
                <p className="text-muted-foreground text-lg mb-2">
                  {mode === 'trading'
                    ? 'Deterministic trade analysis, risk control, and strategy memory'
                    : 'Your Advanced Cognitive AI Assistant'}
                </p>
                <p className="text-muted-foreground/60 max-w-sm">
                  {mode === 'trading'
                    ? 'Ask for a setup review, strategy check, or signal generation. The user stays in control.'
                    : "Ask me anything! I'll provide intelligent responses powered by a layered memory system."}
                </p>
              </div>
            ) : (
              <>
                {messages.map((message, index) => {
                  const isAssistant = message.role === 'assistant'
                  const isTradingMode = mode === 'trading'

                  // RULE: Trading Mode ASSISTANT messages MUST strictly use TradingSignalCard
                  if (isTradingMode && isAssistant) {
                    const signalData: TradingSignal = message.signal || {
                      signal_id: `hist-${index}`,
                      pair: activeTradingConfig?.pair || '---',
                      timeframe: activeTradingConfig?.timeframe || '---',
                      direction: 'WAIT',
                      confidence: 0,
                      risk_amount: 0,
                      lot_size: 0,
                      rr_ratio: '0:0',
                      summary: message.content,
                      actionable: false,
                    }

                    return (
                      <div key={index} className="w-full max-w-3xl mx-auto my-8 px-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
                        <TradingSignalCard
                          signal={{
                            ...signalData,
                            status:
                              message.signalActionState && message.signalActionState !== 'idle'
                                ? message.signalActionState.toUpperCase()
                                : signalData.status || 'READY',
                          }}
                          actionState={message.signalActionState}
                          onTake={() => handleTakeSignal(signalData.signal_id)}
                          onReject={() => handleRejectSignal(signalData.signal_id)}
                        />
                      </div>
                    )
                  }

                  // RULE: Everything else (User messages in any mode, and all Agent messages) use ChatMessage
                  return (
                    <div key={index} className={`${isTradingMode ? 'w-full max-w-3xl mx-auto px-4' : ''}`}>
                      <ChatMessage
                        role={message.role as any}
                        content={message.content}
                        onQuote={(text) => chatInputRef.current?.appendQuote(text)}
                        mode={mode}
                      />
                    </div>
                  )
                })}
                {isLoading && (
                  <div className={`flex gap-4 mb-6 animate-pulse duration-1000 ${mode === 'trading' ? 'w-full max-w-3xl mx-auto px-4' : ''}`}>
                    <div className="flex-shrink-0">
                      <Avatar className={`size-12 border-2 ${mode === 'trading' ? 'border-amber-500' : 'border-cyan-400'}`}>
                        <AvatarFallback className={`${mode === 'trading' ? 'bg-black text-amber-500' : 'bg-gray-800 text-cyan-400'} font-bold`}>
                          {mode === 'trading' ? 'TD' : 'AI'}
                        </AvatarFallback>
                      </Avatar>
                    </div>
                    <div className="flex flex-col items-start">
                      <p className={`${mode === 'trading' ? 'text-amber-500' : 'text-cyan-300'} text-xs mb-2 font-semibold`}>
                        {mode === 'trading' ? 'Terminal Processing' : 'AI Assistant'}
                      </p>
                      <div className={`message-bubble ${mode === 'trading' ? 'message-bubble-trading border-l-4 border-l-amber-500' : 'message-bubble-ai'} flex items-center gap-2`}>
                        <span className="text-sm">{mode === 'trading' ? 'Scanning Market' : 'Thinking'}</span>
                        <span className="flex gap-1 items-center">
                          <span className={`w-1.5 h-1.5 ${mode === 'trading' ? 'bg-amber-500' : 'bg-green-400'} rounded-full animate-bounce [animation-delay:-0.3s]`}></span>
                          <span className={`w-1.5 h-1.5 ${mode === 'trading' ? 'bg-amber-500' : 'bg-green-400'} rounded-full animate-bounce [animation-delay:-0.15s]`}></span>
                          <span className={`w-1.5 h-1.5 ${mode === 'trading' ? 'bg-amber-500' : 'bg-green-400'} rounded-full animate-bounce`}></span>
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
            onStrategyFilesSelected={handleTradingFilesSelected}
            isLoading={isLoading}
            isUploading={isUploading}
            mode={mode}
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
                  mode={mode}
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

      <TradingSetupModal
        isOpen={isTradingSetupOpen}
        initialPair={pendingTradingSessionId ? getTradingSessionConfig(pendingTradingSessionId)?.pair : undefined}
        initialBalance={pendingTradingSessionId ? getTradingSessionConfig(pendingTradingSessionId)?.balance : undefined}
        initialTimeframe={pendingTradingSessionId ? getTradingSessionConfig(pendingTradingSessionId)?.timeframe : undefined}
        onSave={handleTradingSetupSave}
        onCancel={handleTradingSetupCancel}
      />

      <Settings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
