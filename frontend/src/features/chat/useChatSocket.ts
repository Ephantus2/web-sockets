
import { useCallback, useEffect, useRef, useState } from "react";
import { createChatWebSocket } from "./websocketService";
import type { Message } from "./types";

interface ConnectionMessage {
  type: "connection_established";
  conversation_id: number;
  message: string;
}

interface IncomingMessage {
  type: "chat_message";
  message: Message;
}

type ServerEvent = ConnectionMessage | IncomingMessage;

const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;

export function useChatSocket(
  conversationId: number | null,
  onMessageReceived: (message: Message) => void
) {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const sendMessage = useCallback((content: string) => {
    const socket = socketRef.current;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected.");
    }

    socket.send(
      JSON.stringify({
        type: "message",
        message: content,
      })
    );
  }, []);

  useEffect(() => {
    if (conversationId === null) return;

    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;

    let active = true;

    const connect = () => {
      if (!active || !shouldReconnectRef.current) return;

      let socket: WebSocket;

      try {
        socket = createChatWebSocket(conversationId);
        socketRef.current = socket;
      } catch (error) {
        setConnectionError(
          error instanceof Error
            ? error.message
            : "Unable to create WebSocket connection."
        );
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (!active) {
          socket.close();
          return;
        }

        reconnectAttemptsRef.current = 0;
        setIsConnected(true);
        setConnectionError(null);

        console.log("WebSocket connected:", conversationId);
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const data: ServerEvent = JSON.parse(event.data);

          if (data.type === "connection_established") {
            console.log(data.message);
            return;
          }

          if (data.type === "chat_message") {
            onMessageReceived(data.message);
          }
        } catch (error) {
          console.error("Invalid WebSocket event:", error);
        }
      };

      socket.onerror = () => {
        setConnectionError("WebSocket connection error.");
      };

      socket.onclose = (event) => {
        if (!active) return;

        setIsConnected(false);
        console.log("WebSocket disconnected:", event.code);

        if (event.code === 4401 || event.code === 4403) {
          shouldReconnectRef.current = false;
          setConnectionError(
            event.code === 4401
              ? "Authentication failed. Please log in again."
              : "You do not have access to this conversation."
          );
          return;
        }

        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (!active || !shouldReconnectRef.current) return;

      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }

      const delay = Math.min(
        INITIAL_RECONNECT_DELAY *
          2 ** reconnectAttemptsRef.current,
        MAX_RECONNECT_DELAY
      );

      reconnectAttemptsRef.current += 1;

      setConnectionError(
        `Connection lost. Reconnecting in ${Math.round(delay / 1000)} seconds...`
      );

      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    };

    connect();

    return () => {
      active = false;
      shouldReconnectRef.current = false;

      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      socketRef.current?.close();
      socketRef.current = null;

      setIsConnected(false);
    };
  }, [conversationId, onMessageReceived]);

  return {
    isConnected,
    connectionError,
    sendMessage,
  };
}
