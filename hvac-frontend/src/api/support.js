import client from "./client";

export const listTickets = (statusFilter) =>
  client.get("/support/tickets", {
    params: statusFilter ? { status: statusFilter } : {},
  });

export const getTicket = (ticketId) =>
  client.get(`/support/tickets/${ticketId}`);

export const replyToTicket = (ticketId, text) =>
  client.post(`/support/tickets/${ticketId}/reply`, { text });

export const resolveTicket = (ticketId) =>
  client.post(`/support/tickets/${ticketId}/resolve`);

