const WINDOW_MS = 5 * 60 * 1000; // 5 minutes
const MAX_REQUESTS_PER_WINDOW = 20;

type RateEntry = { count: number; windowStart: number };

const requestCounts = new Map<string, RateEntry>();

// Returns true if this session may send another message right now, and
// records the attempt -- call this exactly once per real request.
export function checkRateLimit(sessionId: string): boolean {
  const now = Date.now();
  const entry = requestCounts.get(sessionId);

  if (!entry || now - entry.windowStart > WINDOW_MS) {
    // First request ever for this session, or the previous window fully
    // expired -- start a fresh window.
    requestCounts.set(sessionId, { count: 1, windowStart: now });
    return true;
  }

  if (entry.count >= MAX_REQUESTS_PER_WINDOW) {
    return false;
  }

  entry.count += 1;
  return true;
}