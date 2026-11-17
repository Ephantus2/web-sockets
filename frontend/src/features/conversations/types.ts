export interface Conversation {
    id: number;
    name: string | null;
    participants: number[];
    created_at: string;
    updated_at: string;
}

export interface UnreadConversation {
    id: number;
    name: string | null;
    unread_count: number;
}
