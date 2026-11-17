import api from "../../api/client";

import type { Message, PaginatedMessages } from "./types";

export const messageService = {
    // retrieve the latest messages in a conversation

    async getMessages(conversationId: number): Promise<PaginatedMessages>{
        const response = await api.get<PaginatedMessages>(
            `/api/conversations/${conversationId}/messages/`
        );
        return response.data
    },

    // Retrieve older messages using Django's cursor URL

    async getOlderMessage(nextUrl: string): Promise<PaginatedMessages> {
        const response = await api.get<PaginatedMessages>(nextUrl);

        return response.data;
    },

    // send a message through the Rest API

    async sendMessage(conversationId: number, content: string): Promise<Message> {
        const response = await api.post<Message>(`/api/conversations/${conversationId}/messages`, { content })
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
    }
}
