import os
from google.adk.tools.tool_context import ToolContext
import psycopg
from pgvector.psycopg import register_vector
import voyageai
from psycopg.types.json import Jsonb
from google.adk.tools import ToolContext
from dotenv import load_dotenv
import uuid

load_dotenv()

vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])
register_vector(conn)


def check_idempotency(cur, key: str, tool_name: str) -> dict | None:
    """Looks up prior result for this(key, tool_name) pair in the idempotency table.
    Call this FIRST in any write tool, before doing the write , using the same cursor the write itself will use
    If this returns a dict, return it to the agent immediately , verbatim, and skip the write ,
    it already happened on an earlier call with this same key.
    """

    cur.execute(
        "SELECT result FROM idempotency_keys WHERE key = %s AND tool_name = %s",
        (key, tool_name),
    )
    row = cur.fetchone()
    # psycopg auto-converts a jsonb column back to a Python dict on read
    if row is None:
        return None
    return row[0]


def record_idempotency(cur, key: str, tool_name: str, result: dict) -> None:
    """
    Records a key, tool_name, result pair in the idempotency table after a write succeeds.
    Call this AFTER the write, with the SAME cursor the write used, and only commit once after this call.
    That puts the write and the record of it in one transaction: if the proceess dies between the write and this call , nothing comitted
    """

    cur.execute(
        "INSERT INTO idempotency_keys (key, tool_name, result) VALUES (%s, %s, %s)",
        (key, tool_name, Jsonb(result)),
    )


def retrieve_hotel_policy(question: str) -> dict:
    """Searches the hotels policy documents for information relevant to a guests question.

    Use this whenever a guest asks about hotel rules, check-in/out times, cancellation,pets breakfast, parking, or similiar policy questions.
    Args:
        questions: The guests question , in their words
    Returns:
        A dictionary with the matched policy text and which source file it came from
    """

    cur = conn.cursor()
    # SQL, sent to Postgres via psycopg — not Python code itself.
    # %s is a psycopg placeholder, safely filled with q_emb (not string formatting).
    # <=> is a pgvector operator: cosine distance between two vectors (smaller = more similar).
    # Meaning: "give me the 2 policy chunks whose embedding is closest to the guest's question."
    q_emb = vo.embed(
        [question], model="voyage-3.5-lite", input_type="query", output_dimension=1024
    ).embeddings[0]
    cur.execute(
        "SELECT source_file, content FROM policy_chunks ORDER by embedding <=> %s::vector limit 2",
        (q_emb,),
    )
    rows = cur.fetchall()
    cur.close()
    return {
        "status": "success",
        "matches": [{"source": r[0], "text": r[1]} for r in rows],
    }


