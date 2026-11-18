import { useCallback, useEffect, useState } from "react";
import { messageService } from "./messageService";
import type { Message, PaginatedMessages } from "./types";

export function useMessages(conversationId: number | null){
    const [messages, setMessages] = useState<Message[]>([])
    const [nextUrl, setNextUrl] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchMessages = useCallback(async () => {
        if (conversationId === null) return;

        try {
            setLoading(true)
            setError(null)

            const data: PaginatedMessages = await messageService.getMessages(conversationId);

            // API returns newest first; display oldest first.

            setMessages([...data.results].reverse());
            setNextUrl(data.next)
        } catch (err) {
            console.error("Failed to fetch messages:", err)
            setError("unable to load messages, Please try again.")
        } finally {
            setLoading(false)
        }
    }, [conversationId])

    useEffect(() => {
        setMessages([])
        setNextUrl(null);
        setError(null);
        if (conversationId !== null) {
            fetchMessages();
        }
    }, [conversationId, fetchMessages])

    return {
        messages,
        setMessages,
        nextUrl,
        loading,
        error,
        refreshMessages: fetchMessages
    }
}