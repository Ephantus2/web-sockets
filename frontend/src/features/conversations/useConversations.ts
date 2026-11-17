import { useCallback, useEffect, useState } from "react";

import { conversationService } from "./conversationService";
import type { Conversation } from "./types";

export function useConversations() {
    const [conversations, setConversations] = useState<Conversation[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchConversations = useCallback(async () => {
        try{
            setLoading(true)
            setError(null)
            const data = await conversationService.getConversations();

            setConversations(data);
        } catch (err){
            console.error("Failed to fetch conversations:", err)

            setError("Unable to load conversations. Please try again.")
        }finally{
            setLoading(false)
        }
    }, []);

    useEffect(() => {
        fetchConversations();
    }, [])

    return {
        conversations,
        loading,
        error,
        refreshConversations: fetchConversations
    }
}