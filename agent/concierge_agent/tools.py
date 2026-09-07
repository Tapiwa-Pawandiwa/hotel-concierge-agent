import os
from dotenv.main import resolve_variables
from google.adk.tools.tool_context import ToolContext
import psycopg
from pgvector.psycopg import register_vector
import voyageai
from psycopg.types.json import Jsonb
from google.adk.tools import ToolContext
from dotenv import load_dotenv
import uuid
import datetime
import functools

load_dotenv()

vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

_conn: psycopg.Connection | None = None

def get_conn() -> psycopg.Connection:
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])
        register_vector(_conn)
    return _conn

def safe_tool(fn):
    """Wraps every agent-facing tool that touches the database so an
    unexpected exception can never reach the guest as a raw crash, and
    can't poison the shared connection for every call after it.

    Without this, a single unexpected DB error (a malformed LLM-generated
    argument, an unanticipated constraint hit) leaves the connection in a
    failed-transaction state -- every subsequent tool call on this same
    process then fails too, "current transaction is aborted", until the
    process restarts. One bad call would otherwise break the rest of the
    guest's session (FR-008; constitution: every tool returns
    {status, data, error} and never raises).
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            get_conn().rollback()
            return {
                "status": "error",
                "error": "Something went wrong processing that request. Please try again, or ask for a staff member.",
            }
    return wrapper

@safe_tool
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

@safe_tool
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

@safe_tool
def _available_room_count(cur, room_type_id, check_in_date, check_out_date, exclude_booking_reference=None)-> int: 
   
    """Shared inventory-availability count -- used by both list_room_types
    and create_booking, so the counting logic exists in exactly one place.

    Total active rooms of this type, minus rooms already committed to an
    active reservation whose dates overlap the requested range. Half-open
    interval: check_in_date inclusive, check_out_date exclusive, so a
    checkout on day X and a new check-in on day X don't count as overlapping.

    excllude bookign ref when rechecking availability for a reservation thats about to be modified 
    its own row would otherwise count against itself pass its booking reference to leave it out of the already reserved count 
    """
    cur.execute(
        "SELECT count(*) FROM rooms WHERE room_type_id = %s AND operational_status = 'active'",
        (room_type_id,),
    )
    total = cur.fetchone()[0]
    cur.execute(
        """
        SELECT count(*) FROM reservations
        WHERE room_type_id = %s
          AND status IN ('confirmed', 'checked_in')
          AND check_in_date < %s
          AND check_out_date > %s
                    AND (%s::text IS NULL OR booking_reference != %s)
        """,
        (room_type_id, check_out_date, check_in_date, exclude_booking_reference, exclude_booking_reference),
    )
    reserved = cur.fetchone()[0]
    return total - reserved

@safe_tool
def retrieve_hotel_policy(question: str) -> dict:
    """Searches the hotels policy documents for information relevant to a guests question.

    Use this whenever a guest asks about hotel rules, check-in/out times, cancellation,pets breakfast, parking, or similiar policy questions.
    Args:
        questions: The guests question , in their words
    Returns:
        A dictionary with the matched policy text and which source file it came from
    """

    conn = get_conn()
    cur = conn.cursor()
    # SQL, sent to Postgres via psycopg — not Python code itself.
    # %s is a psycopg placeholder, safely filled with q_emb (not string formatting).
    # <=> is a pgvector operator: cosine distance between two vectors (smaller = more similar).
    # Meaning: "give me the 2 policy chunks whose embedding is closest to the guest's question."
    q_emb = vo.embed([question], model="voyage-3.5-lite", input_type="query", output_dimension=1024).embeddings[0]
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

@safe_tool
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

    conn = get_conn()
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

@safe_tool
def assign_room(idempotency_key:str, booking_reference:str, room_id: str | None = None, desired_features: list[str] | None = None,) -> dict: 
    """
    Assigns a specific physical room to a confirmed reservation.

    A separate step from both create_booking (reserves inventory) and
    check_in_guest (activates the stay) -- call this any time after booking,
    whenever you're ready to commit to a specific room. Calling it again on
    the same reservation reassigns a different room; it does not error.

    Args:
        idempotency_key: a unique string generated once per logical
            assignment attempt.
        booking_reference: the reservation to assign a room to.
        room_id: a specific room to assign, if already known. Leave unset to
            let this tool pick a suitable one automatically.
        desired_features: optional feature tags to match when picking a room
            automatically (ignored if room_id is given directly).

    Returns:
        On success: {"status": "ok", "data": {"room_id", "room_number",
        "room_type", "view_type"}}
        On failure: {"status": "error", "error": "..."}
    """

    conn = get_conn()
    cur = conn.cursor()
    tool_name = "assign_room"
    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None:
        cur.close()
        return cached

    cur.execute(
        "SELECT status, room_type_id, check_in_date, check_out_date FROM reservations WHERE booking_reference = %s FOR UPDATE",
        (booking_reference,),
    )
    resv = cur.fetchone()

    if resv is None: 
         result = {"status": "error", "error": f"No reservation found under this reference:  {booking_reference}. "}
    elif resv[0] != "confirmed": 
        result = {"status": "error", "error": f"Reservation is '{resv[0]}', not 'confirmed' cannot assign a room. "}
    else: 
        _, room_type_id, check_in_date, check_out_date = resv
        # A room qualifies if it's the right type, not out of order, and not
        # already the assigned room of a DIFFERENT active reservation whose
        # dates overlap this one -- the same half-open interval rule
        # create_booking uses for its aggregate count, just applied per-room.
        query = """
            SELECT rm.id, rm.room_number, rm.view_type, rt.name
            FROM rooms rm
            JOIN room_types rt ON rt.id = rm.room_type_id
            WHERE rm.room_type_id = %s
              AND rm.operational_status = 'active'
              AND NOT EXISTS (
                  SELECT 1 FROM reservations r2
                  WHERE r2.room_id = rm.id
                    AND r2.booking_reference != %s
                    AND r2.status IN ('confirmed', 'checked_in')
                    AND r2.check_in_date < %s
                    AND r2.check_out_date > %s
              )
        """
        params = [room_type_id, booking_reference, check_out_date, check_in_date]
        if room_id:
            query += "AND rm.id = %s"
            params.append(room_id)
        elif desired_features:
            query += """
                AND (
               SELECT count(DISTINCT feature) FROM room_features
                WHERE room_id = rm.id AND feature = ANY(%s)
                ) = %s
            """
            params.extend([desired_features, len(desired_features)])
        query += " LIMIT 1 FOR UPDATE"
        cur.execute(query, params)
        room = cur.fetchone()

        if room is None:
            if room_id:
                result = {"status": "error", "error": "That room isn't available for this reservation's type or dates."}
            else:
                result = {"status": "error", "error": "No matching room is currently available for these dates."}
        else:
            found_room_id, room_number, view_type, room_type_name = room
            cur.execute(
                "UPDATE reservations SET room_id = %s WHERE booking_reference = %s",
                (found_room_id, booking_reference),
            )
            result = {
                "status": "ok",
                "data": {
                    "room_id": str(found_room_id),
                    "room_number": room_number,
                    "room_type": room_type_name,
                    "view_type": view_type,
                },
            }

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

@safe_tool
def list_room_types(check_in_date: str, check_out_date: str) -> dict:
    """Lists every room type with its features and real availability for the given dates.

    Call this whenever a guest wants to book a new stay. Present the results
    conversationally and use your own judgment to match natural-language
    requests (e.g. "a suite with a couch", "something for 3 people with a
    bathtub") against each type's bed_config/max_occupancy/features -- there
    is no structured filter here; reasoning over this list IS the matching
    step.

    Args:
        check_in_date: ISO date string, e.g. "2026-09-01".
        check_out_date: ISO date string. Must be after check_in_date.

    Returns:
        {"status": "ok", "data": {"room_types": [{"room_type_id", "name",
        "bed_config", "max_occupancy", "sq_meters", "features", "available"}]}}
        "available" is how many rooms of that type are free for the WHOLE
        requested range -- 0 means fully booked, not absent from the list.
    """

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, bed_config, max_occupancy, sq_meters, base_rate FROM room_types "
        "ORDER BY max_occupancy, sq_meters"
    )
    types = cur.fetchall()

    room_types = []
    for room_type_id, name, bed_config, max_occupancy, sq_meters, base_rate in types:
        cur.execute(
            "SELECT DISTINCT feature FROM room_features WHERE room_type_id = %s",
            (room_type_id,),
        )
        type_features = [row[0] for row in cur.fetchall()]

        room_types.append({
            "room_type_id": str(room_type_id),
            "name": name,
            "bed_config": bed_config,
            "max_occupancy": max_occupancy,
            "sq_meters": sq_meters,
            "features": type_features,
            "available": _available_room_count(cur, room_type_id, check_in_date, check_out_date),
            "rate_per_night": float(base_rate),
        })

    cur.close()
    return {"status": "ok", "data": {"room_types": room_types}}

@safe_tool
def search_guest_profiles(
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        ) -> dict:
        """Searches for existing guest profiles by contact info or name.

        Call this BEFORE create_guest_profile, every time, never create a new
        profile without searching first. If email or phone is given, matches
        exactly (case-insensitive) on that alone, since those are the most
        reliable identifiers. Otherwise falls back to a partial, case-insensitive
        match on first_name/last_name. Present the returned candidates to the
        guest conversationally and let them confirm which one (if any) is them,
        never guess or auto-select on their behalf.

        Args:
            first_name: partial match, used only if email/phone not given.
            last_name: partial match, used only if email/phone not given.
            email: exact case-insensitive match, if given.
            phone: exact case-insensitive match, if given.

        Returns:
            {"status": "ok", "data": {"candidates": [{"guest_id", "first_name",
            "last_name", "email", "phone"}, ...]}}, up to 5 rows. Empty list if
            nothing matches -- not an error, just no results.

        """
        
        conn = get_conn()
        cur = conn.cursor()
        if email:
            cur.execute(
                "SELECT id, first_name, last_name, email, phone FROM guests WHERE lower(email) = lower(%s) LIMIT 5",
                (email,),
            )
        elif phone:
            cur.execute(
                "SELECT id, first_name, last_name, email, phone FROM guests WHERE lower(phone) = lower(%s) LIMIT 5",
                (phone,),
            )
        else:
            # Missing first_name/last_name becomes '%' -- a harmless wildcard, so
            # a last-name-only or first-name-only search still works naturally.
            cur.execute(
                """
                SELECT id, first_name, last_name, email, phone FROM guests
                WHERE first_name ILIKE %s AND last_name ILIKE %s
                LIMIT 5
                """,
                (f"%{first_name or ''}%", f"%{last_name or ''}%"),
            )

        rows = cur.fetchall()
        cur.close()
        return {
            "status": "ok",
            "data": {
                "candidates": [
                    {"guest_id": str(r[0]), "first_name": r[1], "last_name": r[2], "email": r[3], "phone": r[4]}
                    for r in rows
                ]
            },
        }

@safe_tool
def create_guest_profile(
    idempotency_key: str,
    first_name: str,
    last_name: str,
    email: str | None = None,
    phone: str | None = None,
    country: str | None = None,
) -> dict:
    """Creates a new guest profile.

    Call search_guest_profiles FIRST, always -- this tool does not check for
    duplicates itself. Only call this after the guest has confirmed no
    existing profile matches them.

    Args:
        idempotency_key: a unique string generated once per logical
            creation attempt.
        first_name: guest's first name.
        last_name: guest's last name.
        email: guest's email, optional.
        phone: guest's phone, optional.
        country: guest's country, optional.

    Returns:
        {"status": "ok", "data": {"guest_id": ...}}
    """
    
    conn = get_conn()
    cur = conn.cursor()
    tool_name = "create_guest_profile"

    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None:
        cur.close()
        return cached

    # legacy_guest_id stays NULL -- this is a genuinely new profile, not a
    # backfilled Kaggle row, and the column already permits multiple NULLs.
    cur.execute(
        """
        INSERT INTO guests (legacy_guest_id, first_name, last_name, email, phone, country_code)
        VALUES (NULL, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (first_name, last_name, email, phone, country),
    )
    guest_id = cur.fetchone()[0]
    result = {"status": "ok", "data": {"guest_id": str(guest_id)}}

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

@safe_tool
def update_guest_profile(
    idempotency_key: str,
    guest_id: str,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    country: str | None = None,
) -> dict:
    """Updates an existing guest profile. Only supplied fields are changed.

    Args:
        idempotency_key: a unique string generated once per logical update attempt.
        guest_id: which guest to update.
        first_name, last_name, email, phone, country: only the fields the
            guest actually wants to change -- leave the rest unset. This is a
            partial update, not a full overwrite; an unset field keeps its
            existing value.

    Returns:
        {"status": "ok", "data": {"guest_id": ...}} on success.
        {"status": "error", "error": "..."} if guest_id doesn't exist, or if
        no fields were supplied at all.
    """

    conn = get_conn()
    cur = conn.cursor()
    tool_name = "update_guest_profile"

    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None:
        cur.close()
        return cached

    # Build the SET clause only from fields actually supplied -- an unset
    # (None) argument means "don't touch this column," not "clear it."
    # Safe to build the column list into the SQL string itself here, since
    # `fields`' keys are fixed literals defined right above, never guest
    # input -- only the VALUES are guest-supplied, and those still go through
    # %s placeholders like everywhere else in this file.
    fields = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "country_code": country,
    }
    supplied = {col: val for col, val in fields.items() if val is not None}

    if not supplied:
        result = {"status": "error", "error": "No fields supplied to update."}
    else:
        set_clause = ", ".join(f"{col} = %s" for col in supplied)
        cur.execute(
            f"UPDATE guests SET {set_clause} WHERE id = %s RETURNING id",
            (*supplied.values(), guest_id),
        )
        row = cur.fetchone()
        if row is None:
            result = {"status": "error", "error": f"No guest found with id {guest_id}."}
        else:
            result = {"status": "ok", "data": {"guest_id": str(row[0])}}

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

