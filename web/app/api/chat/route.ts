import {NextRequest} from "next/server";



const AGENT_URL = process.env.AGENT_URL || "http://localhost:8000";
const APP_NAME = "concierge_agent";


export async function POST(req: NextRequest){
    const body = await req.json();
    const { session_id } = body;

    if (!session_id) {
        return new Response(JSON.stringify({ error: "Missing session_id." }), {
            status: 400,
            headers: { "Content-Type": "application/json" },
        });
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

    const sessionRes = await fetch(
        `${AGENT_URL}/apps/${APP_NAME}/users/${session_id}/sessions/${session_id}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }
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
        headers: { "Content-Type": "application/json" },
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