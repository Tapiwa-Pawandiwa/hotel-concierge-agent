CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; 

CREATE TABLE guests (
 guest_id text PRIMARY KEY,  -- the existing G0001..G0300 format, not a UUID yet
 guest_name text NOT NULL, 
 guest_email text, 
 hotel text,
 country text,
 lead_time int,  
 arrival_date_year int,
 arrival_date_month text,
 arrival_date_day int,
 adults int,
 children int,
 babies int,
 is_repeated_guest bool DEFAULT false, 
 previous_cancellations int DEFAULT 0,
 reserved_room_type text,
 customer_type text, 
 adr numeric(10,2)
);

CREATE TABLE policy_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_file text NOT NULL, content text NOT NULL,
  embedding vector(1024) NOT NULL
);
CREATE INDEX policy_chunks_embedding_idx ON policy_chunks USING hnsw(embedding vector_cosine_ops);