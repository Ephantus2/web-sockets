import api from "../../api/client";
import type { Notification } from "./types"

export const notificationService = {

    // Fetch all notifications
    async getNotifications(): Promise<Notification[]> {
        const response = await api.get<Notification[]>("/api/notifications/");

        return response.data
    },

    // Fetch unread notifications only

    async getUnreadNotifications(): Promise<Notification[]> {
        const response = await api.get<Notification[]>(
            "/api/notifications/",
            {
                params: {unread: "true"}
            }
        );

        return response.data
    },

    async markAsRead(id: number): Promise<Notification> {
        const response = await api.patch<Notification>(
            `/api/notifications/${id}/read/`
        );

        return response.data;
    },

    // Mark all notifications as read

    async markAllAsRead(): Promise<void> {
        await api.post(
            "/api/notifications/read-all/"
        );
    }
}