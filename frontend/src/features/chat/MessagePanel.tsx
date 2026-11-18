import { useEffect, useRef } from "react"
import { MessageCircle, RefreshCw } from "lucide-react"

import { useMessages } from "./useMessages"
import { messageService } from "./messageService"
import MessageComposer from "./MessageComposer"

interface MessagePanelProps {
    conversationId: number;
}

const MessagePanel = ({conversationId}: MessagePanelProps) => {
    const {
        messages,
        setMessages,
        loading,
        error,
        refreshMessages,
    } = useMessages(conversationId);

    const handleSendMessage = async (content: string) => {
        const savedMessage = await messageService.sendMessage(
            conversationId,
            content
        );

        setMessages((previousMessages) => [...previousMessages, savedMessage])
    }

    const bottomRef = useRef<HTMLDivElement | null>(null);

    // Scroll to the latest message when messages change

    useEffect(() => {
        bottomRef.current?.scrollIntoView({behavior: "smooth"});
    }, [messages])
  return (
    <div className="flex h-full flex-col bg-slate-950">
        {/* Conversation header */}

        <header className="flex items-center justify-between border-b border-slate-800 p-5">
            <div>
                <h2 className="font-semibold text-white">
                    Conversation #{conversationId}
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                    Real-time messaging
                </p>
            </div>
            <button
            onClick={refreshMessages}
            disabled={loading}
            title="Refresh messages"
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white disabled:opacity-50"
            >
                <RefreshCw
                size={18}
                className={loading ? "animate-spin" : ""}
                 />
            </button>
        </header>
        {/* Messages */}

        <div className="flex-1 overflow-y-auto p-5">
        {loading && messages.length === 0 && (
            <p className="py-10 text-center text-sm text-slate-400">
                Loading messages...
            </p>
        )}

        {error && (
            <div className="mx-auto max-w-md rounded-lg bg-red-500/10 p-4 text-center text-sm text-red-400">
                <p>{error}</p>
                <button onClick={refreshMessages}
                className="mt-2 font-semibold underline"
                >
                    Try again
                </button>
            </div>
        )}

        {!loading && !error && messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center">
                <MessageCircle size={40} className="mb-3 text-slate-600"/>

                <p className="font-medium text-slate-300">
                    No message yet
                </p>
                <p className="mt-1 text-sm text-slate-500">
                    Messages will appear here.
                </p>
            </div>
        )}

        <div className="space-y-4">
            {messages.map((message) => (
                <div key={message.id} className="max-w-2xl">
                    <div className="mb-1 text-xs text-slate-500">
                    {message.sender}
                    </div>
                    <div className="inline-block rounded-2xl rounded-tl-sm bg-slate-800 px-4 py-3 text-sm text-slate-200">
                        {message.content}
                    </div>
                    <p className="mt-1 text-xs text-slate-600">
                    {new Date(message.created_at).toLocaleString()}
                    </p>
                </div>
            ))}

        </div>
        <div ref={bottomRef}/>
        <MessageComposer onSend={handleSendMessage}/>
        </div>
    </div>
  )
}

export default MessagePanel