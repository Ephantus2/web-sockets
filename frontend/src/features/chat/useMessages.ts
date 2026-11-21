import { useCallback, useEffect, useState } from "react";
import { messageService } from "./messageService";
import type { Message, PaginatedMessages, MessageReaction } from "./types";

export function useMessages(conversationId: number | null){
    const [messages, setMessages] = useState<Message[]>([])
    const [nextUrl, setNextUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(false)
    const [loadingOlder, setLoadingOlder] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchMessages = useCallback(async () => {
        if (conversationId === null) return;

        try {
            setLoading(true)
            setError(null);
            const data: PaginatedMessages = await messageService.getMessages(conversationId);
            // The backend returns newest first.
            // Reverse the results for chronological display

            setMessages([...data.results].reverse());
            setNextUrl(data.next)
        } catch (err){
            console.error("Failed to fetch messages:", err);
            setError("Unable to load message. Please try again")
        }finally {
            setLoading(false)
        }
    }, [conversationId])

    const loadOlderMessages = useCallback(async () => {
        if (!nextUrl || loadingOlder) return;

        try{
            setLoadingOlder(true);
            const data = await messageService.getOlderMessages(nextUrl);

            // reverse this page into chronological order
            const olderMessages = [...data.results].reverse()

            setMessages((currentMessages) => {
                const existingIds = new Set(
                    currentMessages.map((message) => message.id)
                )
                const uniqueOlderMessages = olderMessages.filter(
                    (message) => !existingIds.has(message.id)
                )

                return [...uniqueOlderMessages, ...currentMessages]
            })
            setNextUrl(data.next)
        } catch (err) {
            console.error("Failed to load older messages:", err)
            setError("Unable to load older messages. Please try again.")
        } finally {
            setLoadingOlder(false)
        }
    }, [nextUrl, loadingOlder]);
const updateMessage = useCallback((updatedMessage: Message) => {
    setMessages((currentMessages) => currentMessages.map((message) => message.id === updatedMessage.id ? updatedMessage : message ))
}, [])

const  markMessageDeleted = useCallback((messageId: number) => {
    setMessages((currentMessages) => currentMessages.map((message) => message.id === messageId ? {
        ...message,
        is_deleted: true,
        deleted_at: new Date().toISOString()
    }: message))
}, [])

const updateMessageReactions = useCallback((messageId: number, reactions: MessageReaction[]) => {
    setMessages((currentMessages) => currentMessages.map((message) => message.id === messageId ? {
        ...message,
        reactions
    }: message))
}, [])


    useEffect(() => {
        setMessages([]);
        setNextUrl(null)
        setError(null)

        if(conversationId !== null) {
            fetchMessages()
        } 
    }, [conversationId, fetchMessages])

 return {
    messages,
    setMessages,
    updateMessage,
    markMessageDeleted,
    updateMessageReactions,
    nextUrl,
    loading,
    loadingOlder,
    hasMore: nextUrl !== null,
    error,
    refreshMessages: fetchMessages,
    loadOlderMessages,
 }
}