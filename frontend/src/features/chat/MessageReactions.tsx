import type { MessageReaction } from "./types"

interface MessageReactionProps {
    reactions: MessageReaction[];
    currentUsername: string | undefined;
    onReact: (emoji: string) => void;
    disabled?: boolean;
}

const EMOJIS = ["😂", "👍", "❤️", "😢", "😮", "🔥"]

const MessageReactions = ({
    reactions,
    currentUsername,
    onReact,
    disabled = false
}: MessageReactionProps) => {
    // Group reaction by emoji

    const groupedReactions = EMOJIS.map((emoji) => {
        const matchingReactions = reactions.filter((reaction) => reaction.emoji === emoji)
        return {
            emoji,
            count: matchingReactions.length,
            users: matchingReactions.map((reaction) => reaction.user),
            reactedByCurrentUser: matchingReactions.some(
                (reaction) => reaction.user === currentUsername
            ),
        }
    }).filter((group) => group.count > 0);

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
        {/* Existing reactions */}
        {groupedReactions.map((group) => (
            <button
            key={group.emoji}
            type="button"
            disabled={disabled}
            onClick={() => onReact(group.emoji)}
            title={group.users.join(", ")}
            className={`flex items-center gap-1 rounded-full border px-2 py-1 text-xs transition
                ${group.reactedByCurrentUser ? "border-blue-500 bg-blue-500/20 text-blue-300" : "border-slate-700 bg-slate-800 text-slate-300"}`}
            >
                <span>{group.emoji}</span>
                <span>{group.count}</span>
            </button>
        ))}

        {/* Available emojis */}

        <div className="flex items-center gap-1">
            {
                EMOJIS.map((emoji) => (
                    <button
                    key={emoji}
                    type="button"
                    disabled={disabled}
                    onClick={() => onReact(emoji)}
                    title={`React with ${emoji}`}
                    className="rounded-full p-1 text-sm transition hover:bg-slate-700 disabled:opacity-50"
                    >
                        {emoji}
                    </button>
                ))
            }
        </div>
    </div>
  )
}

export default MessageReactions