import {useState, type FormEvent} from "react";
import { Send } from "lucide-react";

interface MessageComposerProps {
    onSend: (content: string) => Promise<void>;
    disabled?: boolean;
}

function MessageComposer({
    onSend,
    disabled=false
}: MessageComposerProps) {
    const [content, setContent] = useState("");
    const [sending, setSending] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleSubmit = async (event:FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        const trimmedContent = content.trim();
        if (!trimmedContent || sending || disabled) return;

        try {
            setSending(true);
            await onSend(trimmedContent);
            setContent("")
        } catch (error) {
            console.error(
                "Failed to send message:", error
            )
            setError("Message could not be sent. Please try again")
        }finally{
            setSending(false)
        }
    }

    return(
        <form onSubmit={handleSubmit}
        className="flex items-center gap-3 border-t border-slate-800 bg-slate-900 p-4"
        >
            <input 
            type="text"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Type your message..."
            maxLength={5000}
            disabled={disabled || sending}
            className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-800
            px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500 disabled:opacity-50"
            />
            <button
            type="submit"
            disabled={!content.trim() || sending || disabled}
            className="flex items-center justify-center rounded-xl bg-blue-600 p-3 text-white transition hover:bg-blue-500
            disabled:cursor-not-allowed disabled:opacity-40"

            title="Send message"
            >
                <Send size={18}/>
            </button>
            {error && (
                <p className="absolute bottom-20 left-4 text-xs text-red-400">
                    {error}
                </p>
            )}
        </form>
    )
}

export default MessageComposer