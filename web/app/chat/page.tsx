"use client"; // needs to run in the browser, since it creates a random ID
// and passes it to ChatWindow.
import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import ChatHeader from "@/components/ChatHeader";
import Sidebar from "@/components/SideBar";

export default function ChatPage() {
  // Generate ONE random ID per visit, the moment the page loads (FR-009 —
  // never saved to localStorage/cookies, so it's gone the moment the tab
  // closes).
  const [sessionId] = useState(() => crypto.randomUUID());

  return (
    <div className="h-screen flex bg-janet-ivory">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <ChatHeader />
        <div className="flex-1 overflow-hidden">
          <ChatWindow sessionId={sessionId} />
        </div>
      </main>
    </div>
  );
}