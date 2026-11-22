import api from "../../api/client";

import type { Message, PaginatedMessages, MessageReaction } from "./types";

export const messageService = {
    // retrieve the latest messages in a conversation

    async getMessages(conversationId: number): Promise<PaginatedMessages>{
        const response = await api.get<PaginatedMessages>(
            `/api/conversations/${conversationId}/messages/`
        );
        return response.data
    },

    // Retrieve older messages using Django's cursor URL

    async getOlderMessages(nextUrl: string ): Promise<PaginatedMessages> {
        const response = await api.get<PaginatedMessages>(nextUrl);

        return response.data;
    },

    // send a message through the Rest API

    async sendMessage(conversationId: number, content: string): Promise<Message> {
        const response = await api.post<Message>(`/api/conversations/${conversationId}/messages/`, { content })
        return response.data;
    },

    // search messages in a conversation 

    async searchMessages(
        conversationId: number,
        query: string
    ): Promise<Message[]> {
        const response = await api.get<Message[]>(
            `/api/conversations/${conversationId}/messages/search/`,
            {
                params: {q: query}
            }
        );

        return response.data
    },

    // Edit a message

    async editMessage(
        conversationId: number,
        messageId: number,
        content: string
    ): Promise<Message>{
        const response = await api.patch<Message>(`/api/conversations/${conversationId}/messages/${messageId}/`,
            { content }
        )

        return response.data
    },

    // Delete an existing message

    async deleteMessage(
        conversationId: number,
        messageId: number
    ): Promise<Message> {
        const response = await api.delete<Message>(
            `/api/conversations/${conversationId}/messages/${messageId}/`
        );
        return response.data
    },

    async toggleReaction(
        conversationId: number,
        messageId: number,
        emoji: string
    ): Promise<{
        message_id: number;
        conversation_id: number;
        action: "added" | "removed";
        reactions: MessageReaction[];
    }> {
        const response = await api.post(
            `/api/conversations/${conversationId}/messages/${messageId}/reactions/`,
            { emoji }
        );

        return response.data
    },

    // pin or unpin message

    async togglePin(
        conversationId: number,
        messageId: number
    ): Promise<{
        message_id: number;
        conversation_id: number;
        action: "pinned" | "unpinned";
        is_pinned: boolean;
        pinned_at: string | null;
        pinned_by: string | null;
    }>{
        const response = await api.post(
            `/api/conversations/${conversationId}/messages/${messageId}/pin/`
        )

        return response.data
    }
}