import { useState } from "react";
import ConversationList from "../features/conversations/ConversationList";
import { MessageCircle } from "lucide-react";
import MessagePanel from "../features/chat/MessagePanel";

const ChatPage = () => {
    const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null)

  return (
    <main className="flex hscreen overflow-hidden bg-slate-950">
        {/* Left sidebar */}

        <section className="h-full w-full border-r border-slate-800 md:w-80 lg:w-96">
            <ConversationList 
            selectedConversationId={selectedConversationId}
            onSelectConversation={setSelectedConversationId}
            />
        </section>

        {/* Main Chat Area */}

        <section className={`h-full flex-1 ${selectedConversationId !== null ? "block" : "hidden"}`}>
            {selectedConversationId !== null ? (
                <MessagePanel conversationId={selectedConversationId}/>
            ) : (
                <div className="text-center">
                    <MessageCircle size={40} className="mx-auto mb-4 text-blue-400"/>
                    <h2 className="text-lg font-semibold text-white">Conversation #{selectedConversationId}</h2>
                    <p className="mt-2 text-sm text-slate-400">Your Messages will appear here.</p>
                </div>
            )}

        </section>

    </main>
  )
}

export default ChatPage