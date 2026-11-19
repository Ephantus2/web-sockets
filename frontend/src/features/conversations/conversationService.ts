import api from "../../api/client";
import type { Conversation, UnreadConversation } from "./types";

export const conversationService = {
    async getConversations(): Promise<Conversation[]>{
        const response = await api.get<Conversation[]>("/api/conversation/")

        return response.data;
    },

    async getConversation(id: number): Promise<Conversation> {
        const response = await api.get<Conversation>(
            `/api/conversations/${id}/`
        );

        return response.data
    },

    async createConversation(name: string, participants: number[]): Promise<Conversation> {
        const response = await api.post<Conversation>(
            "api/conversation/",
            {
                name,
                participants
            }
        )

        return response.data
    },

    async getUnreadCounts(): Promise<UnreadConversation[]> {
        const response = await api.get<UnreadConversation[]>("/api/conversations/unread-counts/");
        return response.data
    },
}