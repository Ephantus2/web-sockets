import { useState } from "react";
import ConversationList from "../features/conversations/ConversationList";
import { MessageCircle } from "lucide-react";
import MessagePanel from "../features/chat/MessagePanel";
import NotificationBell from "../features/notifications/NotificationBell";

const ChatPage = () => {
    const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null)

 return (
    <main className="flex h-screen flex-col overflow-hidden bg-slate-950">
        {/* Application Header */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-6">
            <div className="flex items-center gap-3">
                <MessageCircle className="text-blue-400" size={25} />
                <h1 className="text-lg font-bold text-white">TealTime Chat</h1>
            </div>
            <NotificationBell onOpenConversation={setSelectedConversationId}/>
        </header>

        {/* Main Application Layout */}
        <div className="flex min-h-0 flex-1 overflow-hidden">
            {/* Left Sidebar */}
            <section className={`h-full w-full border-r border-slate-800 md:w-80 lg:w-96 ${selectedConversationId !== null ? "hidden" : "block"}`}>
                <ConversationList selectedConversationId={selectedConversationId} onSelectConversation={setSelectedConversationId} />
            </section>

            { /* Main Chat Area */}
            <section
            className={`h-full min-w-0 flex-1 ${selectedConversationId !== null ? "block" : "hidden"} md:block`}
            >
                {selectedConversationId !== null ? (
                    <MessagePanel conversationId={selectedConversationId} onBack={() => setSelectedConversationId(null)} /> ) : (
                        <div className="flex h-full items-center justify-center text-center">
                            <div>
                                <MessageCircle size={40} className="mx-auto mb-4 text-blue-400" />
                                <h2 className="text-lg font-semibold text-white">
                                    Welcome to RealTime chat
                                </h2>
                                <p className="mt-2 text-sm text-slate-400">
                                    Select a conversation to start messaging.
                                </p>
                            </div>
                        </div>
                    )}

            </section>
        </div>
    </main>
 )
}

export default ChatPage