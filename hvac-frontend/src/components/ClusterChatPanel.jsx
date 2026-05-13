import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, User, X, Minus } from "lucide-react";
import { useClusterChat } from "../hooks/useClusterChat";
import Spinner from "./ui/Spinner";

const STARTER_QUESTIONS = [
  "What's driving the recent spike in this cluster?",
  "Which regions and SKUs should I prioritise?",
  "Summarise the most common symptom in one sentence.",
  "What action items should I assign to the field team?",
];

function MessageRow({ role, content }) {
  const isUser = role === "user";
  return (
    <div className={`flex gap-2 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div
        className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${
          isUser ? "bg-carrier text-white" : "bg-ink-100 text-ink-700"
        }`}
      >
        {isUser ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
      </div>
      <div
        className={`max-w-[80%] px-3 py-2 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap ${
          isUser
            ? "bg-carrier text-white rounded-tr-sm"
            : "bg-surface border border-surface-border text-ink-900 rounded-tl-sm"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

export default function ClusterChatPanel({ clusterId, clusterLabel }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const chat = useClusterChat(clusterId);

  // Reset history when the user opens a different cluster
  useEffect(() => {
    setMessages([]);
    setDraft("");
    setIsOpen(false);
  }, [clusterId]);

  // Scroll to bottom whenever messages change or while pending
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, chat.isPending]);

  // Focus input when window opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [isOpen]);

  const send = (text) => {
    const trimmed = (text ?? draft).trim();
    if (!trimmed || chat.isPending) return;

    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    const userMsg = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setDraft("");

    chat.mutate(
      { message: trimmed, history },
      {
        onSuccess: (data) => {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: data?.reply || "(empty reply)" },
          ]);
        },
        onError: (err) => {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: `Sorry — analysis failed: ${err?.message || "unknown error"}`,
              isError: true,
            },
          ]);
        },
      }
    );
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      send();
    }
  };

  const unreadDot = !isOpen && messages.length > 0;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {/* Chat window */}
      {isOpen && (
        <div
          className="w-80 bg-surface border border-surface-border rounded-2xl shadow-2xl flex flex-col overflow-hidden"
          style={{ height: "440px" }}
        >
          {/* Header */}
          <header className="px-4 py-3 bg-carrier flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <Sparkles className="w-4 h-4 text-white shrink-0" />
              <div className="min-w-0">
                <div className="text-sm font-semibold text-white leading-tight">
                  Analytics co-pilot
                </div>
                <div className="text-[10px] text-white/70 truncate">
                  {clusterLabel || `Cluster #${clusterId}`}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button
                  onClick={() => { setMessages([]); setDraft(""); }}
                  disabled={chat.isPending}
                  title="Clear chat"
                  className="p-1 rounded hover:bg-white/20 text-white/70 hover:text-white transition-colors disabled:opacity-40"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded hover:bg-white/20 text-white/70 hover:text-white transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </header>

          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5 bg-surface-soft"
          >
            {messages.length === 0 ? (
              <div className="text-xs text-ink-500">
                <p className="mb-2 font-medium">Try asking:</p>
                <ul className="space-y-1.5">
                  {STARTER_QUESTIONS.map((q) => (
                    <li key={q}>
                      <button
                        onClick={() => send(q)}
                        className="text-left text-xs text-carrier hover:underline leading-snug"
                      >
                        {q}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              messages.map((m, i) => (
                <MessageRow key={i} role={m.role} content={m.content} />
              ))
            )}
            {chat.isPending && (
              <div className="flex items-center gap-1.5 text-xs text-ink-500 pl-8">
                <Spinner size="sm" /> Thinking…
              </div>
            )}
          </div>

          {/* Input */}
          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            className="border-t border-surface-border p-2.5 flex gap-2 bg-surface shrink-0"
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ask about this cluster…"
              disabled={chat.isPending}
              className="flex-1 resize-none border border-surface-border rounded-lg px-2.5 py-1.5 text-xs text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-carrier/40 disabled:bg-ink-100 leading-snug"
              style={{ minHeight: "32px", maxHeight: "72px" }}
            />
            <button
              type="submit"
              disabled={chat.isPending || !draft.trim()}
              className="bg-carrier text-white px-2.5 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1 hover:bg-carrier-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              {chat.isPending ? (
                <Spinner size="sm" color="text-white" />
              ) : (
                <Send className="w-3.5 h-3.5" />
              )}
            </button>
          </form>
        </div>
      )}

      {/* Trigger button */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="relative flex items-center gap-2 bg-carrier hover:bg-carrier-dark text-white px-4 py-2.5 rounded-full shadow-lg font-medium text-sm transition-all hover:shadow-xl active:scale-95"
      >
        <Sparkles className="w-4 h-4" />
        Co-pilot
        {unreadDot && (
          <span className="absolute -top-1 -right-1 w-3 h-3 bg-high rounded-full border-2 border-white" />
        )}
      </button>
    </div>
  );
}