@safe_tool
def check_in_guest(idempotency_key: str, booking_reference: str) -> dict:
    """Checks a guest into their already-assigned room.

    Requires assign_room to have run first -- this tool does NOT search for
    or pick a room itself. If the reservation has no room assigned yet, it
    returns an error telling the caller to call assign_room first.

    Args:
        idempotency_key: a unique string generated once per logical check-in
            attempt. Retrying with the SAME key returns the original result.
        booking_reference: the reservation's booking reference, e.g. "BK-G0001".

    Returns:
        On success: {"status": "ok", "data": {"room_id", "room_number",
        "room_type", "view_type", "reservation_status": "checked_in"}}
        On failure: {"status": "error", "error": "..."} -- reservation not
        found, not 'confirmed', no room assigned yet, or the assigned room
        isn't currently ready (still occupied or out of order).
    """

    conn = get_conn()
    cur = conn.cursor()
    tool_name = "check_in_guest"

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
        result = {"status": "error", "error": f"No reservation found for {booking_reference}."}
    else:
        status, room_id = resv
        if status != "confirmed":
            result = {"status": "error", "error": f"Reservation is '{status}', not 'confirmed' — cannot check in."}
        elif room_id is None:
            result = {"status": "error", "error": "No room assigned to this reservation yet — call assign_room first."}
        else:
            cur.execute(
                """
                SELECT rm.occupancy_status, rm.operational_status, rm.room_number, rm.view_type, rt.name
                FROM rooms rm
                JOIN room_types rt ON rt.id = rm.room_type_id
                WHERE rm.id = %s
                FOR UPDATE
                """,
                (room_id,),
            )
            occupancy_status, operational_status, room_number, view_type, room_type_name = cur.fetchone()

            if occupancy_status != "vacant" or operational_status != "active":
                result = {"status": "error", "error": "The assigned room isn't ready yet — it may still be occupied or out of order."}
            else:
                cur.execute(
                    "UPDATE reservations SET status = 'checked_in' WHERE booking_reference = %s",
                    (booking_reference,),
                )
                cur.execute(
                    "UPDATE rooms SET occupancy_status = 'occupied' WHERE id = %s",
                    (room_id,),
                )
                result = {
                    "status": "ok",
                    "data": {
                        "room_id": str(room_id),
                        "room_number": room_number,
                        "room_type": room_type_name,
                        "view_type": view_type,
                        "reservation_status": "checked_in",
                    },
                }

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

