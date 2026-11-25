import api from "../../api/client";

import type { Message, PaginatedMessages, MessageReaction, MessageEditHistory } from "./types";

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

    async sendMessage(conversationId: number, content: string, replyTo: number | null = null): Promise<Message> {
        const response = await api.post<Message>(`/api/conversations/${conversationId}/messages/`, { content, reply_to: replyTo })
        return response.data;
    },

    // search messages in a conversation 

    async searchMessages(
        conversationId: number,
        query: string,
        filters?: {
            sender?: number;
            date_from?: string;
            date_to?: string;
        }
    ): Promise<PaginatedMessages> {
        const response = await api.get<PaginatedMessages>(
            `/api/conversations/${conversationId}/messages/search/`,
            {
                params: {
                    q: query,
                    ...filters
                }
            }
        );

        return response.data
    },

    // Load the next page of search results
    async getNextSearchPage(nextUrl: string): Promise<PaginatedMessages> {
        const response = await api.get<PaginatedMessages>(nextUrl);

        return response.data;
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

    async getMessageEditHistory(
        conversationId: number,
        messageId: number
    ): Promise<MessageEditHistory[]>{
        const response = await api.get(
            `/api/conversations/${conversationId}/messages/${messageId}/history/`
        )

        return response.data
    },

    // Delete an existing message

    async deleteMessage(
        conversationId: number,
        messageId: number,
        deleteFor: "me" | "everyone" = "everyone"
    ): Promise<Message | {
        message: string;
        message_id: number;
        delete_for: "me"
    }> {
        const response = await api.delete<Message>(
            `/api/conversations/${conversationId}/messages/${messageId}/`,
            {
                data: {
                    delete_for: deleteFor
                }
            }
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
    },

    async forwardMessage(
        conversationId: number,
        messageId: number,
        destinationConversationIds: number[]
    ): Promise<{
        forwarded_count: number;
        messages: Message[];
    }> {
        const response = await api.post(
            `/api/conversations/${conversationId}/messages/${messageId}/forward/`,
            {
                destination_conversation_ids: destinationConversationIds
            }
        );

        return response.data;
    }
}