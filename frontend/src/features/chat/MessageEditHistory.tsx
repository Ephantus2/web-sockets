import { useEffect, useState } from "react";
import { X, History, Clock } from "lucide-react";
import { messageService } from "./messageService";
import type { MessageEditHistory as MessageEditHistoryType } from "./types";

interface MessageEditHistoryProps {
    conversationId: number;
    messageId: number;
    onClose: () => void
}

const MessageEditHistory = ({
    conversationId,
    messageId,
    onClose
}: MessageEditHistoryProps) => {
    const [history, setHistory] = useState<MessageEditHistoryType[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                setLoading(true)
                setError(null)

                const data = await messageService.getMessageEditHistory(
                    conversationId,
                    messageId
                )

                setHistory(data)
            } catch (err) {
                console.error(
                    "Failed to fetch message history:", err
                )

                setError("Unable to load edit history.")
            } finally {
                setLoading(false)
            }
        }

        fetchHistory();
    }, [conversationId, messageId])

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-xl">
                <div className="mb-5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <History size={20} className="text-blue-400"/>
                        <h2 className="text-lg font-semi-bold text-white">
                            Message edit history
                        </h2>
                    </div>
                    <button 
                    onClick={onClose}
                    className="rounded-lg p-2 text-slate-400 hover:bg-slate-800
                    hover:text-white"
                    >
                        <X size={20}/>
                    </button>
                </div>
                {loading ? (
                    <p className="py-6 text-center text-slate-400">
                        Loading history...
                    </p>) : error ? (
                        <p className="py-6 text-center text-red-400">
                            {error}
                        </p>) : history.length === 0 ? (
                            <p className="py-6 text-center text-slate-600">
                                No previous versions found.
                            </p>
                            ) : (
                                <div className="max-h-96 space-y-4 overflow-y-auto">
                                    {history.map((entry) =>(
                                        <div
                                        key={entry.id}
                                        className="rounded-lg border border-slate-700 bg-slate-800/60 p-4"
                                        >
                                            <p className="whitespace-pre-wrap wrap-break-word text-sm text-slate-200">
                                                {entry.previous_content}
                                            </p>
                                            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                                                <span>
                                                    Edited by {entry.edited_by || "Unknown"}
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <Clock size={12}/>
                                                    {new Date(entry.edited_at).toLocaleString()}
                                                </span>
                                            </div>

                                        </div>
                                    ))}
                                </div>
                            )}
            </div>
        </div>
    )
}

export default MessageEditHistory
