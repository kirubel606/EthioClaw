'use client'

import { useEffect, useState } from 'react'

export interface TradingSessionConfig {
  pair: string
  balance: number
  timeframe: string
}

interface TradingSetupModalProps {
  isOpen: boolean
  initialPair?: string
  initialBalance?: number
  initialTimeframe?: string
  onSave: (config: TradingSessionConfig) => void | Promise<void>
  onCancel: () => void
}

export default function TradingSetupModal({
  isOpen,
  initialPair = 'XAU/USD',
  initialBalance = 1000,
  initialTimeframe = '15M',
  onSave,
  onCancel,
}: TradingSetupModalProps) {
  const [pair, setPair] = useState(initialPair)
  const [balance, setBalance] = useState(String(initialBalance))
  const [timeframe, setTimeframe] = useState(initialTimeframe)

  const SUPPORTED_INSTRUMENTS = [
    {
      label: 'Commodities',
      options: [
        { label: 'Gold (XAU/USD)', value: 'XAU/USD' },
        { label: 'Silver (XAG/USD)', value: 'XAG/USD' },
        { label: 'US Oil (WTI)', value: 'WTI/USD' },
        { label: 'UK Oil (Brent)', value: 'BRENT/USD' },
      ],
    },
    {
      label: 'Forex Majors',
      options: [
        { label: 'EUR/USD', value: 'EUR/USD' },
        { label: 'GBP/USD', value: 'GBP/USD' },
        { label: 'USD/JPY', value: 'USD/JPY' },
        { label: 'AUD/USD', value: 'AUD/USD' },
        { label: 'USD/CAD', value: 'USD/CAD' },
        { label: 'USD/CHF', value: 'USD/CHF' },
        { label: 'GBP/JPY', value: 'GBP/JPY' },
      ],
    },
    {
      label: 'Crypto',
      options: [
        { label: 'Bitcoin (BTC/USD)', value: 'BTC/USD' },
        { label: 'Ethereum (ETH/USD)', value: 'ETH/USD' },
        { label: 'Solana (SOL/USD)', value: 'SOL/USD' },
      ],
    },
    {
      label: 'Indices',
      options: [
        { label: 'S&P 500 (SPX)', value: 'SPX' },
        { label: 'Nasdaq 100 (IXIC)', value: 'IXIC' },
        { label: 'Dow Jones (DJI)', value: 'DJI' },
      ],
    },
  ]

  useEffect(() => {
    if (!isOpen) return
    setPair(initialPair)
    setBalance(String(initialBalance))
    setTimeframe(initialTimeframe)
  }, [isOpen, initialPair, initialBalance, initialTimeframe])

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const parsedBalance = Number(balance)
    if (!pair.trim() || !Number.isFinite(parsedBalance) || parsedBalance <= 0) return
    await onSave({
      pair: pair.trim(),
      balance: parsedBalance,
      timeframe: timeframe.trim() || '15M',
    })
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/85 backdrop-blur-sm px-4 font-mono">
      <div className="w-full max-w-md rounded-lg border-2 border-amber-500/40 bg-black/90 p-8 shadow-[0_0_50px_rgba(245,158,11,0.2)]">
        <div className="mb-8">
          <p className="text-[10px] uppercase tracking-[0.3em] text-amber-500 font-black">System :: Initializing Setup</p>
          <h2 className="mt-2 text-2xl font-black text-foreground tracking-tighter uppercase">Configure Terminal</h2>
          <p className="mt-3 text-xs text-muted-foreground/80 leading-relaxed font-sans">
            Specify instrument and capital allocation for the active scanning session.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <label className="block space-y-2">
            <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Select Instrument</span>
            <select
              value={pair}
              onChange={(e) => setPair(e.target.value)}
              className="w-full rounded border-2 border-border/50 bg-background px-4 py-3 text-sm text-foreground outline-none focus:border-amber-500/50 transition-colors cursor-pointer appearance-none"
            >
              {SUPPORTED_INSTRUMENTS.map((group) => (
                <optgroup key={group.label} label={group.label} className="bg-card text-amber-500 font-bold uppercase text-[10px]">
                  {group.options.map((opt) => (
                    <option key={opt.value} value={opt.value} className="bg-background text-foreground text-sm font-sans">
                      {opt.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>

          <label className="block space-y-2">
            <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Allocated Balance (USD)</span>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-amber-500 font-black text-sm">$</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
                className="w-full rounded border-2 border-border/50 bg-background pl-8 pr-4 py-3 text-sm text-foreground font-black outline-none focus:border-amber-500/50 transition-colors"
                placeholder="1000.00"
              />
            </div>
          </label>

          <label className="block space-y-2">
            <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Scan Timeframe</span>
            <div className="grid grid-cols-3 gap-2">
              {['5M', '15M', '1H', '4H', '1D'].map((tf) => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => setTimeframe(tf)}
                  className={`py-2 text-[10px] font-black rounded border-2 transition-all ${
                    timeframe === tf
                      ? 'border-amber-500 bg-amber-500/20 text-amber-400'
                      : 'border-border/40 bg-transparent text-muted-foreground hover:border-border hover:text-foreground'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </label>

          <div className="flex gap-4 pt-4">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 rounded border-2 border-border/50 px-4 py-3 text-[10px] font-black uppercase tracking-widest text-muted-foreground hover:bg-muted/10 transition-colors"
            >
              Abort
            </button>
            <button
              type="submit"
              className="flex-1 rounded bg-amber-500 px-4 py-3 text-[10px] font-black uppercase tracking-widest text-black hover:bg-amber-400 transition-all shadow-[0_0_20px_rgba(245,158,11,0.3)] active:scale-95"
            >
              Initialize Chat
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
