import { useState } from "react"
import { Bell, CheckCheck, X } from "lucide-react"
import { useNotifications } from "./useNotifications"

interface NotificationBellProps {
  onOpenConversation: (conversationId: number) => void
}

const NotificationBell = ({onOpenConversation}: NotificationBellProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const {
    notifications,
    loading,
    error,
    unreadCount,
    markAsRead,
    markAllAsRead,
    isConnected,
    connectionError,
  } = useNotifications();

  return (
    <div className="relative">
      {/* Notification bell */}
      <button onClick={() => setIsOpen((previous) => !previous)}
      className="relative rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
      aria-label="Notifications"
        >
        <Bell size={22} />
        <span className={`absolute bottom-1 right-1 h-2.5 w-2.5
          rounded-full border-2 border-slate-950 ${
            isConnected ? "bg-green-500" : "bg-red-500"
          }`} 
          title={isConnected ? "Live notifications connected" : "Disconnected"}
          />
        {unreadCount > 0 && (
          <span
          className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center
          rounded-full bg-red-500 px-1 text-xs font-semibold text-white"
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      { /* Notification dropdown */}
      {isOpen && (
        <div className="absolute right-0 top-12 z-50 w-80 overflow-hidden rounded-xl
        border border-slate-700 bg-slate-900 shadow-xl sm:w-96">
          {/* Header */}
          <div className="flex items-center justify-between border-b borde-slate-800 p-4">
            <div>

            
            <h2 className="font-semibold text-white">
              Notifications
            </h2>
            <p className="text-xs text-slate-400">
              {unreadCount} unread notifications
            </p>
            </div>
          
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <button
              onClick={markAllAsRead}
              title="Mark all as read"
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-blue-400"
              >
                <CheckCheck size={18} />
              </button>
            )}
            <button
            onClick={() => setIsOpen(false)}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Close notifications"
            >
              <X size={18}/>
            </button>
          </div>
        </div>

        {connectionError && (
          <p className="border-b border-slate-800 px-4 py-2 text-xs text-red-400">
            {connectionError}
          </p>
        )}
        {/* Notification list */}
        <div className="max-h-96 overflow-y-auto">
            {loading && (
              <p className="p-6 text-center text-sm text-slate-400">Loading notifications...</p>
              )}
            {error && (
              <p className="p-6 text-center text-sm text-red-400">{error}</p>
            )}

            {
              !loading && !error && notifications.length === 0 && (
                <p className="p-6 text-center text-sm text-slate-400">No notifications yet.</p>
              )
            }
            {
              !loading && notifications.map((notification) => (
                <button
                key={notification.id}
                onClick={() => {
                  if(!notification.is_read) {
                    void markAsRead(notification.id)
                  }
                  if (notification.conversation !== null){
                    onOpenConversation(notification.conversation)
                    setIsOpen(false)
                  }
                }}
                className={`w-full border-b border-slate-800 p-4 text-left
                transition hover:bg-slate-800 ${!notification.is_read ? "bg-slate-800/50" : ""}`}
                >
                  <div className="flex items-start gap-3">
                    {!notification.is_read && (
                      <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-white">{notification.title}</p>
                      <p className="mt-2 text-xs text-slate-500">{notification.message}</p>
                      <p className="mt-2 text-xs text-slate-500">{new Date(notification.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                </button>
              ))
            }
            </div>
        </div>
      )}
    </div>
  )
}

export default NotificationBell