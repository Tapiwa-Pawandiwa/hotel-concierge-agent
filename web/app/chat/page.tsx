"use client";
import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import ChatHeader from "@/components/ChatHeader";
import SideBar from "@/components/SideBar";

export default function ChatPage() {
  const [sessionId] = useState(() => crypto.randomUUID());
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="h-screen flex bg-janet-ivory overflow-hidden">
      <SideBar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        <ChatHeader onMenuClick={() => setSidebarOpen(true)} />
        <div className="flex-1 overflow-hidden">
          <ChatWindow sessionId={sessionId} />
        </div>
      </main>
    </div>
  );
}