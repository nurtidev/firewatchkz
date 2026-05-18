import { ChatPanel } from '@/components/ai/ChatPanel'

export default function ChatPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div>
        <h1 className="text-white font-semibold text-xl">ИИ-аналитик</h1>
        <p className="text-gray-400 text-sm mt-1">
          Задавайте вопросы естественным языком — система отвечает по данным ДЧС вашего города.
          Подходит для быстрого среза перед совещанием.
        </p>
      </div>
      <ChatPanel fullHeight />
    </div>
  )
}
