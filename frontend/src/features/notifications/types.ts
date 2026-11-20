export interface Notification {
    id: number;
    sender: string | null;
    notification_type: string;
    title: string;
    message: string;
    conversation: number | null;
    is_read: boolean;
    created_at: string;
}