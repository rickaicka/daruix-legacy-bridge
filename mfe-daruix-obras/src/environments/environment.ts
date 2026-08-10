const apiHost = window.location.hostname;

export const environment = {
  production: false,
  apiUrl: `http://${apiHost}:8000/api`,
} as const;
