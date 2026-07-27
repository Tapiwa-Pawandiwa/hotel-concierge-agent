import os, glob
import psycopg
from pgvector.psycopg import register_vector
import voyageai
import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "concierge_agent", ".env"))

vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])
register_vector(conn)
cur = conn.cursor()


policy_files = glob.glob(os.path.join(os.path.dirname(__file__), "..", "..", "data", "policies", "*.md"))
sources, chunks = [], []
for path in policy_files:
    with open(path) as f:
        sources.append(os.path.basename(path))
        chunks.append(f.read().strip())

result = vo.embed(chunks, model="voyage-3.5-lite", input_type="document", output_dimension=1024)

for source, content, embedding in zip(sources, chunks, result.embeddings):
    cur.execute(
        "insert into policy_chunks (source_file, content, embedding) values (%s, %s, %s)",
        (source, content, embedding),
    )
print(f"Ingested {len(chunks)} policy chunks.")


df = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "..", "data", "guests.csv"))
cols = list(df.columns)
placeholders = ",".join(["%s"] * len(cols))
for _, row in df.iterrows():
    cur.execute(
        f"insert into guests ({','.join(cols)}) values ({placeholders}) on conflict (guest_id) do nothing",
        tuple(row[c] for c in cols),
    )
print(f"Loaded {len(df)} guest profiles.")

conn.commit()
cur.close()
conn.close()