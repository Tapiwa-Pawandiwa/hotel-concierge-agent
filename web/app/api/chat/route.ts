import {NextRequest} from "next/server";
import { checkRateLimit } from "@/lib/rate-limit";



const AGENT_URL = process.env.AGENT_URL || "http://localhost:8000";
const APP_NAME = "concierge_agent";

// Cloud Run's own metadata server hands out a signed identity token scoped
// to a specific target service (the "audience") -- this is how one Cloud
// Run service proves its identity to another private one, no API key
// needed. This server only exists when actually running ON Cloud Run, so
// locally (npm run dev) the fetch simply fails and we return null --
// meaning "call the agent with no auth," which is correct for a plain
// localhost:8000 dev server.
async function getIdentityToken(audience: string): Promise<string | null> {
    try {
        const res = await fetch(
            `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(audience)}`,
            { headers: { "Metadata-Flavor": "Google" }, signal: AbortSignal.timeout(2000) }
        );
        if (!res.ok) return null;
        return await res.text();
    } catch {
        return null;
    }
}

export async function POST(req: NextRequest){
    const body = await req.json();
    const { session_id } = body;


    if (!session_id) {
        return new Response(JSON.stringify({ error: "Missing session_id." }), {
            status: 400,
            headers: { "Content-Type": "application/json" },
        });
    }
    
    if (!checkRateLimit(session_id)) {
        return new Response(
            JSON.stringify({ error: "You're sending messages a bit fast — please wait a moment and try again." }),
            { status: 429, headers: { "Content-Type": "application/json" } }
        );
    }


    // Two possible shapes: a normal typed message, or an answer to a
    // pending Tier-3 confirmation -- these need different "parts" sent to
    // the agent (plain text vs. a structured FunctionResponse).
    let parts;
    if (body.confirmation) {
        const { id, confirmed } = body.confirmation;
        if (!id || typeof confirmed !== "boolean") {
            return new Response(JSON.stringify({ error: "Malformed confirmation." }), {
                status: 400,
                headers: { "Content-Type": "application/json" },
            });
        }
        parts = [{ function_response: { id, name: "adk_request_confirmation", response: { confirmed } } }];
    } else if (typeof body.message === "string" && body.message.trim()) {
        parts = [{ text: body.message }];
    } else {
        return new Response(JSON.stringify({ error: "Missing message or confirmation." }), {
            status: 400,
            headers: { "Content-Type": "application/json" },
        });
    }

    // null when running locally (no metadata server) -- the agent's own
    // localhost:8000 dev server takes plain, unauthenticated calls.
    const identityToken = await getIdentityToken(AGENT_URL);
    const authHeader: Record<string, string> = identityToken
        ? { Authorization: `Bearer ${identityToken}` }
        : {};

    const sessionRes = await fetch(
        `${AGENT_URL}/apps/${APP_NAME}/users/${session_id}/sessions/${session_id}`,
        { method: "POST", headers: { "Content-Type": "application/json", ...authHeader }, body: "{}" }
    );

    if (!sessionRes.ok && sessionRes.status !== 409) {
        console.error("Session create failed:", sessionRes.status, await sessionRes.text().catch(() => ""));
        return new Response(
            JSON.stringify({ error: "The concierge is temporarily unavailable. Please try again in a few minutes" }),
            { status: 502, headers: { "Content-Type": "application/json" } }
        );
    }

    const runRes = await fetch(`${AGENT_URL}/run_sse`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({
            app_name: APP_NAME,
            user_id: session_id,
            session_id: session_id,
            new_message: { role: "user", parts },
            streaming: true,
        }),
    });

    if (!runRes.ok || !runRes.body) {
        console.error("run_sse failed:", runRes.status, await runRes.text().catch(() => ""));
        return new Response(
            JSON.stringify({ error: "The concierge is temporarily unavailable. Please try again in a moment." }),
            { status: 502, headers: { "Content-Type": "application/json" } }
        );
    }

    return new Response(runRes.body, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
    });
}