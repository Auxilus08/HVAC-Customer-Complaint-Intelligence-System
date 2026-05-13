import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, Inbox, MessageSquare } from "lucide-react";
import {
  useResolveTicket,
  useSupportTicket,
  useSupportTickets,
} from "../hooks/useSupport";
import { asArray } from "../utils/format";
import EmptyState from "./ui/EmptyState";
import Spinner from "./ui/Spinner";
import AgentReplyComposer from "./support/AgentReplyComposer";
import MessageBubble from "./support/MessageBubble";
import ProductInfoPanel from "./support/ProductInfoPanel";
import TicketListItem from "./support/TicketListItem";

const FILTERS = [
  { value: null, label: "All" },
  { value: "escalated", label: "Escalated" },
  { value: "agent_active", label: "Agent active" },
  { value: "bot_collecting", label: "Bot active" },
  { value: "bot_resolved", label: "Bot resolved" },
  { value: "closed", label: "Closed" },
];

export default function SupportInboxView() {
  const { ticketId: ticketIdParam } = useParams();
  const navigate = useNavigate();
  const [filter, setFilter] = useState(null);
  const messagesEndRef = useRef(null);

  const ticketsQuery = useSupportTickets(filter);
  const tickets = useMemo(() => {
    const raw = ticketsQuery.data?.tickets;
    return Array.isArray(raw) ? raw : asArray(ticketsQuery.data);
  }, [ticketsQuery.data]);

  const selectedId = ticketIdParam ? Number(ticketIdParam) : null;
  const ticketQuery = useSupportTicket(selectedId);
  const ticket = ticketQuery.data;

  const resolve = useResolveTicket();

  // Auto-select first ticket on load if none is selected
  useEffect(() => {
    if (selectedId == null && tickets.length > 0) {
      navigate(`/inbox/${tickets[0].id}`, { replace: true });
    }
  }, [selectedId, tickets, navigate]);

  // Scroll thread to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ block: "end" });
    }
  }, [ticket?.messages?.length]);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left pane: list */}
      <aside className="w-[340px] flex-shrink-0 border-r border-surface-border bg-surface flex flex-col">
        <div className="px-4 py-3 border-b border-surface-border">
          <h2 className="text-sm font-semibold text-ink-900 flex items-center gap-2">
            <Inbox className="w-4 h-4" />
            Support Inbox
          </h2>
          <p className="text-xs text-ink-500 mt-0.5">
            Telegram conversations — live updates every 5s.
          </p>
        </div>
        <div className="px-3 py-2 flex flex-wrap gap-1 border-b border-surface-border">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => setFilter(f.value)}
              className={`text-xs px-2.5 py-1 rounded-full font-medium transition-colors ${
                filter === f.value
                  ? "bg-carrier text-white"
                  : "bg-ink-100 text-ink-700 hover:bg-ink-300/40"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto">
          {ticketsQuery.isLoading ? (
            <div className="flex items-center justify-center py-10">
              <Spinner />
            </div>
          ) : ticketsQuery.isError ? (
            <div className="p-4 text-sm text-status-critical">
              Failed to load tickets: {ticketsQuery.error?.message}
            </div>
          ) : tickets.length === 0 ? (
            <EmptyState
              icon={<MessageSquare className="w-10 h-10" />}
              title="No tickets yet"
              description={
                filter
                  ? "No tickets match this filter."
                  : "When customers message your Telegram bot, conversations will appear here."
              }
            />
          ) : (
            tickets.map((t) => (
              <TicketListItem
                key={t.id}
                ticket={t}
                selected={t.id === selectedId}
                onClick={() => navigate(`/inbox/${t.id}`)}
              />
            ))
          )}
        </div>
      </aside>

      {/* Right pane: thread */}
      <section className="flex-1 flex flex-col min-w-0 bg-surface-soft">
        {!selectedId ? (
          <EmptyState
            icon={<Inbox className="w-12 h-12" />}
            title="Select a ticket"
            description="Pick a conversation from the list to see the message thread."
          />
        ) : ticketQuery.isLoading ? (
          <div className="flex items-center justify-center flex-1">
            <Spinner />
          </div>
        ) : ticketQuery.isError ? (
          <div className="p-6 text-sm text-status-critical">
            Failed to load ticket: {ticketQuery.error?.message}
          </div>
        ) : ticket ? (
          <>
            <div className="border-b border-surface-border bg-surface px-6 py-3 flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="text-xs uppercase tracking-wide text-ink-500 mb-1">
                  Ticket #{ticket.id} ·{" "}
                  <span className="text-ink-700 font-medium">
                    {ticket.status.replace(/_/g, " ")}
                  </span>
                </div>
                <ProductInfoPanel
                  matchedProduct={ticket.matched_product}
                  gatheredInfo={ticket.gathered_info}
                />
                {ticket.escalation_reason ? (
                  <div className="text-xs text-status-critical mt-2">
                    Escalation reason: {ticket.escalation_reason}
                  </div>
                ) : null}
                {ticket.complaint_id ? (
                  <div className="text-xs text-ink-500 mt-1">
                    Linked complaint #{ticket.complaint_id} (clustering in
                    progress)
                  </div>
                ) : null}
              </div>
              <button
                onClick={() => resolve.mutate(ticket.id)}
                disabled={
                  ticket.status === "closed" || resolve.isPending
                }
                className="bg-status-positive/10 text-status-positive border border-status-positive/30 px-3 py-1.5 rounded-md text-sm font-medium inline-flex items-center gap-1.5 hover:bg-status-positive/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                <CheckCircle2 className="w-4 h-4" />
                {ticket.status === "closed" ? "Closed" : "Mark resolved"}
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              {ticket.messages.length === 0 ? (
                <EmptyState
                  title="No messages yet"
                  description="The conversation hasn't started."
                />
              ) : (
                ticket.messages.map((m) => (
                  <MessageBubble key={m.id} message={m} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            <AgentReplyComposer
              ticketId={ticket.id}
              disabled={ticket.status === "closed"}
            />
          </>
        ) : (
          <EmptyState title="Ticket not found" />
        )}
      </section>
    </div>
  );
}
