import os
import psycopg
from pgvector.psycopg import register_vector
import voyageai
from dotenv import load_dotenv

load_dotenv()

vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])
register_vector(conn)


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
        (
            q_emb,
        ),
    )
    rows = cur.fetchall()
    cur.close()
    return {
        "status": "success",
        "matches": [{"source": r[0], "text": r[1]} for r in rows],
    }


def lookup_guest_profile(guest_id: str) -> dict:
    """Looks up a guest's booking profile by their guest ID.

    Use this when you know which guest youre talking to and want to personalize your repsonse
    eg. whether theyre a returning guest, how many nights they're staying, or whether they're traveling with children.

    Args:
        guest_id: The guests ID, eg. "G0001"

    Returns:
        A dictionary with the guests profile fields, or a not_found status if no match.
    """

    cur = conn.cursor
    cur.execute("SELECT * FROM guests WHERE guest_id = %s::vector", (guest_id))
    row = cur.fetchone()
    columns = [desc[0] for desc in cur.description]
    cur.close()

    if row is None:
        return {"status": "not_found", "guest_id": guest_id}
    return {"status": "success", "profile": dict(zip(columns, row))}
