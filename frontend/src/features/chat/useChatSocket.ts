
import { useCallback, useEffect, useRef, useState } from "react";
import { createChatWebSocket } from "./websocketService";
import type { Message, MessageReaction } from "./types";

interface ConnectionMessage {
  type: "connection_established";
  conversation_id: number;
  message: string;
}

interface IncomingMessage {
  type: "chat_message";
  message: Message;
}

interface SyncBatchMessage {
  type: "sync_batch";
  conversation_id: number;
  messages: Message[];
  next_cursor: number;
  has_more: boolean;
}

interface ReadReceiptMessage {
    type: "read_receipt";
    user: string;
    conversation_id: number | string;
    message_ids: number[];
    count: number;
    unread_count: number;
}

interface TypingMessage {
  type: "typing",
  user: string,
  is_typing: boolean;
}

type ServerEvent =
  | ConnectionMessage
  | IncomingMessage
  | SyncBatchMessage
  | ReadReceiptMessage
  | TypingMessage
  | {
    type: "message_edited";
    message: Message
  }
  | {
    type: "message_deleted";
    message_id: number;
    conversation_id: number;
  }
  | {
    type: "reaction_updated",
    message_id: number,
    conversation_id: number,
    reactions: MessageReaction[]
  }
  | {
    type: "pin_updated";
    conversation_id: number;
    message_id: number | null;
    is_pinned: boolean;
    pinned_at: string | null;
    pinned_by: string | null;
  }

const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;

export function useChatSocket(
  conversationId: number | null,
  onMessageReceived: (message: Message) => void,
  lastMessageId = 0,
  onMessageEdited: (message:  Message) => void,
  onMessageDeleted: (messageId: number) => void,
  onReactionUpdated: (messageId: number, reactions: MessageReaction[]) => void,
  onPinUpdated: (
    messageId: number | null,
    isPinned: boolean,
    pinnedAt: string | null,
    pinnedBy: string | null
  ) => void
) {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const lastMessageIdRef = useRef(lastMessageId);

  // Keep the latest message ID without restarting the WebSocket effect.
  lastMessageIdRef.current = lastMessageId;

  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [readReceipt, setReadReceipt] = useState<ReadReceiptMessage | null>(null);
  const [typingUsers, setTypingUsers] = useState<string[]>([])

  const sendMessage = useCallback((content: string, replyTo: number | null) => {
    const socket = socketRef.current;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected.");
    }

    socket.send(JSON.stringify({
      type: "message",
      message: content,
      reply_to: replyTo
    }));
  }, []);

  const markAsRead = useCallback(() => {
    const socket = socketRef.current;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
        return;
    }
    socket.send(JSON.stringify({
        type: "read"
    }));
  }, [])

  const sendTyping = useCallback((isTyping: boolean) => {
    const socket = socketRef.current;

    console.log("SEND TYPING CALLED:", isTyping)
    console.log("WEBSOCKET STATE:", socket?.readyState)

    if (!socket || socket.readyState !== WebSocket.OPEN){
      console.log("WEBSOCKET NOT OPEN - TYPING NOT SENT :", socket?.readyState)
      return;
    }

    socket.send(JSON.stringify({
      type: "typing",
      is_typing: isTyping
    }))
    console.log("TYPING EVENT SENT")
  }, [])

  useEffect(() => {
    if (conversationId === null) return;

    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;

    let active = true;

    const requestSync = (cursor: number) => {
      const socket = socketRef.current;

      if (!socket || socket.readyState !== WebSocket.OPEN) return;

      socket.send(JSON.stringify({
        type: "sync",
        last_message_id: cursor,
      }));
    };

    const scheduleReconnect = () => {
      if (!active || !shouldReconnectRef.current) return;

      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }

      const delay = Math.min(
        INITIAL_RECONNECT_DELAY * 2 ** reconnectAttemptsRef.current,
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

            // Recover messages missed while disconnected.
            requestSync(lastMessageIdRef.current);

            // Tell Django that this user has opened the conversation.
            socket.send(JSON.stringify({
                type: "read",
            }))

            return;
          }

          if (data.type === "pin_updated") {
            onPinUpdated(
              data.message_id,
              data.is_pinned,
              data.pinned_at,
              data.pinned_by
            );
            return;
          }

          if (data.type === "chat_message") {
            onMessageReceived(data.message);
            return;
          }

          console.log("WEBSOCKET EVENT:", data)

          if (data.type === "message_edited"){
            onMessageEdited(data.message);
            return;
          }

          if (data.type === "message_deleted") {
            onMessageDeleted(data.message_id)
            return
          }

          if (data.type === "reaction_updated"){
            onReactionUpdated(
              data.message_id,
              data.reactions
            );
            return
          }

          if(data.type === "read_receipt")  {
            setReadReceipt(data);
            console.log("Read receipt received:", data);
            return;
          }

          if(data.type === "typing") {
            setTypingUsers((previousUsers) => {
              if(data.is_typing){
                if(previousUsers.includes(data.user)) {
                  return previousUsers
                }
                return [...previousUsers, data.user];
              } 
              return previousUsers.filter(
                (user) => user !== data.user
              )
            })
            return
          }

          if (data.type === "sync_batch") {
            // Add recovered messages to the chat.
            data.messages.forEach(onMessageReceived);

            // Fetch another batch if the server has more.
            if (data.has_more) {
              requestSync(data.next_cursor);
            }

            return;
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
        setTypingUsers([])
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
  }, [conversationId, onMessageReceived, onPinUpdated]);

  return {
    isConnected,
    connectionError,
    sendMessage,
    readReceipt,
    markAsRead,
    sendTyping,
    typingUsers
  };
}
