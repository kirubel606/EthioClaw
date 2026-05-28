'use client'

import { CheckCircle2, XCircle, BadgeInfo, TrendingUp, TrendingDown, PauseCircle } from 'lucide-react'
import RichText from './RichText'

export interface TradingSignal {
  signal_id: string
  status?: string
  pair: string
  timeframe: string
  balance?: number
  direction: string
  confidence: number
  entry?: number | null
  stop_loss?: number | null
  take_profit?: number | null
  risk_amount: number
  lot_size: number
  rr_ratio: string
  reasons?: string[]
  actionable?: boolean
  summary?: string
}

interface TradingSignalCardProps {
  signal: TradingSignal
  actionState?: 'idle' | 'taking' | 'rejecting' | 'taken' | 'rejected'
  onTake: () => void | Promise<void>
  onReject: () => void | Promise<void>
}

export default function TradingSignalCard({
  signal,
  actionState = 'idle',
  onTake,
  onReject,
}: TradingSignalCardProps) {
  const isWait = signal.direction === 'WAIT'
  const isBuy = signal.direction === 'BUY'
  const isSell = signal.direction === 'SELL'
  
  const locked = 
    actionState === 'taken' || 
    actionState === 'rejected' || 
    signal.status === 'TAKEN' || 
    signal.status === 'REJECTED' ||
    !signal.actionable

  const getStatusColor = () => {
    if (isBuy) return 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10'
    if (isSell) return 'text-rose-400 border-rose-400/40 bg-rose-400/10'
    return 'text-amber-400 border-amber-400/40 bg-amber-400/10'
  }

  const getConfidenceColor = () => {
    if (signal.confidence > 70) return 'bg-emerald-500'
    if (signal.confidence > 50) return 'bg-amber-500'
    return 'bg-rose-500'
  }

  return (
    <div className="rounded-lg border-2 border-border bg-black/60 backdrop-blur-xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)] font-mono">
      {/* Terminal Header */}
      <div className={`px-5 py-3 border-b-2 flex items-center justify-between ${getStatusColor().split(' ')[1]}`}>
        <div className="flex items-center gap-3">
          {isBuy && <TrendingUp className="size-5 text-emerald-400" />}
          {isSell && <TrendingDown className="size-5 text-rose-400" />}
          {isWait && <PauseCircle className="size-5 text-amber-400" />}
          <span className="text-xs font-black tracking-[0.3em] uppercase">
            {signal.direction} SIGNAL :: {signal.pair}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="px-2 py-0.5 rounded border border-current text-[10px] font-black uppercase opacity-80">
            {signal.status || 'READY'}
          </div>
          <div className="text-[10px] font-bold opacity-50 tracking-widest">
            {signal.signal_id.slice(0, 8)}
          </div>
        </div>
      </div>

      <div className="p-8">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-8">
          <div className="space-y-1">
            <div className="flex items-baseline gap-3">
              <span className={`text-5xl font-black tracking-tighter ${isBuy ? 'text-emerald-400' : isSell ? 'text-rose-400' : 'text-amber-400'}`}>
                {signal.direction}
              </span>
              <span className="text-2xl font-black text-foreground/90">{signal.pair}</span>
            </div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-[0.3em] font-black">
              TIME FRAME: {signal.timeframe} • RISK REWARD: {signal.rr_ratio}
            </p>
          </div>

          <div className="flex flex-col items-end gap-2 min-w-[200px]">
            <div className="flex justify-between w-full text-[10px] font-black uppercase tracking-[0.2em] mb-1">
              <span className="text-muted-foreground">Execution Confidence</span>
              <span className={signal.confidence > 70 ? 'text-emerald-400' : 'text-amber-400'}>
                {signal.confidence}%
              </span>
            </div>
            <div className="w-full h-2 bg-muted/30 rounded-full overflow-hidden border border-border/50">
              <div 
                className={`h-full transition-all duration-1000 shadow-[0_0_10px_rgba(0,0,0,0.5)] ${getConfidenceColor()}`}
                style={{ width: `${signal.confidence}%` }}
              />
            </div>
          </div>
        </div>

        {/* Technical Specs Grid */}
        <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="p-4 rounded-lg bg-background/40 border-2 border-border/30 hover:border-primary/30 transition-colors group">
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-black mb-2 group-hover:text-primary transition-colors">Entry Price</p>
            <p className="text-lg font-black text-foreground tabular-nums">{signal.entry ?? '---'}</p>
          </div>
          <div className="p-4 rounded-lg bg-background/40 border-2 border-rose-500/20 hover:border-rose-500/40 transition-colors group">
            <p className="text-[10px] text-rose-400/60 uppercase tracking-widest font-black mb-2 group-hover:text-rose-400 transition-colors">Stop Loss</p>
            <p className="text-lg font-black text-rose-400 tabular-nums">{signal.stop_loss ?? '---'}</p>
          </div>
          <div className="p-4 rounded-lg bg-background/40 border-2 border-emerald-500/20 hover:border-emerald-500/40 transition-colors group">
            <p className="text-[10px] text-emerald-400/60 uppercase tracking-widest font-black mb-2 group-hover:text-emerald-400 transition-colors">Take Profit</p>
            <p className="text-lg font-black text-emerald-400 tabular-nums">{signal.take_profit ?? '---'}</p>
          </div>
          <div className="p-4 rounded-lg bg-background/40 border-2 border-border/30 hover:border-primary/30 transition-colors group">
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-black mb-2 group-hover:text-primary transition-colors">Risk / Units</p>
            <p className="text-lg font-black text-foreground tabular-nums">
              ${signal.risk_amount} <span className="text-[10px] text-muted-foreground ml-1">@ {signal.lot_size}</span>
            </p>
          </div>
        </div>

        {/* Confluence Section */}
        {signal.reasons?.length ? (
          <div className="mt-10 pt-6 border-t-2 border-border/20">
            <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground font-black mb-4">Technical Confluence Analysis</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-3">
              {signal.reasons.map((reason, idx) => (
                <div key={idx} className="flex items-start gap-3 text-xs border-b border-border/10 pb-2">
                  <span className="text-primary font-black opacity-40 leading-none">0{idx + 1}</span>
                  <span className="text-foreground/70 leading-relaxed uppercase tracking-tight">{reason}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* Summary Block */}
        {signal.summary ? (
          <div className="mt-10 p-6 rounded-lg bg-primary/5 border-l-4 border-primary/40 text-sm text-muted-foreground italic leading-relaxed font-sans">
            <RichText content={signal.summary} />
          </div>
        ) : null}

        {/* Control Interface */}
        <div className="mt-10 flex flex-wrap items-center gap-6">
          <button
            type="button"
            onClick={onTake}
            disabled={locked || actionState === 'taking'}
            className="flex-1 min-w-[200px] flex items-center justify-center gap-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:bg-emerald-500/10 text-black font-black uppercase text-xs py-4 transition-all active:scale-[0.98] disabled:cursor-not-allowed shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)]"
          >
            <CheckCircle2 className="size-5" />
            {actionState === 'taking' ? 'Executing Order...' : 'Confirm Execution'}
          </button>
          
          <button
            type="button"
            onClick={onReject}
            disabled={locked || actionState === 'rejecting'}
            className="flex-1 min-w-[200px] flex items-center justify-center gap-3 rounded-lg border-2 border-rose-500/40 hover:bg-rose-500/10 disabled:opacity-20 text-rose-500 font-black uppercase text-xs py-4 transition-all active:scale-[0.98] disabled:cursor-not-allowed"
          >
            <XCircle className="size-5" />
            {actionState === 'rejecting' ? 'Rejecting Signal...' : 'Reject Signal'}
          </button>

          {!signal.actionable && (
            <div className="w-full flex items-center justify-center gap-3 p-4 rounded-lg bg-amber-500/5 border-2 border-amber-500/20 text-amber-500 text-[10px] font-black uppercase tracking-[0.3em]">
              <BadgeInfo className="size-5 opacity-70" />
              Disciplined Wait :: Insufficient Market Confluence
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
