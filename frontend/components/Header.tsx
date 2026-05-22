'use client'

interface HeaderProps {
  onMemoryToggle?: () => void
  memoryOpen?: boolean
  onSettingsToggle?: () => void
}

export default function Header({ onMemoryToggle, memoryOpen, onSettingsToggle }: HeaderProps) {
  return (
    <header className="bg-gradient-to-r from-blue-900 via-purple-900 to-blue-900 border-b-2 border-cyan-400 py-4 px-6 shadow-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="portal-effect w-8 h-8 border-2 border-green-400 rounded-full"></div>
          <div>
            <h1 className="neon-text text-2xl">EthioClaw</h1>
            <p className="text-cyan-300 text-sm">Rick and Morty AI Agent</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onSettingsToggle}
            className="hidden lg:block px-4 py-2 rounded-lg border-2 border-purple-400 text-purple-400 bg-purple-400/10 hover:bg-purple-400/20 hover:border-purple-300 transition-all duration-200 font-bold text-sm"
            title="Settings"
          >
            ⚙ Settings
          </button>
          <button
            onClick={onMemoryToggle}
            className={`hidden lg:block px-4 py-2 rounded-lg border-2 transition-all duration-200 font-bold text-sm ${
              memoryOpen
                ? 'border-red-400 text-red-400 bg-red-400/10 hover:bg-red-400/20'
                : 'border-cyan-400 text-cyan-400 bg-cyan-400/10 hover:bg-cyan-400/20 hover:border-green-400 hover:text-green-400'
            }`}
          >
            {memoryOpen ? '✕ Close Memory' : '📚 Memory Bank'}
          </button>
          <div className="text-right">
            <p className="text-cyan-300 text-sm">Status: Online</p>
            <p className="text-green-400 text-xs animate-pulse">⚡ Ready to assist</p>
          </div>
        </div>
      </div>
    </header>
  )
}