@safe_tool
def check_out_guest(idempotency_key: str, booking_reference: str) -> dict:
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

    conn = get_conn()
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

@safe_tool
def create_booking(
    idempotency_key:str,
    guest_id:str,
        room_type_id: str,
    check_in_date: str,
    check_out_date: str,
    breakfast_included: bool = False,
) -> dict:
    """Creates a new reservation against the room catalogue.

    guest_id must already be resolved -- from verify_guest_identity or the
    profile-search/create tools. Never invent a guest_id. Always tell the
    guest both the per-night rate and the total price for their whole stay
    before booking -- both are in this tool's response.

    Args:
        idempotency_key: a unique string generated once per logical booking attempt.
        guest_id: the guest's id (a UUID string) this booking belongs to.
        room_type_id: which room type to book (a UUID string, from list_room_types).
        check_in_date: an ISO date string, e.g. "2026-09-01".
        check_out_date: an ISO date string. Must be after check_in_date.
        breakfast_included: whether to add breakfast for the whole stay.
            Ask the guest -- don't assume. Breakfast can also be arranged
            on-site at the hotel, or later, so this is optional, not required.

    Returns:
        On success: {"status": "ok", "data": {"booking_reference",
        "rate_per_night", "nights", "breakfast_included",
        "breakfast_total", "total_price"}}
        On failure: {"status": "error", "error": "..."}
    """

    conn = get_conn()
    cur = conn.cursor()
    tool_name = "create_booking"

    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None:
        cur.close()
        return cached
    if check_in_date < datetime.date.today().isoformat():
        result = {"status": "error", "error": "Check-in date can't be in the past."}
    
    elif check_out_date <= check_in_date:
        result = {"status": "error", "error": "Check-out date must be after check-in date."}
    else:
        available = _available_room_count(cur, room_type_id, check_in_date, check_out_date)
        if available <= 0:
            result = {"status": "error", "error": "No room of the requested type is available for those dates."}
        else:
            cur.execute("SELECT base_rate FROM room_types WHERE id = %s", (room_type_id,))
            base_rate = cur.fetchone()[0]

            from datetime import date
            nights = (date.fromisoformat(check_out_date) - date.fromisoformat(check_in_date)).days

            booking_reference = "BK-" + str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO reservations
                    (booking_reference, guest_id, room_type_id, check_in_date, check_out_date, adr, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'confirmed')
                """,
                (booking_reference, guest_id, room_type_id, check_in_date, check_out_date, base_rate),
            )

            breakfast_total = 0
            if breakfast_included:
                # Snapshot the price in effect on check_in_date into
                # reservation_products -- a later catalogue price change must
                # never retroactively reprice this already-made booking.
                cur.execute(
                    """
                    SELECT pp.amount, pp.pricing_basis, p.id
                    FROM product_prices pp
                    JOIN products p ON p.id = pp.product_id
                    WHERE p.code = 'BREAKFAST'
                      AND pp.valid_from <= %s
                      AND (pp.valid_to IS NULL OR pp.valid_to >= %s)
                    ORDER BY pp.valid_from DESC
                    LIMIT 1
                    """,
                    (check_in_date, check_in_date),
                )
                unit_price, pricing_basis, product_id = cur.fetchone()
                breakfast_total = unit_price * nights
                cur.execute(
                    """
                    INSERT INTO reservation_products
                        (reservation_id, product_id, quantity, unit_price, pricing_basis, line_total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (booking_reference, product_id, nights, unit_price, pricing_basis, breakfast_total),
                )

            total_price = (base_rate * nights) + breakfast_total

            result = {
                "status": "ok",
                "data": {
                    "booking_reference": booking_reference,
                    "rate_per_night": float(base_rate),
                    "nights": nights,
                    "breakfast_included": breakfast_included,
                    "breakfast_total": float(breakfast_total),
                    "total_price": float(total_price),
                },
            }

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

