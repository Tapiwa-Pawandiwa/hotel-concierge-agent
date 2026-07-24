import pandas as pd
from faker import Faker 
import random

fake = Faker()
random.seed(42)

df = pd.read_csv("hotel_bookings.csv")
df = df[df["is_canceled"] == 0]  # keep confirmed stays only

cols = ["hotel", "lead_time", "arrival_date_year", "arrival_date_month",
        "arrival_date_day_of_month", "stays_in_weekend_nights", "stays_in_week_nights",
        "adults", "children", "babies", "country", "is_repeated_guest",
        "previous_cancellations", "reserved_room_type", "customer_type", "adr"]

df = df[cols].sample(n=300, random_state=42).reset_index(drop=True)

df["guest_id"] = ["G" + str(i + 1).zfill(4) for i in range(len(df))]
df["guest_name"] = [fake.name() for _ in range(len(df))]
df["guest_email"] = [fake.email() for _ in range(len(df))]

df.to_csv("guests.csv", index=False)
print(f"Wrote {len(df)} synthetic guest profiles to guests.csv")