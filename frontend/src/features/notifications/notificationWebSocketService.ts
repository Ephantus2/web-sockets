import { tokenStorage } from "../../utils/tokenStorage";

const WS_BASE_URL = (
    import.meta.env.VITE_WS_BASE_URL || "ws://127.0.0.1:8000"
).replace(/\/$/, "");

export function createNotificationWebSocket(): WebSocket {
    const accessToken = tokenStorage.getAccessToken();

    if (!accessToken) {
        throw new Error("Cannot establish notification WebSocket without authentication.");
    }

    const url = `${WS_BASE_URL}/ws/notifications/` + `?token=${encodeURIComponent(accessToken)}`
    return new WebSocket(url);
}