def verify_guest_identity(
    booking_reference: str, surname: str, tool_context: ToolContext
) -> dict:
    """Verifies a guest's identity via booking reference + surname.

    Call this FIRST, before answering any guest-specific question or taking any
    guest-specific action (booking details, check-in/out, modifying or canceling
    a reservation). Never skip this or guess at the guest's identity.

    Args:
        booking_reference: The reservation's booking reference, e.g. "BK-G0001".
        surname: The guest's last name, as given by the guest.

    Returns:
        On match: {"status": "ok", "data": {"guest_id", "verified": True, "reservation_status"}}
        On any non-match: {"status": "error", "error": "..."} — deliberately generic, never
        says which field was wrong, so failed attempts can't be used to probe for valid
        booking references.
    """
    failures = tool_context.state.get("verify_guest_identity_failures", 0)
    if failures >= 3:
        return {
            "status": "error",
            "error": "Too many failed verification attempts. Please contact the front desk directly.",
        }

    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.status, g.id, g.last_name
        FROM reservations r
        JOIN guests g ON g.id = r.guest_id
        WHERE r.booking_reference = %s
        """,
        (booking_reference,),
    )
    row = cur.fetchone()
    cur.close()

    # Case/whitespace-insensitive match, and both values must point at the SAME
    # reservation — checked in one query, not two separate lookups, so a real
    # booking_reference can't be paired with an unrelated guest's surname.
    if row is None or row[2].strip().lower() != surname.strip().lower():
        tool_context.state["verify_guest_identity_failures"] = failures + 1
        return {
            "status": "error",
            "error": "Could not verify identity — please check the booking reference and surname.",
        }

    reservation_status, guest_id, _ = row
    return {
        "status": "ok",
        "data": {
            "guest_id": str(guest_id),
            "verified": True,
            "reservation_status": reservation_status,
        },
    }


def check_in_guest(idempotency_key: str, booking_reference: str) -> dict:
    """
    Checks a guest into an available room for their reservation

    Call this only after verify_guest_identity has succeeded for this guest in this conversation.
    Requires the reservation to be confirmed.

    Args:
        idempotency_key: a UUID string generated once per logical checkin attempt.
        Retrying with the SAME key returns the original result instead of assigning a second room.
        booking_reference: the reservation's booking reference e.g "BK-xxxx"

    Returns:
        On success {"status": "ok", "data":{"room_id","floor","view_type","reservation_status": "checked_in"}}
        On failure: {"status": "error", "error": "..."} reservation not
        found, not 'confirmed', or no room of the required type is free.
    """

    cur = conn.cursor()
    tool_name = "check_in_guest"

    # idempotency check FIRST before touching any reservation
    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None:
        cur.close()
        return cached

    cur.execute(
        "SELECT status, room_type_id FROM reservations WHERE booking_reference = %s FOR UPDATE",
        (booking_reference,),
    )
    resv = cur.fetchone()
    if resv is None:
        result = {
            "status": "error",
            "error": f"No reservation found for {booking_reference}.",
        }
    else:
        status, room_type_id = resv
        if status != "confirmed":
            result = {
                "status": "error",
                "error": f"Reservation is '{status}', not 'confirmed' — cannot check in.",
            }
        else:
            cur.execute(
                """
                SELECT rm.id, rm.room_number, rm.view_type, rt.name
                FROM rooms rm
                JOIN room_types rt ON rt.id = rm.room_type_id
                WHERE rm.room_type_id = %s AND rm.occupancy_status = 'vacant'
                LIMIT 1 FOR UPDATE
                """,
                (room_type_id,),
            )
            room = cur.fetchone()
            if room is None:
                result = {"status": "error", "error": "No room of the required type is currently available."}
            else:
                room_id, room_number, view_type, room_type_name = room
                cur.execute(
                    "UPDATE reservations SET room_id = %s, status = 'checked_in' WHERE booking_reference = %s", 
                   (room_id, booking_reference),
                )
                cur.execute(
                    "UPDATE rooms SET occupancy_status = 'occupied' WHERE id = %s",
                    (room_id,),
                )
                result = {
                    "status": "ok",
                    "data": {
                        "room_id": str(room_id),  # kept for internal/DB use, not for the guest
                        "room_number": room_number,
                        "room_type": room_type_name,
                        "view_type": view_type,
                        "reservation_status": "checked_in",
                    },
                }
                

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close
    return result


def check_out_guest(idempotency_key: str, booking_reference: str) -> str:
    """Checks a guest out and releases their room for housekeeping.
    Requires the reservation to currently be 'checked_in'
     Args:
        idempotency_key: a UUID string generated once per logical check-out
            attempt. Retrying with the same key returns the original result
            instead of releasing the room a second time.
        booking_reference: the reservation's booking reference, e.g. "BK-G0001".

    Returns:
        On success: {"status": "ok", "data": {"reservation_status": "checked_out"}}
        On failure: {"status": "error", "error": "..."} — reservation not
        found, or not currently checked in.
    """
    cur = conn.cursor()
    tool_name = "check_out_guest"

    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None:
        cur.close()
        return cached

    cur.execute(
        "SELECT status, room_id FROM reservations WHERE booking_reference = %s FOR UPDATE",
        (booking_reference,),
    )
    resv = cur.fetchone()

    if resv is None:
        result = {
            "status": "error",
            "error": f"No reservation found for {booking_reference}.",
        }
    else:
        status, room_id = resv
        if status != "checked_in":
            result = {
                "status": "error",
                "error": f"Reservation is '{status}', not 'checked_in' — cannot check out.",
            }
        else:
            cur.execute(
                "UPDATE reservations SET status = 'checked_out' WHERE booking_reference = %s",
                (booking_reference,),
            )
            cur.execute(
                "UPDATE rooms SET occupancy_status = 'vacant', housekeeping_status = 'needs_cleaning' WHERE id = %s",
                (room_id,),
            )
            result = {"status": "ok", "data": {"reservation_status": "checked_out"}}

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

def create_booking(
    idempotency_key: str, 
    guest_id: str, 
    room_type_id: str,
    check_in_date: str,
    check_out_date: str,
)-> dict: 
    """
    Creates a new reservation for an existing guest
     Args:
        idempotency_key: a unique string generated once per logical booking
            attempt. Retrying with the same key returns the original result
            instead of creating a second reservation.
        guest_id: the guest's id (a UUID string) this booking belongs to.
        room_type_id: which room type to book (a UUID string).
        check_in_date: an ISO date string, e.g. "2026-09-01".
        check_out_date: an ISO date string. Must be after check_in_date.

    Returns:
        On success: {"status": "ok", "data": {"booking_reference": ...}}
        On failure: {"status": "error", "error": "..."} — invalid dates, or no
        room of the requested type is free for the entire requested range.

    """

    cur = conn.cursor()
    tool_name = "create_booking"

    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None: 
        cur.close()
        return cached 
    
    if check_out_date <= check_in_date:
        result ={"status":"error","error": "Check-out date must be after check-in date."}
    else: 
         # Availability across the WHOLE requested date range, not just "does this
        # room type exist." Half-open interval: check_in_date is inclusive,
        # check_out_date is exclusive, so a guest checking out on day X and a new
        # guest checking in on day X are not treated as overlapping.
        cur.execute(
            """
            SELECT
                (SELECT count(*) FROM rooms WHERE room_type_id = %s)
              - (SELECT count(*) FROM reservations
                 WHERE room_type_id = %s
                   AND status IN ('confirmed', 'checked_in')
                   AND check_in_date < %s
                   AND check_out_date > %s)
            """,
            (room_type_id, room_type_id, check_out_date, check_in_date),
            
        )
        rooms_free = cur.fetchone()[0]

        if rooms_free <= 0:
            result = {"status": "error", "error": "No room of the requested type is available for those dates."}
        else:
            booking_reference = "BK-" + str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO reservations
                    (booking_reference, guest_id, room_type_id, check_in_date, check_out_date, status)
                VALUES (%s, %s, %s, %s, %s, 'confirmed')
                """,
                (booking_reference, guest_id, room_type_id, check_in_date, check_out_date),
            )
            result = {"status": "ok", "data": {"booking_reference": booking_reference}}

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result
