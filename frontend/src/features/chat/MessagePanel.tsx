import { useCallback, useEffect, useRef, useState } from "react";
import {
  MessageCircle,
  RefreshCw,
  Search,
  X,
  ArrowLeft,
  Pin,
  PinOff,
  Forward,
  Reply,
} from "lucide-react";

import { useMessages } from "./useMessages";
import { useChatSocket } from "./useChatSocket";
import MessageComposer from "./MessageComposer";
import { messageService } from "./messageService";
import MessageEditHistory from "./MessageEditHistory";
import type { Message } from "./types";
import type { Conversation } from "../conversations/types";

import { useAuth } from "../../context/AuthContext";

import MessageReactions from "./MessageReactions";
interface MessagePanelProps {
  conversationId: number;
  onBack: () => void;
  conversations: Conversation[];
}

const MessagePanel = ({
  conversationId,
  onBack,
  conversations,
}: MessagePanelProps) => {
  const {
    messages,
    setMessages,
    updateMessage,
    updateMessageReactions,
    updatePinnedMessage,
    markMessageDeleted,
    loading,
    loadingOlder,
    hasMore,
    error,
    refreshMessages,
    loadOlderMessages,
  } = useMessages(conversationId);

  const { user } = useAuth();

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Message[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showSearch, setShowSearch] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [readMessageIds, setReadMessageIds] = useState<number[]>([]);
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [historyMessageId, setHistoryMessageId] = useState<number | null>(null)

  // message forwading

  const [forwardingMessage, setForwardingMessage] = useState<Message | null>(
    null,
  );
  const [selectedDestinations, setSelectedDestinations] = useState<number[]>(
    [],
  );
  const [forwarding, setForwarding] = useState(false);
  const [forwardError, setForwardError] = useState<string | null>(null);

  const [replyingTo, setReplyingTo] = useState<Message | null>(null);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const previousScrollHeightRef = useRef<number | null>(null);

  // Restore read indicators from messages loaded through the rest API.

  useEffect(() => {
    if (!user) return;

    const previouslyReadIds = messages
      .filter((message) => {
        const isOwnMessage = message.sender === user.username;

        const wasReadBySomeoneElse =
          Array.isArray(message.read_by) &&
          message.read_by.some((reader) => reader !== user.username);

        return isOwnMessage && wasReadBySomeoneElse;
      })
      .map((message) => message.id);

    setReadMessageIds((previousIds) => [
      ...new Set([...previousIds, ...previouslyReadIds]),
    ]);
  }, [messages, user]);

  const handleSearch = async () => {
    const query = searchQuery.trim();

    if (!query) return;

    try {
      setSearching(true);
      setSearchError(null);

      const results = await messageService.searchMessages(
        conversationId,
        query,
      );

      setSearchResults(results);
      setHasSearched(true);
    } catch (error) {
      console.error("Message search failed:", error);
      setSearchError("Unable to search messages. Please try again.");
    } finally {
      setSearching(false);
    }
  };

  // Receive messages from the websocket

  const handleIncomingMessage = useCallback(
    (message: (typeof messages)[number]) => {
      setMessages((previousMessages) => {
        //prevent duplicate messages
        
        if (previousMessages.some((item) => item.id == message.id)) {
          return previousMessages;
        }
        return [...previousMessages, message];
      });
    },
    [setMessages],
  );

  const handleTooglePin = async (messageId: number) => {
    try {
      const response = await messageService.togglePin(
        conversationId,
        messageId,
      );
      updatePinnedMessage(
        response.message_id,
        response.is_pinned,
        response.pinned_at,
        response.pinned_by,
      );
    } catch (error) {
      console.error("Failed to toggle message pin:", error);
    }
  };

  // Establish the websocket connection

  const lastMessageId = messages.reduce(
    (lastId, message) => Math.max(lastId, message.id),
    0,
  );

  const {
    isConnected,
    connectionError,
    sendMessage,
    readReceipt,
    markAsRead,
    sendTyping,
    typingUsers,
  } = useChatSocket(
    conversationId,
    handleIncomingMessage,
    lastMessageId,
    updateMessage,
    markMessageDeleted,
    updateMessageReactions,
    updatePinnedMessage,
  );

  // clear previous conversation's read statuses.
  useEffect(() => {
    setReadMessageIds([]);
  }, [conversationId]);

  // track messages read by other participants

  useEffect(() => {
    if (!readReceipt) return;

    if (Number(readReceipt.conversation_id) !== conversationId) {
      return;
    }

    // Ignore read receipts generated by the current user.
    if (readReceipt.user === user?.username) {
      return;
    }
    setReadMessageIds((previousIds) => [
      ...new Set([...previousIds, ...readReceipt.message_ids]),
    ]);
  }, [readReceipt, conversationId, user?.username]);

  useEffect(() => {
    if (isConnected && document.visibilityState === "visible") {
      markAsRead();
    }
  }, [isConnected, messages, markAsRead]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && isConnected) {
        markAsRead();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isConnected, markAsRead]);

  // send messages through the websocket

  const handleSendMessage = async (content: string) => {
    sendMessage(content, replyingTo?.id ?? null);
    setReplyingTo(null);
  };

  const handleEditMessage = async (messageId: number) => {
    const content = editContent.trim();
    if (!content || savingEdit) return;

    try {
      setSavingEdit(true);
      setEditError(null);
      const updatedMessage = await messageService.editMessage(
        conversationId,
        messageId,
        content,
      );

      updateMessage(updatedMessage);

      setEditingMessageId(null);
      setEditContent("");
    } catch (error) {
      console.error("Failed to edit message:", error);
      setEditError("Unable to edit message. Please try again.");
    } finally {
      setSavingEdit(false);
    }
  };

  // handle delete message

  const handleDeleteMessage = async (messageId: number) => {
    try {
      const deletedMessage = await messageService.deleteMessage(
        conversationId,
        messageId,
      );

      // update the messageusing server response.
      updateMessage(deletedMessage);
    } catch (error) {
      console.error("Failed to delete message:", error);
    }
  };

  const handleReact = async (messageId: number, emoji: string) => {
    try {
      const response = await messageService.toggleReaction(
        conversationId,
        messageId,
        emoji,
      );
      updateMessageReactions(messageId, response.reactions);
    } catch (error) {
      console.error("Failed to toogle reaction:", error);
    }
  };

  const handleOpenForward = (message: Message) => {
    setForwardingMessage(message);
    setSelectedDestinations([]);
    setForwardError(null);
  };

  const handleToggleDestination = (conversationId: number) => {
    setSelectedDestinations((previous) =>
      previous.includes(conversationId)
        ? previous.filter((id) => id !== conversationId)
        : [...previous, conversationId],
    );
  };

  const handleForwardMessage = async () => {
    if (!forwardingMessage || selectedDestinations.length === 0) {
      return;
    }

    try {
      setForwarding(true);
      setForwardError(null);

      const response = await messageService.forwardMessage(
        conversationId,
        forwardingMessage.id,
        selectedDestinations,
      );

      // if the current conversation is also a destination
      // refresh its message to display the forwarded copy

      if (selectedDestinations.includes(conversationId)) {
        await refreshMessages;
      }

      console.log(`
        Successfully forwarded a message to ${response.forwarded_count} conversations.`);

      setForwardingMessage(null);
      setSelectedDestinations([]);
    } catch (error: any) {
      console.error("Failed to forward message:", error);

      setForwardError(
        error.response?.data?.error ||
          "Unable to forward message. Please try again.",
      );
    } finally {
      setForwarding(false);
    }
  };

  // scroll to the latest message

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const previousHeight = previousScrollHeightRef.current;

    if (previousHeight !== null) {
      const heightDifference = container.scrollHeight - previousHeight;
      container.scrollTop += heightDifference;
      previousScrollHeightRef.current = null;
      return;
    }
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  const pinnedMessage = messages.find((message) => message.is_pinned);

  return (
    <div className="flex h-full flex-col bg-slate-950">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-800 p-5">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={onBack}
            className="shrink-0 rounded-lg p-2 text-slate-400
                hover:bg-slate-800 hover:text-white md:hidden"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h2 className="font-semibold text-white">
              Conversation #{conversationId}
            </h2>

            <p className="mt-1 text-xs text-slate-400">
              {isConnected ? "Connected" : "Connecting..."}
            </p>
            {readReceipt &&
              Number(readReceipt.conversation_id) === conversationId && (
                <p className="mt-2 text-xs text-green-400">
                  <span className="font-semibold">{readReceipt.user}</span> read{" "}
                  {readReceipt.count}
                  message(s), Unread: {readReceipt.unread_count}
                </p>
              )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`h-2.5 w-2.5 rounded-full ${isConnected ? "bg-green-500" : "bg-yellow-500"}`}
            title={isConnected ? "Connected" : "Disconnected"}
          />

          <button
            onClick={() => {
              setShowSearch((previous) => !previous);
              setSearchQuery("");
              setSearchResults([]);
              setSearchError(null);
            }}
            title="Search messages"
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white"
          >
            <Search size={18} />
          </button>

          <button
            onClick={refreshMessages}
            disabled={loading}
            title="Refresh Messages"
            className="rounded-lg p-2 text-slate-400 transition  hover:bg-slate-800
                hover:text-white disabled:opacity-50"
          >
            <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </header>

      {showSearch && (
        <div className="border-b border-slate-800 bg-slate-900 p-4">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              handleSearch();
            }}
            className="flex gap-2"
          >
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search messages..."
              className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-800
                        px-4 py-2 text-sm text-white oultline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={searching || !searchQuery.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {searching ? "Searching..." : "Search"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowSearch(false);
                setSearchQuery("");
                setSearchResults([]);
                setSearchError(null);
              }}
              title="Close search"
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              <X size={18} />
            </button>
          </form>
        </div>
      )}

      {/* connection error */}

      {connectionError && (
        <div
          className="border-b border-red-500/20 bg-red-500/10
            p-3 text-center text-xs text-red-400"
        >
          {connectionError}
        </div>
      )}

      {/* Search results */}

      {showSearch && hasSearched && (
        <div className="border-b border-slate-800 bg-slate-900 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Search Results</h3>
            <span className="text-xs text-slate-400">
              {searchResults.length} found
            </span>
          </div>
          {searchError && (
            <p className="text-xs text-slate-400">{searchError}</p>
          )}
          <div className="max-h-64 space-y-3 overflow-y-auto">
            {searchResults.map((message) => (
              <div
                key={message.id}
                className="rounded-lg border border-slate-700 bg-slate-800 p-3"
              >
                <p className="mb-1 text-xs font-semibold text-blue-400">
                  {message.sender}
                </p>
                <p className="text-sm text-slate-200">
                  {message.is_deleted
                    ? "This message was deleted"
                    : message.content}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  {new Date(message.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {pinnedMessage && (
        <div
          onClick={() => {
            document
              .getElementById(`message-${pinnedMessage.id}`)
              ?.scrollIntoView({
                behavior: "smooth",
                block: "center",
              });
          }}
          className="border-b border-slate-800 bg-slate-900 px-4 py-3 cursor-pointer"
        >
          <div className="mx-auto flex max-w-4xl items-center gap-3">
            <Pin size={18} className="shrink-0 text-blue-400" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-blue-400">
                Pinned message . {pinnedMessage.sender}
              </p>
              <p className="truncate text-sm text-slate-200">
                {pinnedMessage.is_deleted
                  ? "This message was deleted "
                  : pinnedMessage.content}
              </p>
            </div>
            <span className="shrink-0 text-xs text-slate-500">
              {new Date(pinnedMessage.pinned_at!).toLocaleDateString()}
            </span>
          </div>
        </div>
      )}

      {/* Messages */}

      <div
        ref={messagesContainerRef}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:p-5"
      >
        {loading && messages.length === 0 && (
          <p className="py-10 text-center text-sm text-slate-400">
            Loading Messages...
          </p>
        )}

        {error && (
          <div className="mx-auto max-w-md rounded=lg bg-red-500/10 p-4 text-center text-sm text-red-400">
            <p>{error}</p>

            <button
              onClick={refreshMessages}
              className="mt-2 font-semibold underline"
            >
              Try again
            </button>
          </div>
        )}

        {!loading && !error && messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <MessageCircle size={40} className="mb-3 text-slate-600" />
            <p className="font-medium text-slate-300">No messages yet</p>

            <p className="mt-1 text-sm text-slate-500">
              Messages will appear here.
            </p>
          </div>
        )}

        <div className="space-y-4">
          {hasMore && (
            <div className="flex justify-center pb-4">
              <button
                onClick={() => {
                  if (messagesContainerRef.current) {
                    previousScrollHeightRef.current =
                      messagesContainerRef.current.scrollHeight;
                  }

                  loadOlderMessages();
                }}
                disabled={loadingOlder}
                className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-300 transition hover:bg-slate-700 disabled:opacity-50"
              >
                {loadingOlder
                  ? "Loading older messages..."
                  : "Load older messages"}
              </button>
            </div>
          )}
          {messages.map((message) => {
            const isOwnMessage = message.sender === user?.username;

            const isRead = readMessageIds.includes(message.id);

            return (
              <div
                key={message.id}
                id={`message-${message.id}`}
                className={`flex w-full ${
                  isOwnMessage ? "justify-end" : "justify-start"
                }`}
              >
                <div className="max-w-[90%] sm:max-w-2xl">
                  <div
                    className={`mb-1 text-xs text-slate-500 ${isOwnMessage ? "text-right" : "text-left"}`}
                  >
                    {isOwnMessage ? "You" : message.sender}
                  </div>
                  {message.is_deleted ? (
                    <div
                      className=" inline-block rounded-2xl bg-slate-800
                                    px-4 py-3 text-sm italic text-slate-400
                                    "
                    >
                      This message was deleted
                    </div>
                  ) : editingMessageId === message.id ? (
                    <div
                      className="w-full min-w-[240px] rounded-xl
                                    border border-slate-700 bg-slate-900 p-3"
                    >
                      <textarea
                        value={editContent}
                        onChange={(event) => setEditContent(event.target.value)}
                        maxLength={5000}
                        rows={3}
                        className="w-full resize-y rounded-lg border border-slate-700
                                            bg-slate-800 p-3 text-sm text-white outline-none focus:border-blue-500"
                        autoFocus
                      />
                      {editError && (
                        <p className="mt-2 text-xs text-red-400">{editError}</p>
                      )}

                      <div className="mt-3 flex justify-end gap-2">
                        <button
                          onClick={() => {
                            setEditingMessageId(null);
                            setEditContent("");
                            setEditError(null);
                          }}
                          disabled={savingEdit}
                          className="rounded-lg px-3 py-2 text-xs text-slate-700
                                            disabled:opacity-50"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => {
                            handleEditMessage(message.id);
                          }}
                          disabled={savingEdit || !editContent.trim()}
                          className="rounded-lg bg-blue-600 px-3 py-2 text-xs front-medium text-white hover:bg-blue-500
                                            disabled:opacity-50"
                        >
                          {savingEdit ? "Saving..." : "Save"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      {message.forwarded_from && (
                        <div
                          className="mb-1 flex items-center gap-1.5
                        text-xs italic-xs italic text-slate-400"
                        >
                          <Forward size={13} />
                          <span>
                            Forwarded from{" "}
                            {message.forwarded_sender || "another user"}
                          </span>
                        </div>
                      )}

                      <div
                        className={`inline-block rounded-2xl px-4 py-3 text-sm
                                    ${isOwnMessage ? "rounded-tr-sm bg-blue-600 text-white" : "rounded-tl-sm bg-slate-800 text-slate-200"}`}
                      >
                        {message.reply_to && (
                          <button
                            type="button"
                            onClick={() => {
                              document
                                .getElementById(`message-${message.reply_to}`)
                                ?.scrollIntoView({
                                  behavior: "smooth",
                                  block: "center",
                                });
                            }}
                            className="mb-2 block w-full max-w-full rounded-lg border-l-4 border-blue-500 bg-slate-800/80 px-3 py-2 text-left hover:bg-slate-700 transition"
                          >
                            <p className="text-xs font-semibold text-slate-400">{message.reply_sender || "Original sender"}</p>
                            <p className="truncate text-xs text-slate-300">{message.reply_content || "Original Message"}</p>
                          </button>
                        )}
                        {message.content}
                      </div>

                      <MessageReactions
                        reactions={message.reactions ?? []}
                        currentUsername={user?.username}
                        onReact={(emoji) => handleReact(message.id, emoji)}
                        disabled={!isConnected}
                      />
                    </>
                  )}
                  <div
                    className={`mt-1 flex items-center gap-1 text-xs ${
                      isOwnMessage ? "justify-end" : "justify-start"
                    }`}
                  >
                    {!message.is_deleted && editingMessageId !== message.id && (
                      <div className="mb-1 flex items-center justify-end gap-3">
                        <button
                          onClick={() => setReplyingTo(message)}
                          title="Reply to message"
                          className="rounded p-1.5 text-slate-400 hover:bg-slate-700 hover:text-white transition"
                        >
                          <Reply size={16} />
                        </button>

                        <button
                          onClick={() => handleTooglePin(message.id)}
                          disabled={!isConnected}
                          title={
                            message.is_pinned ? "Unpin message" : "Pin message"
                          }
                          className={`flex items-center gap-1 text-xs transition 
                              ${message.is_pinned ? "text-blue-400 hover:text-blue-300" : "text-slate-400 hover:text-blue-400"} disabled:opacity-50`}
                        >
                          {message.is_pinned ? (
                            <PinOff size={13} />
                          ) : (
                            <Pin size={13} />
                          )}
                          {message.is_pinned ? "Unpin" : "Pin"}
                        </button>
                        {isOwnMessage && (
                          <>
                            <button
                              onClick={() => {
                                setEditingMessageId(message.id);
                                setEditContent(message.content);
                                setEditError(null);
                              }}
                              className="text-xs text-slate-400 transition hover:text-blue-400"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteMessage(message.id)}
                              className="text-xs text-red-400 hover:text-red-300"
                            >
                              Delete
                            </button>
                            <button
                              onClick={() => handleOpenForward(message)}
                              title="Forward message"
                              className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-700 hover:text-white"
                            >
                              <Forward size={16} />
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    <span className="text-slate-500">
                      {new Date(message.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    {message.is_edited && !message.is_deleted && (
                      <>
                      <span className="text-slate-500 italic">Edited</span>

                      <button
                      type="button"
                      onClick={() => setHistoryMessageId(message.id)}
                      className="text-blue-400 transition hover:text-blue-300"
                      title="View edit history"
                      >
                        View History
                      </button>
                      </>
                    )}
                    {isOwnMessage && (
                      <span
                        title={isRead ? "Read" : "Sent"}
                        className={isRead ? "text-blue-400" : "text-slate-500"}
                      >
                        {isRead ? "✓✓" : "✓"}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div ref={bottomRef} />
      </div>
      {/* Typing indicator */}

      {typingUsers.length > 0 && (
        <div className="border-t border-slate-800 px-5 py-2">
          <p className="text-xs italic text-blue-400">
            {typingUsers.length === 1
              ? `${typingUsers[0]} is typing...`
              : typingUsers.length === 2
                ? `${typingUsers[0]} and ${typingUsers[1]} are typing...`
                : `${typingUsers.length} people are typing`}
          </p>
        </div>
      )}

      {/* Message input */}

      {replyingTo && (
        <div
          className="flex items-center justify-between gap-3
          border-t border-slate-700 bg-slate-800 px-4 py-3"
        >
          <div className="min-w-0 border-l-4 border-blue-500 pl-3">
            <p className="text-xs font-semibold text-blue-400">
              Replying to {replyingTo.sender}
            </p>
            <p className="truncate text-sm text-slate-300">
              {replyingTo.content}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setReplyingTo(null)}
            title="Cancel reply"
            className="shrink-0 rounded-lg p-2 text-slate-400 hover:bg-slate-700 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>
      )}

      <MessageComposer
        onSend={handleSendMessage}
        onTyping={sendTyping}
        disabled={!isConnected}
      />

      {forwardingMessage && (
        <div className="fixed inset-o z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-xs border border-slate-700 bg-slate-900 p-5 shadow-2xl">
            {/* Dialog header */}
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">
                  Forward message
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  Select one or more conversations
                </p>
              </div>
              <button
                onClick={() => setForwardingMessage(null)}
                disabled={forwarding}
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>

            {/* Message preview */}

            <div className="mb-4 rounded-lg bg-slate-800 p-3">
              <p className="text-xs font-semibold text-slate-400">
                {forwardingMessage.sender}
              </p>
              <p className="mt-1 line-clamp-3 text-sm text-slate-200">
                {forwardingMessage.content}
              </p>
            </div>
            {/* Available destinations */}

            <div className="max-h-64 space-y-2 overflow-y-auto">
              {conversations
                .filter((conversation) => conversation.id !== conversationId)
                .map((conversation) => (
                  <label
                    key={conversation.id}
                    className="flex cursor-pointer items-center gap-3 rounded-lg
                    p-3 transition hover:bg-slate-800"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDestinations.includes(conversation.id)}
                      onChange={() => handleToggleDestination(conversation.id)}
                      disabled={forwarding}
                      className="h-4 w-4 accent-blue-500"
                    />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">
                        {conversation.name || `Conversation ${conversation.id}`}
                      </p>
                      <p className="text-xs text-slate-400">
                        {conversation.participants.length} participants
                      </p>
                    </div>
                  </label>
                ))}

              {conversations.filter(
                (conversation) => conversation.id !== conversationId,
              ).length === 0 && (
                <p className="py-8 text-center text-sm text-slate-400">
                  No other conversations available.
                </p>
              )}
            </div>
            {/* Error */}

            {forwardError && (
              <p className="mt-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
                {forwardError}
              </p>
            )}

            {/* Footer */}
            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setForwardingMessage(null)}
                disabled={forwarding}
                className="rounded-lg px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleForwardMessage}
                disabled={forwarding || selectedDestinations.length === 0}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2
                text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Forward size={16} />
                {forwarding ? "Forwarding..." : "Forward"}
              </button>
            </div>
          </div>
        </div>
      )}

      {
        historyMessageId && (
          <MessageEditHistory conversationId={conversationId}
          messageId={historyMessageId}
          onClose={() => setHistoryMessageId(null)}
           />
        )
      }
    </div>
  );
};

export default MessagePanel;
