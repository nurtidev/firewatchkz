'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, ShieldCheck, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'
import { useCity } from '@/context/CityContext'
import { api } from '@/lib/api'
import type { ChatMessage } from '@/lib/types'

const SUGGESTED = [
  'Покажи здания с высоким риском в Сарыарка',
  'Какой район наиболее опасен сейчас?',
  'Сравни этот год с прошлым по ущербу',
  'Где находятся слепые зоны прибытия?',
]

export interface ChatPanelProps {
  /** Сделать панель растягивающейся по высоте родителя. По умолчанию — фикс 520px (виджет). */
  fullHeight?: boolean
}

export function ChatPanel({ fullHeight = false }: ChatPanelProps = {}) {
  const { city } = useCity()
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, loading])

  useEffect(() => {
    inputRef.current?.focus()
  }, [city])

  async function send(text: string) {
    if (!city || !text.trim() || loading) return
    const userMsg: ChatMessage = { role: 'user', content: text.trim() }
    setHistory((h) => [...h, userMsg])
    setInput('')
    setLoading(true)
    try {
      const { reply } = await api.chat.send(city.id, text.trim(), history)
      setHistory((h) => [...h, { role: 'assistant', content: reply }])
    } catch {
      setHistory((h) => [
        ...h,
        { role: 'assistant', content: 'Ошибка соединения с сервером.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  const heightClass = fullHeight ? 'h-[calc(100vh-180px)]' : 'h-[520px]'

  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl flex flex-col ${heightClass}`}>
      <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-3">
        <Bot size={18} className="text-orange-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <h2 className="text-white font-semibold text-sm">ИИ-аналитик</h2>
          <p className="text-gray-500 text-xs flex items-center gap-1 mt-0.5">
            <ShieldCheck size={10} className="shrink-0" />
            Работает только с данными ДЧС — без галлюцинаций
          </p>
        </div>
        {history.length > 0 && (
          <button
            type="button"
            onClick={() => setHistory([])}
            className="text-gray-500 hover:text-white text-xs flex items-center gap-1 shrink-0 transition-colors"
            title="Очистить переписку"
          >
            <RefreshCw size={12} />
            Сброс
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {history.length === 0 && (
          <div className="space-y-3 pt-2">
            <p className="text-gray-500 text-xs text-center">
              Спросите своими словами — например, по риску или причинам пожаров.
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-xs bg-gray-800 text-gray-300 hover:bg-gray-700 px-3 py-1.5 rounded-full transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {history.map((msg, i) => (
          <div
            key={i}
            className={clsx('flex gap-2', msg.role === 'user' ? 'justify-end' : 'justify-start')}
          >
            {msg.role === 'assistant' && (
              <Bot size={16} className="text-orange-400 mt-1 shrink-0" />
            )}
            <div
              className={clsx(
                'max-w-[85%] text-sm px-3 py-2 rounded-2xl leading-relaxed whitespace-pre-wrap',
                msg.role === 'user'
                  ? 'bg-orange-500 text-white rounded-tr-sm'
                  : 'bg-gray-800 text-gray-200 rounded-tl-sm'
              )}
            >
              {msg.content}
            </div>
            {msg.role === 'user' && (
              <User size={16} className="text-gray-400 mt-1 shrink-0" />
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-2">
            <Bot size={16} className="text-orange-400 mt-1 shrink-0" />
            <div className="bg-gray-800 px-3 py-2 rounded-2xl rounded-tl-sm flex gap-1 items-center">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
        className="p-3 border-t border-gray-800 flex gap-2"
      >
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Введите вопрос..."
          className="flex-1 bg-gray-800 text-white text-sm rounded-lg px-3 py-2 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-orange-500"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="bg-orange-500 hover:bg-orange-600 disabled:opacity-40 text-white rounded-lg p-2 transition-colors"
        >
          <Send size={15} />
        </button>
      </form>
    </div>
  )
}
