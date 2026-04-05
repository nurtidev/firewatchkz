import { RequireAuth } from '@/context/AuthContext'
import { TelegramConfig } from '@/components/telegram/TelegramConfig'

export default function AlertsPage() {
  return (
    <RequireAuth roles={['admin']}>
      <div className="max-w-xl">
        <h1 className="text-white font-semibold text-lg mb-4">Уведомления</h1>
        <TelegramConfig />
      </div>
    </RequireAuth>
  )
}
