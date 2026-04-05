'use client'

import { useEffect, useState } from 'react'
import { Bell, CheckCircle, XCircle, Send } from 'lucide-react'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'

export function TelegramConfig() {
  const { city } = useCity()
  const [config, setConfig] = useState<{ status: string; chat_id?: string | null; bot_token_masked?: string } | null>(null)
  const [loadingConfig, setLoadingConfig] = useState(true)
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle')

  useEffect(() => {
    let cancelled = false

    api.telegram.config()
      .then((data) => {
        if (!cancelled) setConfig(data)
      })
      .catch(() => {
        if (!cancelled) setConfig(null)
      })
      .finally(() => {
        if (!cancelled) setLoadingConfig(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  async function sendTest() {
    if (!city) return
    setStatus('sending')
    try {
      await api.telegram.test(city.id)
      setStatus('success')
      const nextConfig = await api.telegram.config()
      setConfig(nextConfig)
    } catch {
      setStatus('error')
    } finally {
      setTimeout(() => setStatus('idle'), 3000)
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Bell size={16} className="text-orange-400" />
        <h2 className="text-white font-semibold">Telegram уведомления</h2>
      </div>

      <p className="text-gray-400 text-sm">
        Настройте Telegram-бота для получения алертов о высоких рисках и ежедневных дайджестов.
        Укажите <code className="bg-gray-800 px-1 rounded text-orange-300">TELEGRAM_BOT_TOKEN</code> и{' '}
        <code className="bg-gray-800 px-1 rounded text-orange-300">TELEGRAM_CHAT_ID</code> в настройках сервера.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-gray-800 bg-gray-950 px-3 py-2">
          <div className="text-xs text-gray-500">Bot Token</div>
          <div className="text-sm text-white">{loadingConfig ? 'Загрузка...' : (config?.bot_token_masked ?? 'Не настроен')}</div>
        </div>
        <div className="rounded-lg border border-gray-800 bg-gray-950 px-3 py-2">
          <div className="text-xs text-gray-500">Chat ID</div>
          <div className="text-sm text-white">{loadingConfig ? 'Загрузка...' : (config?.chat_id ?? 'Не настроен')}</div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-400">Статус:</span>
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
          config?.status === 'configured'
            ? 'bg-green-500/10 text-green-400 border border-green-500/20'
            : 'bg-gray-800 text-gray-400 border border-gray-700'
        }`}>
          {config?.status === 'configured' ? 'Connected' : 'Not configured'}
        </span>
      </div>

      <button
        onClick={sendTest}
        disabled={status === 'sending'}
        className="flex items-center gap-2 self-start bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
      >
        {status === 'sending' ? (
          <Send size={14} className="animate-pulse" />
        ) : status === 'success' ? (
          <CheckCircle size={14} className="text-green-400" />
        ) : status === 'error' ? (
          <XCircle size={14} className="text-red-400" />
        ) : (
          <Send size={14} />
        )}
        {status === 'sending' ? 'Отправка...'
          : status === 'success' ? 'Отправлено!'
          : status === 'error' ? 'Ошибка'
          : 'Отправить тест'}
      </button>
    </div>
  )
}
