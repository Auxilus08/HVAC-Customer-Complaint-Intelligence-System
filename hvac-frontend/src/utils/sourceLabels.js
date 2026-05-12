export const SOURCE_LABELS = {
  nyc_311: "NYC city service requests",
  synthetic: "Test data",
  cpsc: "CPSC product safety reports",
  app_store: "Carrier app reviews",
  crm: "CRM tickets",
  email: "Email",
  whatsapp: "WhatsApp",
  app: "Mobile app",
  field_tech: "Field tech",
  call_center: "Call center",
};

export const sourceLabel = (key) => SOURCE_LABELS[key] ?? key;
