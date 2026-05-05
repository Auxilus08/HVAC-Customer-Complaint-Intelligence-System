import client from "./client";

export const getAlerts = () => client.get("/alerts");
