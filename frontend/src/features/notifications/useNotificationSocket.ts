import { useCallback, useEffect, useRef, useState } from "react";
import { createNotificationWebSocket } from "./notificationWebSocketService";
import type { Notification } from "./types";

interface NotificationEvent {
    type: "notification";
    notification: Notification;
}

interface ConnectionEvent {
    type: "notification_connection";
    message: string;
}

type ServerEvent = NotificationEvent | ConnectionEvent;

export function useNotificationSocket(onNotification: (notification: Notification) => void) {
    const socketRef = useRef<WebSocket | null>(null)
    const callbackRef = useRef(onNotification);
    const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(null)
    const reconnectAttemptsRef = useRef(0);
    const mountedRef = useRef(false)

    const [isConnected, setIsConnected] = useState(false)
    const [connectionError, setConnectionError] = useState<string | null>(null);

    // keep the latest callback without reconnecting the socket.

    useEffect(() => {
        callbackRef.current = onNotification;
    }, [onNotification])

    const connect = useCallback(() => {
        if (!mountedRef.current) return;

        try {
            const socket = createNotificationWebSocket();
            socketRef.current = socket;

            socket.onopen = () => {
                reconnectAttemptsRef.current = 0;
                setIsConnected(true)
                setConnectionError(null);
                console.log("Notification WebSocket connected.");
            };

            socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data) as ServerEvent;

                    if (data.type === "notification") {
                        callbackRef.current(data.notification)
                    }
                } catch (error) {
                    console.error(
                        "Failed to process notification event:",
                        event
                    );
                }
            }
            socket.onerror = () => {
                setConnectionError("Notification connection encountered an error.")
            }

            socket.onclose = (event) => {
                setIsConnected(false);
                if (socketRef.current === socket) {
                    socketRef.current = null
                }

                // Authentication failures should not retry indefinitely.

                if(event.code === 4401 || event.code === 4403) {
                    setConnectionError("Notification connection authentication failed");
                    return;
                }

                if (!mountedRef.current) return;

                const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current,
                    30000
                );

                reconnectAttemptsRef.current += 1;

                reconnectTimerRef.current = setTimeout(() => {
                    connect();
                }, delay)
            }
        } catch (error) {
            console.error("Failed to create notification WebSocket:", error)
            setConnectionError("Unable to establish nitification connection.");
        }
    }, []);

    useEffect(() => {
        mountedRef.current = true;

        connect();

        return () => {
            mountedRef.current = false;

            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
            }

            socketRef.current?.close();
            socketRef.current = null
        }
    }, [connect]);

    return {
        isConnected,
        connectionError
    }
}