window.__AGENTSTUDIO_CONFIG__ = {
  BACKEND_HOST: window.location.hostname,
  BACKEND_PORT: 8001,
  FRONTEND_PORT: 5173,
  API_BASE_URL: window.location.protocol + '//'+ window.location.hostname + ':8001/api',
  WS_BASE_URL: (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + window.location.hostname + ':8001/api/ws',
  AGENTSTUDIO_ROOT: "F:\\Source\\repos\\Theanova\\AI\\AgentStudio"
};
