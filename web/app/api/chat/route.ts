import {NextRequest} from "next/server";



const AGENT_URL = process.env.AGENT_URL || "http://localhost:8000";
const APP_NAME = "concierge_agent";


export async function POST(req: NextRequest){
    const {session_id, message} = await req.json();

    if (!session_id || typeof message !== "string" || !message.trim()){
        return new Response(JSON.stringify({error: "Missing session_id or message"}), {
            status: 400,
            headers: {"Content-Type": "application/json"},
        })
    }

    const sessionRes = await fetch(
        `${AGENT_URL}/apps/${APP_NAME}/users/${session_id}/sessions/${session_id}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }
    ); 
    if(!sessionRes.ok){
        return new Response(
            JSON.stringify({error: "The concierge is temporarily unavailable. Please try again in a few minutes"}),
            {status: 502, headers: {"Content-Type": "application/json"}}
        );
    }

    const runRes = await fetch(`${AGENT_URL}/run_sse`,{
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            app_name: APP_NAME,
            user_id: session_id,
            session_id: session_id,
            new_message: {role: "user", parts: [{text: message}]},
            streaming : true, 
        })
    });

    if (!runRes.ok || !runRes.body){
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