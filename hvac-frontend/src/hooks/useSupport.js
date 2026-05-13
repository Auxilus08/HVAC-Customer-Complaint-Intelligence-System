import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getTicket,
  listTickets,
  replyToTicket,
  resolveTicket,
} from "../api/support";

const TICKETS_KEY = "support-tickets";
const TICKET_KEY = "support-ticket";

export const useSupportTickets = (statusFilter = null) =>
  useQuery({
    queryKey: [TICKETS_KEY, statusFilter ?? "all"],
    queryFn: () => listTickets(statusFilter),
    refetchInterval: 5_000,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
  });

export const useSupportTicket = (ticketId) =>
  useQuery({
    queryKey: [TICKET_KEY, ticketId],
    queryFn: () => getTicket(ticketId),
    enabled: Boolean(ticketId),
    refetchInterval: 5_000,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
  });

export const useReplyToTicket = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ticketId, text }) => replyToTicket(ticketId, text),
    onSuccess: (_, { ticketId }) => {
      qc.invalidateQueries({ queryKey: [TICKET_KEY, ticketId] });
      qc.invalidateQueries({ queryKey: [TICKETS_KEY] });
    },
  });
};

export const useResolveTicket = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ticketId) => resolveTicket(ticketId),
    onSuccess: (_, ticketId) => {
      qc.invalidateQueries({ queryKey: [TICKET_KEY, ticketId] });
      qc.invalidateQueries({ queryKey: [TICKETS_KEY] });
    },
  });
};