@safe_tool
def modify_booking(
    idempotency_key: str,
    booking_reference: str,
    new_check_in: str,
    new_check_out: str,
) -> dict:
    """Changes an existing reservation's dates.

    ADK gates this tool behind an explicit human confirmation before this
    function ever runs -- by the time this code executes, the guest has
    already said yes; there is no separate confirmation check needed here.

    Args:
        idempotency_key: a unique string generated once per logical modify attempt.
        booking_reference: which reservation to modify.
        new_check_in: new ISO date string for check-in.
        new_check_out: new ISO date string for check-out. Must be after new_check_in.

    Returns:
        {"status": "ok", "data": {"booking_reference", "check_in_date", "check_out_date"}}
        {"status": "error", "error": "..."}
    """

    conn = get_conn()
    cur = conn.cursor()
    tool_name = "modify_booking"

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
        result = {"status": "error", "error": f"No reservation found for {booking_reference}."}
    elif resv[0] not in ("confirmed", "checked_in"):
        result = {"status": "error", "error": f"Reservation is '{resv[0]}' — dates can't be changed."}
    elif new_check_out <= new_check_in:
        result = {"status": "error", "error": "Check-out date must be after check-in date."}
    else:
        room_type_id = resv[1]
        # Same guard create_booking uses -- a date change is really "give up
        # the old dates, ask for the new ones," so it needs the same
        # capacity check a brand-new booking would get. Excludes this
        # reservation's own (still-old-dated) row so it doesn't count
        # against itself.
        available = _available_room_count(
            cur, room_type_id, new_check_in, new_check_out,
            exclude_booking_reference=booking_reference,
        )
        if available <= 0:
            result = {"status": "error", "error": "No room of this reservation's room type is available for the new dates."}
        else:
            cur.execute(
                "UPDATE reservations SET check_in_date=%s, check_out_date = %s WHERE booking_reference = %s",
                (new_check_in,new_check_out,booking_reference)
            )
            result = {
                "status": "ok",
                "data": {
                    "booking_reference": booking_reference,
                    "check_in_date": new_check_in,
                    "check_out_date": new_check_out,
                },
            }
    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

