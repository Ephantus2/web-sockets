export interface Message {
    id: number;
    conversation: number;
    sender: string;
    content: string;
    created_at: string;
    read_by: string[];
    is_edited: boolean;
    edited_at: string | null;
    is_deleted: boolean;
    deleted_at: string | null;
    reactions?: MessageReaction[];
}

export interface PaginatedMessages {
    next: string | null;
    previous: string | null;
    results: Message[]
}

export interface MessageReaction {
    id: number;
    message: number;
    user: string;
    emoji: string;
    created_at: string;
}

export interface ReactionUpdate {
    message_id: number;
    conversation_id: number;
    reactions?: MessageReaction[];
}