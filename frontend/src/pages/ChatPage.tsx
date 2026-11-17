import { useState } from "react";
import ConversationList from "../features/conversations/ConversationList";
import { MessageCircle } from "lucide-react";


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

        <section className="hidden flex-1 items-center justify-center md:flex">
            {selectedConversationId == null ? (
                <div className="test-center">
                    <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-slate-800">
                        <MessageCircle size={38}  className="text-blue-400"/>
                    </div>
                    <h2 className="text-xl font-semibold text-white">
                        Welcome to RealTime Chat
                    </h2>
                    <p className="mt-2 text-sm text-slate-400">
                        Select a conversation to start messaging
                    </p>
                </div>
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