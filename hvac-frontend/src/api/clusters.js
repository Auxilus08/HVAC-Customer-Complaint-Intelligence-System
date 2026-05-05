import client from "./client";

export const getClusters = (params = {}) =>
  client.get("/clusters", { params });

export const getClusterDetail = (id) => client.get(`/clusters/${id}`);

export const getAdvisory = (id) => client.get(`/clusters/${id}/advisory`);

export const getClusterTrend = (id, days = 30) =>
  client.get(`/clusters/${id}/trend`, { params: { days } });
