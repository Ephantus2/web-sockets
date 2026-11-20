import { useCallback, useEffect, useState } from "react";
import { notificationService } from "./notificationService";
import type { Notification } from "./types";

export function useNotifications() {
    const [notifications, setNotifications] = useState<Notification[]>([])
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null)

    // calculate unread notifications

    const unreadCount = notifications.filter(
        (notification) => !notification.is_read
    ).length;

    // Fetch notifications from the backend

    const fetchNotifications = useCallback(async () => {
        try {
            setLoading(true)
            setError(null);

            const data = await notificationService.getNotifications();
            setNotifications(data)
        } catch (error){
            console.error("Failed to fetch notifications:", error)
        } finally {
            setLoading(false)
        }
    }, []);

    // Mark one notification as read

    const markAsRead = async (id: number) => {
        try {
            const updatedNotification = await notificationService.markAsRead(id);
            setNotifications((previousNotifications) => previousNotifications.map((notification) => notification.id ? updatedNotification : notification))
        } catch (error) {
            console.error("Failed to mark notification as read:", error);
        }
    }

    // Mark all notifications as read

    const markAllAsRead = async () => {
        try {
            await notificationService.markAllAsRead();
            setNotifications((previousNotifications) => previousNotifications.map((notification) => ({
                ...notification,
                is_read:true,
            })))
        } catch (error) {
            console.error("Failed to mark all notifications as read:", error);
        }
    }

    // Fetch notifications when the hook is first used

    useEffect(() => {
        fetchNotifications();
        const intervalId = setInterval(() => {
            fetchNotifications();
        }, 10000)

        return () => {
            clearInterval(intervalId)
        };
    }, [fetchNotifications]);

    return {
        notifications,
        loading,
        error,
        unreadCount,
        fetchNotifications,
        markAsRead,
        markAllAsRead
    }
}