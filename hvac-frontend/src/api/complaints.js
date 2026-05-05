import client from "./client";

export const uploadCSV = (file) => {
  const form = new FormData();
  form.append("file", file);
  return client.post("/complaints/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const uploadJSON = (complaints) =>
  client.post("/complaints/upload", { complaints });
