import { useCallback, useEffect, useRef } from "react"
import { MessageCircle, RefreshCw } from "lucide-react"

import { useMessages } from "./useMessages"
import { useChatSocket } from "./useChatSocket"
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
        refreshMessages
    } = useMessages(conversationId)

    const bottomRef = useRef<HTMLDivElement | null>(null);

    // Receive messages from the websocket

    const handleIncomingMessage = useCallback(
        (message: (typeof messages)[number]) => {
            setMessages((previousMessages) => {
                //prevent duplicate messages

                if (previousMessages.some((item) => item.id == message.id)) {
                    return previousMessages
                }
                return [...previousMessages, message]
            });

        },
        [setMessages]
    )

    // Establish the websocket connection

    const lastMessageId = messages.reduce((lastId, message) => Math.max(lastId, message.id), 0);

    const {
        isConnected,
        connectionError,
        sendMessage,
        readReceipt,
    } = useChatSocket(conversationId, handleIncomingMessage, lastMessageId)

    // send messages through the websocket

    const handleSendMessage = async (content: string) => {
        sendMessage(content)
    };

    // scroll to the latest message

    useEffect(() => {
        bottomRef.current?.scrollIntoView({
            behavior: "smooth",
        });
    }, [messages])

  return (
    <div className="flex h-full flex-col bg-slate-950">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-slate-800 p-5">
            <div>
                <h2 className="font-semibold text-white">Conversation #{conversationId}</h2>

                <p className="mt-1 text-xs text-slate-400">{isConnected ? "Connected": "Connecting..."}</p>
                {
                    readReceipt && Number(readReceipt.conversation_id) === conversationId && (
                        <p className="mt-2 text-xs text-green-400">
                            <span className="font-semibold">
                                {readReceipt.user}
                            </span>
                            {" "}read {readReceipt.count}
                            message(s),
                            {" "}Unread: {readReceipt.unread_count}
                        </p>
                    )
                }
            </div>

            <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-full ${isConnected ? "bg-green-500" : "bg-yellow-500"}`}
            title={isConnected ? "Connected" : "Disconnected"} />

            <button 
                onClick={refreshMessages}
                disabled={loading}
                title = "Refresh Messages"
                className="rounded-lg p-2 text-slate-400 transition  hover:bg-slate-800
                hover:text-white disabled:opacity-50"
            >
                <RefreshCw
                size={18}
                className={loading ? "animate-spin" : ""}
                 />
            </button>
            </div>
        </header>

        {/* connection error */}

        {connectionError && (
            <div className="border-b border-red-500/20 bg-red-500/10
            p-3 text-center text-xs text-red-400">
                {connectionError}
            </div>
        )}

        {/* Messages */}

        <div className="flex-1 overflow-y-auto p-5">
            {loading && messages.length === 0 && (
                <p className="py-10 text-center text-sm text-slate-400">
                    Loading Messages...
                </p>
            )}

            {error && (
                <div className="mx-auto max-w-md rounded=lg bg-red-500/10 p-4 text-center text-sm text-red-400">
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
                    <MessageCircle
                    size={40}
                    className="mb-3 text-slate-600"
                     />
                     <p className="font-medium text-slate-300">
                        No messages yet
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

                        <p className="mt-1 text-xs text-slate-600">{new Date(message.created_at).toLocaleString()}</p>
                    </div>
                ))}
            </div>
            <div ref={bottomRef} />
        </div>

        {/* Message input */}

        <MessageComposer
        onSend={handleSendMessage}
        disabled={!isConnected}
         />
    </div>
  )
}

export default MessagePanel