export interface Message {
    id: number;
    conversation: number;
    sender: string;
    content: string;
    created_at: string;
}

export interface PaginatedMessages {
    next: string | null;
    previous: string | null;
    results: Message[]
}