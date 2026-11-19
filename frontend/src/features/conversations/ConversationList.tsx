import { useConversations } from "./useConversations";
import { MessageCircle, RefreshCw, Users } from "lucide-react";
import { conversationService } from "./conversationService";
import { useCallback, useEffect, useState } from "react";
import type { UnreadConversation } from "./types";

interface ConversationListProps {
  selectedConversationId: number | null;
  onSelectConversation: (id: number) => void;
}

const ConversationList = ({
  selectedConversationId,
  onSelectConversation,
}: ConversationListProps) => {
  const { conversations, loading, error, refreshConversations } =
    useConversations();

  const [unreadCounts, setUnreadCounts] = useState<UnreadConversation[]>([]);

  const fetchUnreadCounts = useCallback(async () => {
    try {
      const data = await conversationService.getUnreadCounts();
      setUnreadCounts(data);
    } catch (error) {
      console.error("Failed to fetch unread counts:", error);
    }
  }, []);

  useEffect(() => {
    fetchUnreadCounts();

    const interval = setInterval(fetchUnreadCounts, 15000);
    return () => clearInterval(interval);
  }, [fetchUnreadCounts]);
  return (
    <aside className="flex, h-full flex-col border-r border-slate-800 bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 p-5">
        <div>
          <h2 className="text-xl font-bold text-white">Messages</h2>
          <p className="mt-1 text-xs text-slate-400">Your conversations</p>
        </div>

        <button
          onClick={refreshConversations}
          disabled={loading}
          title="Refresh conversations"
          className="rounded-lg text-slate-400 transition hover:bg-slate-800 hover:text-white disabled:opacity-50"
        >
          <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
        </button>
      </div>
      {/* conversation list */}

      <div className="flex-1 overflw-y-auto p-3">
        {loading && conversations.length === 0 && (
          <div className="py-10 text-center text-sm text-slate-400">
            Loading conversations...
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
            {error}
            <button
              onClick={refreshConversations}
              className="mt-2 block font-semibold text-red-300 underline"
            >
              Try again
            </button>
          </div>
        )}
        {!loading && !error && conversations.length === 0 && (
          <div className="flex flex-col items-center py-12 text-center">
            <MessageCircle size={35} className="mb-3 text-slate-600" />
            <p className="text-sm font-medium text-slate-300">
              No conversations yet
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Your conversations will appear here
            </p>
          </div>
        )}

        <div className="space-y-2">
          {conversations.map((conversation) => {
            const unreadCount =
              unreadCounts.find((item) => item.id === conversation.id)
                ?.unread_count ?? 0;
            return (
              <button
                key={conversation.id}
                onClick={() => onSelectConversation(conversation.id)}
                className={`flex w-full items-center gap-3 rounded-xl p-3 text-left transition ${
                  selectedConversationId === conversation.id
                    ? "bg-blue-600/20 ring-1 ring-blue-500/30"
                    : "hover:bg-slate-800"
                }`}
              >
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-700">
                  <Users size={20} className="text-slate-300" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semi-bold text-white">
                    {conversation.name || `Conversation ${conversation.id}`}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {conversation.participants.length} participants
                  </p>
                </div>
                {unreadCount > 0 && (
                    <span className="flex h-6 min-w-6 shrink-0 items-center
                    justify-center rounded-full bg-blue-600 px-2 text-xs font-bold text-white">
                        {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
};

export default ConversationList;
