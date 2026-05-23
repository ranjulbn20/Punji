const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

let socket: WebSocket | null = null;
let pingInterval: ReturnType<typeof setInterval> | null = null;
const listeners: Map<string, ((data: unknown) => void)[]> = new Map();

export function connectWebSocket(userId: string, token: string) {
  if (socket?.readyState === WebSocket.OPEN) return;

  socket = new WebSocket(`${WS_BASE}/ws/${userId}?token=${token}`);

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      const fns = listeners.get(msg.type) || [];
      fns.forEach((fn) => fn(msg.data));
    } catch {}
  };

  socket.onopen = () => {
    pingInterval = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "pong" }));
      }
    }, 30000);
  };

  socket.onclose = () => {
    if (pingInterval) clearInterval(pingInterval);
    // Reconnect after 5 seconds
    setTimeout(() => connectWebSocket(userId, token), 5000);
  };
}

export function onWsMessage(type: string, fn: (data: unknown) => void) {
  if (!listeners.has(type)) listeners.set(type, []);
  listeners.get(type)!.push(fn);
  return () => {
    const fns = listeners.get(type) || [];
    listeners.set(type, fns.filter((f) => f !== fn));
  };
}

export function disconnectWebSocket() {
  if (pingInterval) clearInterval(pingInterval);
  socket?.close();
  socket = null;
}