@safe_tool
def cancel_booking(idempotency_key: str, booking_reference: str) -> dict:
    """Cancels an existing reservation.

    ADK gates this tool behind an explicit human confirmation before this
    function ever runs -- same as modify_booking, no confirmation check
    needed in this code.

    Args:
        idempotency_key: a unique string generated once per logical cancel attempt.
        booking_reference: which reservation to cancel.

    Returns:
        {"status": "ok", "data": {"booking_reference", "reservation_status": "cancelled"}}
        {"status": "error", "error": "..."}
    """

    conn = get_conn()
    cur = conn.cursor()
    tool_name = "cancel_booking"

    cached = check_idempotency(cur, idempotency_key, tool_name)
    if cached is not None:
        cur.close()
        return cached

    cur.execute(
        "SELECT status FROM reservations WHERE booking_reference = %s FOR UPDATE",
        (booking_reference,),
    )
    resv = cur.fetchone()

    if resv is None:
        result = {"status": "error", "error": f"No reservation found for {booking_reference}."}
    elif resv[0] not in ("confirmed", "checked_in"):
        result = {"status": "error", "error": f"Reservation is '{resv[0]}' — cannot be cancelled."}
    else:
        cur.execute(
            "UPDATE reservations SET status = 'cancelled' WHERE booking_reference = %s",
            (booking_reference,),
        )
        result = {
            "status": "ok",
            "data": {"booking_reference": booking_reference, "reservation_status": "cancelled"},
        }

    record_idempotency(cur, idempotency_key, tool_name, result)
    conn.commit()
    cur.close()
    return result

@safe_tool
def request_human_handoff(reason: str | None = None) -> dict:
    """Acknowledges a guest's request to speak with a staff member.
 
    Tier 1, no persistence this phase -- there's no staff_tasks table yet
    (that arrives in a later phase). This just gives the guest a clear,
    honest acknowledgment instead of the agent dead-ending or continuing
    to attempt something it can't actually resolve.

    Args:
        reason: optional free-text note on why the guest wants a human --
            not stored anywhere yet, just useful for the agent to pass
            along in its own response to the guest if relevant.

    Returns:
        {"status": "ok", "data": {"acknowledged": True}}
    """
    return {"status": "ok", "data": {"acknowledged": True}}