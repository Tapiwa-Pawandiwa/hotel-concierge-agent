type MessageBubbleProps = {
    role: "user" | "assistant";
    text: string;
  };

export default function MessageBubble({ role, text }: MessageBubbleProps) {
    const isUser = role === "user";
    return (
      <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
        <div
          className={`max-w-[75%] rounded-2xl px-4 py-2 whitespace-pre-wrap ${
            isUser ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
          }`}
        >
          {text}
        </div>
      </div>
    );
}



