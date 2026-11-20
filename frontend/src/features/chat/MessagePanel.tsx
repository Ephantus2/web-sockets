import { useCallback, useEffect, useRef, useState} from "react"
import { MessageCircle, RefreshCw, Search, X,  ArrowLeft} from "lucide-react"

import { useMessages } from "./useMessages"
import { useChatSocket } from "./useChatSocket"
import MessageComposer from "./MessageComposer"
import { messageService } from "./messageService"
import type { Message } from "./types"

interface MessagePanelProps {
    conversationId: number;
    onBack: () => void;
}

const MessagePanel = ({conversationId, onBack}: MessagePanelProps) => {
    const {
        messages,
        setMessages,
        loading,
        loadingOlder,
        hasMore,
        error,
        refreshMessages,
        loadOlderMessages,
    } = useMessages(conversationId)

    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<Message[]>([])
    const [searching, setSearching] = useState(false)
    const [searchError, setSearchError] = useState<string | null>(null)
    const [showSearch, setShowSearch] = useState(false)
    const [hasSearched, setHasSearched] = useState(false)

    const bottomRef = useRef<HTMLDivElement | null>(null);

    const messagesContainerRef = useRef<HTMLDivElement | null>(null);
    const previousScrollHeightRef = useRef<number | null>(null);

    const handleSearch = async () => {
        const query = searchQuery.trim();

        if (!query) return;

        try {
            setSearching(true)
            setSearchError(null);

            const results = await messageService.searchMessages(
                conversationId,
                query
            );

            setSearchResults(results)
            setHasSearched(true)
        } catch (error) {
            console.error("Message search failed:", error);
            setSearchError("Unable to search messages. Please try again.");
        } finally {
            setSearching(false)
        }
    }


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
        markAsRead,
        sendTyping,
        typingUsers,
    } = useChatSocket(conversationId, handleIncomingMessage, lastMessageId)

    useEffect(() => {
        if (isConnected && document.visibilityState === "visible"){
            markAsRead();
        }
    }, [isConnected, messages, markAsRead])

    useEffect(() => {
        const handleVisibilityChange = () => {
            if (
                document.visibilityState === "visible" && isConnected
            ) {
                markAsRead();
            }
        }

        document.addEventListener(
            "visibilitychange",
            handleVisibilityChange
        );

        return () => {
            document.removeEventListener(
                "visibilitychange",
                handleVisibilityChange
            )
        }
    }, [isConnected, markAsRead])

    // send messages through the websocket

    const handleSendMessage = async (content: string) => {
        sendMessage(content)
    };

    // scroll to the latest message

    useEffect(() => {
        const container = messagesContainerRef.current;
        if (!container) return;

        const previousHeight = previousScrollHeightRef.current;

        if (previousHeight !== null) {
            const heightDifference = container.scrollHeight - previousHeight;
            container.scrollTop += heightDifference;
            previousScrollHeightRef.current = null;
            return;
        }
        bottomRef.current?.scrollIntoView({
            behavior: "smooth",
        });
    }, [messages])

  return (
    <div className="flex h-full flex-col bg-slate-950">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-slate-800 p-5">
            <div className="flex min-w-0 items-center gap-3">
                <button
                onClick={onBack}
                className="shrink-0 rounded-lg p-2 text-slate-400
                hover:bg-slate-800 hover:text-white md:hidden"
                >
                    <ArrowLeft size={20} />
                </button>
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
            </div>

            <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-full ${isConnected ? "bg-green-500" : "bg-yellow-500"}`}
            title={isConnected ? "Connected" : "Disconnected"} />

            <button
            onClick={
                () => {
                    setShowSearch((previous) => !previous)
                    setSearchQuery("");
                    setSearchResults([])
                    setSearchError(null);
                }
            }
            title="Search messages"
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white"
            >
                <Search size={18} />
            </button>

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

        {
            showSearch && (
                <div className="border-b border-slate-800 bg-slate-900 p-4">
                    <form
                    onSubmit={(event) => {
                        event.preventDefault()
                        handleSearch();
                    }}
                    className="flex gap-2"
                    >
                        <input
                        type="text"
                        value={searchQuery}
                        onChange={(event) => setSearchQuery(event.target.value)}
                        placeholder="Search messages..."
                        className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-800
                        px-4 py-2 text-sm text-white oultline-none focus:border-blue-500"
                         />
                        <button
                        type="submit"
                        disabled={searching || !searchQuery.trim()}
                        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                        >
                            {searching ? "Searching...": "Search"}
                        </button>
                        <button
                        type="button"
                        onClick={() => {
                            setShowSearch(false);
                            setSearchQuery("")
                            setSearchResults([])
                            setSearchError(null)
                        }}
                        title="Close search"
                        className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
                        >
                            <X size={18} />
                        </button>
                    </form>

                </div>
            )
        }

        {/* connection error */}

        {connectionError && (
            <div className="border-b border-red-500/20 bg-red-500/10
            p-3 text-center text-xs text-red-400">
                {connectionError}
            </div>
        )}

        {/* Search results */}

        {
            showSearch && hasSearched && (
                <div className="border-b border-slate-800 bg-slate-900 p-4">
                    <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-white">
                            Search Results
                        </h3>
                        <span className="text-xs text-slate-400">
                            {searchResults.length} found
                        </span>
                    </div>
                    {searchError && (
                        <p className="text-xs text-slate-400">
                            {searchError}
                        </p>
                    )}
                    <div className="max-h-64 space-y-3 overflow-y-auto">
                        {searchResults.map((message) => (
                            <div 
                            key={message.id}
                            className="rounded-lg border border-slate-700 bg-slate-800 p-3"
                            >
                                <p className="mb-1 text-xs font-semibold text-blue-400">
                                    {message.sender}
                                </p>
                                <p className="text-sm text-slate-200">
                                    {message.content}
                                </p>
                                <p className="mt-2 text-xs text-slate-500">
                                    {new Date(message.created_at).toLocaleString()}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )
        }

        {/* Messages */}

        <div ref={messagesContainerRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:p-5">
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
                {hasMore && (
                    <div className="flex justify-center pb-4">
                        <button
                        onClick={() => {
                            if (messagesContainerRef.current) {
                                previousScrollHeightRef.current = messagesContainerRef.current.scrollHeight;
                            }

                            loadOlderMessages();
                        }}
                        disabled={loadingOlder}
                        className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-300 transition hover:bg-slate-700 disabled:opacity-50"
                        >
                            {loadingOlder ? "Loading older messages..." : "Load older messages"}
                        </button>
                    </div>
                )}
                {messages.map((message) => (
                    <div key={message.id} className="max-w-[90%] sm:max-w-2xl">
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
        {/* Typing indicator */}

        {typingUsers.length > 0 && (
            <div className="border-t border-slate-800 px-5 py-2">
                <p className="text-xs italic text-blue-400">
                    {typingUsers.length === 1 ? `${typingUsers[0]} is typing...` 
                    : typingUsers.length === 2 ? `${typingUsers[0]} and ${typingUsers[1]} are typing...`
                : `${typingUsers.length} people are typing` }
                </p>
            </div>
        )}

        {/* Message input */}

        <MessageComposer
        onSend={handleSendMessage}
        onTyping={sendTyping}
        disabled={!isConnected}
         />
    </div>
  )
}

export default MessagePanel