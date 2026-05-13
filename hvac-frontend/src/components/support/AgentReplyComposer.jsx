import { useState } from "react";
import { Send } from "lucide-react";
import { useReplyToTicket } from "../../hooks/useSupport";
import Spinner from "../ui/Spinner";

export default function AgentReplyComposer({ ticketId, disabled }) {
  const [text, setText] = useState("");
  const reply = useReplyToTicket();

  const submit = (e) => {
    e?.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || reply.isPending) return;
    reply.mutate(
      { ticketId, text: trimmed },
      {
        onSuccess: () => setText(""),
      }
    );
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      submit();
    }
  };

  return (
    <form
      onSubmit={submit}
      className="border-t border-surface-border bg-surface p-3 flex flex-col gap-2"
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={
          disabled
            ? "Ticket closed — reopen to reply"
            : "Type your reply to the customer… (⌘/Ctrl+Enter to send)"
        }
        rows={3}
        disabled={disabled || reply.isPending}
        className="w-full resize-none border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-900 placeholder:text-ink-500 focus:outline-none focus:ring-2 focus:ring-carrier/40 disabled:bg-ink-100 disabled:cursor-not-allowed"
      />
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs text-ink-500">
          {reply.isError ? (
            <span className="text-status-critical">
              {reply.error?.message || "Send failed"}
            </span>
          ) : (
            <span>Reply will be sent via Telegram to the customer.</span>
          )}
        </div>
        <button
          type="submit"
          disabled={disabled || reply.isPending || !text.trim()}
          className="bg-carrier text-white px-4 py-2 rounded-md text-sm font-medium inline-flex items-center gap-2 hover:bg-carrier-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {reply.isPending ? (
            <Spinner size="sm" color="text-white" />
          ) : (
            <Send className="w-4 h-4" />
          )}
          Send reply
        </button>
      </div>
    </form>
  );
}
