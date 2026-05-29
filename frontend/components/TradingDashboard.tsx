'use client'

import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Wallet, Trophy, LineChart, BarChart } from 'lucide-react'

interface TradingDashboardProps {
  userId: string
  sessionId: string
  backendUrl: string
  onUpdateBalance?: (newBalance: number) => void
}

interface TradingStats {
  user_id: string
  session_id: string
  balance: number
  todays_pl: number
  win_rate: number
  open_trades: number
  profit_factor: number
  average_rr: string
  best_pair: string
  best_session: string
  best_market_condition: string
  recent_trades: Array<{
    id: string
    signal_id: string
    status: string
    pair: string | null
    outcome: string | null
    pnl: number
    opened_at: string
    closed_at: string | null
  }>
}

export default function TradingDashboard({ userId, sessionId, backendUrl, onUpdateBalance }: TradingDashboardProps) {
  const [stats, setStats] = useState<TradingStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditingBalance, setIsEditingBalance] = useState(false)
  const [editBalanceValue, setEditBalanceValue] = useState('')

  const fetchDashboard = async () => {
    if (!sessionId || sessionId === 'default') return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${backendUrl}/trading/dashboard/${sessionId}`)
      if (!res.ok) {
        throw new Error(`Error fetching dashboard: ${res.statusText}`)
      }
      const data: TradingStats = await res.json()
      setStats(data)
    } catch (err: any) {
      setError(err.message)
      console.error('Failed to fetch trading dashboard:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleUpdateBalance = async () => {
    const val = parseFloat(editBalanceValue)
    if (isNaN(val)) return

    try {
      const res = await fetch(`${backendUrl}/trading/balance/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, new_balance: val }),
      })
      if (res.ok) {
        setIsEditingBalance(false)
        fetchDashboard()
        if (onUpdateBalance) onUpdateBalance(val)
      }
    } catch (err) {
      console.error('Failed to update balance:', err)
    }
  }

  useEffect(() => {
    fetchDashboard()
    const interval = setInterval(fetchDashboard, 15000) // Refresh every 15 seconds
    return () => clearInterval(interval)
  }, [sessionId, backendUrl])

  if (isLoading && !stats) {
    return (
      <div className="p-6 text-center text-muted-foreground animate-pulse font-mono">
        Loading Trading Dashboard...
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 text-center text-rose-500 font-mono">
        Error: {error}
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="p-6 text-center text-muted-foreground font-mono">
        Initialize trading to see dashboard data.
      </div>
    )
  }

  const pnlColorClass = stats.todays_pl >= 0 ? 'text-emerald-500' : 'text-rose-500'

  return (
    <div className="p-6 space-y-8 font-mono text-xs">
      {/* Overview Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="relative group">
          <StatCard title="Current Balance" value={`$${stats.balance.toFixed(2)}`} icon={<Wallet className="size-4" />} />
          <button 
            onClick={() => {
              setEditBalanceValue(stats.balance.toString())
              setIsEditingBalance(true)
            }}
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] text-primary hover:underline font-black uppercase"
          >
            Edit
          </button>
        </div>
        <StatCard title="Today's P/L" value={`${stats.todays_pl >= 0 ? '+' : ''}$${stats.todays_pl.toFixed(2)}`} valueClass={pnlColorClass} icon={stats.todays_pl >= 0 ? <TrendingUp className="size-4" /> : <TrendingDown className="size-4" />} />
        <StatCard title="Win Rate" value={`${stats.win_rate.toFixed(1)}%`} icon={<Trophy className="size-4" />} />
        <StatCard title="Open Trades" value={stats.open_trades.toString()} icon={<LineChart className="size-4" />} />
      </div>

      {isEditingBalance && (
        <div className="bg-primary/5 border-2 border-primary/20 rounded-lg p-4 space-y-3 animate-in fade-in slide-in-from-top-2">
          <p className="text-[10px] font-black uppercase text-primary tracking-widest">Update Session Balance</p>
          <div className="flex gap-2">
            <input 
              type="number"
              value={editBalanceValue}
              onChange={(e) => setEditBalanceValue(e.target.value)}
              className="flex-1 bg-background border border-border rounded px-3 py-2 text-xs focus:outline-none focus:border-primary"
              placeholder="Enter new balance..."
            />
            <button 
              onClick={handleUpdateBalance}
              className="bg-primary text-black px-4 py-2 rounded text-[10px] font-black uppercase"
            >
              Update
            </button>
            <button 
              onClick={() => setIsEditingBalance(false)}
              className="bg-muted text-muted-foreground px-4 py-2 rounded text-[10px] font-black uppercase"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Performance Metrics */}
      <div className="bg-card border-2 border-border/50 rounded-lg p-4 space-y-4">
        <h3 className="text-[10px] uppercase tracking-[0.2em] text-amber-500 font-black mb-4">Performance Metrics</h3>
        <StatRow title="Profit Factor" value={stats.profit_factor.toFixed(2)} />
        <StatRow title="Average R:R" value={stats.average_rr} />
        <StatRow title="Best Performing Pair" value={stats.best_pair || 'N/A'} />
        <StatRow title="Best Session" value={stats.best_session || 'N/A'} />
        <StatRow title="Best Market Condition" value={stats.best_market_condition || 'N/A'} />
      </div>

      {/* Recent Trades */}
      <div className="bg-card border-2 border-border/50 rounded-lg p-4 space-y-4">
        <h3 className="text-[10px] uppercase tracking-[0.2em] text-cyan-500 font-black mb-4">Recent Trades</h3>
        {stats.recent_trades.length === 0 ? (
          <p className="text-muted-foreground text-center">No recent trades.</p>
        ) : (
          <div className="space-y-3">
            {stats.recent_trades.map((trade) => (
              <div key={trade.id} className="flex justify-between items-center text-[10px] border-b border-border/10 pb-2">
                <div className="flex flex-col">
                  <span className="text-muted-foreground">{new Date(trade.opened_at).toLocaleDateString()}</span>
                  <span className={`font-bold ${trade.status === 'OPEN' ? 'text-amber-500' : 'text-muted-foreground'}`}>
                    {trade.status}
                  </span>
                </div>
                <span className="flex-1 text-center font-bold px-2">
                  {trade.signal_id.slice(0, 6)} :: {trade.pair || '---'}
                </span>
                <span className={`${trade.pnl >= 0 ? 'text-emerald-500' : 'text-rose-500'} font-black text-xs`}>
                  {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: string
  valueClass?: string
  icon: React.ReactNode
}

const StatCard = ({ title, value, valueClass = 'text-foreground', icon }: StatCardProps) => (
  <div className="bg-card border-2 border-border/50 rounded-lg p-4 flex items-center space-x-3">
    <div className="p-2 bg-muted/20 rounded-full text-primary">
      {icon}
    </div>
    <div>
      <p className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">{title}</p>
      <p className={`text-lg font-black ${valueClass}`}>{value}</p>
    </div>
  </div>
)

interface StatRowProps {
  title: string
  value: string
}

const StatRow = ({ title, value }: StatRowProps) => (
  <div className="flex justify-between items-center text-xs border-b border-border/30 pb-2 last:border-b-0 last:pb-0">
    <span className="text-muted-foreground">{title}:</span>
    <span className="text-foreground font-black">{value}</span>
  </div>
)
