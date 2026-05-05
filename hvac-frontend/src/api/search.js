import client from "./client";

export const searchComplaints = (params = {}) =>
  client.get("/complaints/search", { params });
