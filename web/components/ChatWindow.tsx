"use client"; // this component runs in the visitor's browser, not on our
              // server -- required because it reacts to typing/clicking.

import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import { streamChat } from "@/lib/stream-client";

type Message = {
    role: "user" | "assistant";
    text: string;
};

export default function ChatWindow({ sessionId }: { sessionId: string }) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }, [messages]);

      async function handleSend() {
        const text = input.trim();
        if (!text || isSending) return;
    
        setInput("");
        setIsSending(true);
    
        // Add the guest's own message right away, then add an EMPTY
        // assistant message that we'll fill in bit by bit as chunks arrive.
        setMessages((prev) => [...prev, { role: "user", text }, { role: "assistant", text: "" }]);
    
        try {
          for await (const chunk of streamChat(sessionId, text)) {
            // Glue this chunk onto the end of the assistant's in-progress
            // reply (the last message), instead of replacing it.
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, text: last.text + chunk };
              return updated;
            });
          }
        } catch {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: "Sorry, something went wrong. Please try again." },
          ]);
        } finally {
          setIsSending(false);
        }
      }

    return (
    <div className="flex flex-col h-full max-w-2xl mx-auto p-4">
        <div className="flex-1 overflow-y-auto mb-4">
        {messages.map((m, i) => (
            <MessageBubble key={i} role={m.role} text={m.text} />
        ))}
        <div ref={bottomRef} />
        </div>
        <div className="flex gap-2">
        <input
          className="flex-1 border rounded-full px-4 py-2 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          disabled={isSending}
        />
        <button
            className="bg-blue-600 text-white rounded-full px-5 py-2 disabled:opacity-50"
            onClick={handleSend}
            disabled={isSending}
        >
            Send
        </button>
        </div>
    </div>
    );

}