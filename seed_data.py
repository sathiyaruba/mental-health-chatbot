"""
Solace Dataset - PostgreSQL Import Script
Run: py app/seed_data.py
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import uuid
import math

# ─── DB CONFIG ───────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "solace_db",
    "user": "postgres",
    "password": "newpassword123",   # <-- unga actual password
}

EXCEL_PATH = r"D:\mental_health_chatbot2\solace-backend\app\data\Solace_Dataset.xlsx"

# ─── ID MAPPING ──────────────────────────────────────────────
id_map = {}

def to_uuid(short_id):
    if not short_id or (isinstance(short_id, float) and math.isnan(short_id)):
        return None
    short_id = str(short_id).strip()
    if short_id not in id_map:
        id_map[short_id] = str(uuid.uuid5(uuid.NAMESPACE_DNS, short_id))
    return id_map[short_id]

def clean(val):
    if isinstance(val, float) and math.isnan(val):
        return None
    if val is None:
        return None
    if isinstance(val, str):
        val = val.strip()
        if val == '' or val.lower() == 'nan':
            return None
    return val

def to_bool(val):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == 'true'
    return False

# ─── MOOD MAPPING ────────────────────────────────────────────
MOOD_MAP = {
    "great": "great", "happy": "great", "excited": "great", "joyful": "great", "elated": "great",
    "good": "good", "calm": "good", "content": "good", "relaxed": "good", "hopeful": "good",
    "okay": "okay", "neutral": "okay", "fine": "okay", "mixed": "okay",
    "low": "low", "anxious": "low", "sad": "low", "depressed": "low", "stressed": "low",
    "angry": "low", "frustrated": "low", "overwhelmed": "low", "tired": "low", "lonely": "low",
    "scared": "low", "worried": "low", "numb": "low", "hopeless": "low", "miserable": "low",
}

def map_mood(val):
    if not val or (isinstance(val, float) and math.isnan(val)):
        return "okay"
    return MOOD_MAP.get(str(val).strip().lower(), "okay")

def read_sheet(sheet_name, header_row=2):
    df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name, header=header_row)
    df = df.dropna(how='all')
    return df

# ─── MAIN SEED ───────────────────────────────────────────────
def seed():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("✅ Connected to PostgreSQL")

    try:
        # ── 1. USERS
        print("\n📥 Seeding Users...")
        df = read_sheet('01_Users')
        df.columns = ['user_id','display_name','email','is_anonymous','is_verified','is_active','oauth_provider','created_at','last_login']
        df = df[df['user_id'].notna() & df['user_id'].astype(str).str.startswith('u')]
        users_data = [(to_uuid(r['user_id']), clean(r['display_name']), clean(r['email']), to_bool(r['is_anonymous']), to_bool(r['is_verified']), to_bool(r['is_active']), clean(r['oauth_provider']), clean(r['created_at']), clean(r['last_login'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO users (id, display_name, email, is_anonymous, is_verified, is_active, oauth_provider, created_at, last_login) VALUES %s ON CONFLICT (id) DO NOTHING", users_data)
        print(f"   ✓ {len(users_data)} users inserted")

        # ── 2. THERAPISTS
        print("\n📥 Seeding Therapists...")
        df = read_sheet('05_Therapists')
        df.columns = ['therapist_id','name','specialization','languages','approaches','rating','review_count','availability','avatar_emoji','bio','is_active','created_at']
        df = df[df['therapist_id'].notna() & df['therapist_id'].astype(str).str.startswith('t')]
        therapists_data = [(to_uuid(r['therapist_id']), clean(r['name']), clean(r['specialization']), clean(r['languages']), clean(r['approaches']), float(r['rating']) if pd.notna(r['rating']) else None, int(r['review_count']) if pd.notna(r['review_count']) else None, clean(r['availability']), clean(r['avatar_emoji']), clean(r['bio']), to_bool(r['is_active']), clean(r['created_at'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO therapists (id, name, specialization, languages, approaches, rating, review_count, availability, avatar_emoji, bio, is_active, created_at) VALUES %s ON CONFLICT (id) DO NOTHING", therapists_data)
        print(f"   ✓ {len(therapists_data)} therapists inserted")

        # ── 3. MOOD LOGS
        print("\n📥 Seeding Mood Logs...")
        df = read_sheet('02_Mood Logs')
        df.columns = ['log_id','user_id','mood','score','note','tags','ai_insight','created_at']
        df = df[df['log_id'].notna() & df['log_id'].astype(str).str.startswith('ml')]
        mood_data = [(to_uuid(r['log_id']), to_uuid(r['user_id']), map_mood(r['mood']), int(r['score']) if pd.notna(r['score']) else None, clean(r['note']), clean(r['tags']), clean(r['ai_insight']), clean(r['created_at'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO mood_logs (id, user_id, mood, score, note, tags, ai_insight, created_at) VALUES %s ON CONFLICT (id) DO NOTHING", mood_data)
        print(f"   ✓ {len(mood_data)} mood logs inserted")

        # ── 4. CHAT SESSIONS
        print("\n📥 Seeding Chat Sessions...")
        df = read_sheet('03_Chat Sessions')
        df.columns = ['session_id','user_id','title','created_at','updated_at','message_count']
        df = df[df['session_id'].notna() & df['session_id'].astype(str).str.startswith('cs')]
        sessions_data = [(to_uuid(r['session_id']), to_uuid(r['user_id']), clean(r['title']), clean(r['created_at']), clean(r['updated_at'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES %s ON CONFLICT (id) DO NOTHING", sessions_data)
        print(f"   ✓ {len(sessions_data)} chat sessions inserted")

        # ── 5. CHAT MESSAGES
        print("\n📥 Seeding Chat Messages...")
        df = read_sheet('04_Chat Messages')
        df = df[['Message Id', 'Session Id', 'Role', 'Content', 'Detected Mood', 'Crisis Flag', 'Created At']]
        df.columns = ['message_id','session_id','role','content','detected_mood','crisis_flag','created_at']
        df = df[df['message_id'].notna() & df['message_id'].astype(str).str.startswith('cm')]
        # Only keep rows where created_at is a valid timestamp
        def is_valid_ts(val):
            if val is None:
                return False
            s = str(val).strip()
            return s.startswith('2024') or s.startswith('2023')
        df = df[df['created_at'].apply(is_valid_ts)]
        messages_data = [(to_uuid(r['message_id']), to_uuid(r['session_id']), clean(r['role']), clean(r['content']), map_mood(r['detected_mood']), to_bool(r['crisis_flag']), clean(r['created_at'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO chat_messages (id, session_id, role, content, detected_mood, crisis_flag, created_at) VALUES %s ON CONFLICT (id) DO NOTHING", messages_data)
        print(f"   ✓ {len(messages_data)} chat messages inserted")

        # ── 6. BOOKINGS
        print("\n📥 Seeding Bookings...")
        df = read_sheet('06_Bookings')
        df.columns = ['booking_id','user_id','therapist_id','scheduled_at','status','notes','created_at']
        df = df[df['booking_id'].notna() & df['booking_id'].astype(str).str.startswith('b')]
        bookings_data = [(to_uuid(r['booking_id']), to_uuid(r['user_id']), to_uuid(r['therapist_id']), clean(r['scheduled_at']), clean(r['status']), clean(r['notes']), clean(r['created_at'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO therapist_bookings (id, user_id, therapist_id, scheduled_at, status, notes, created_at) VALUES %s ON CONFLICT (id) DO NOTHING", bookings_data)
        print(f"   ✓ {len(bookings_data)} bookings inserted")

        # ── 7. TRUSTED CONTACTS
        print("\n📥 Seeding Trusted Contacts...")
        df = read_sheet('07_Contacts')
        df.columns = ['contact_id','user_id','name','relationship','email','phone','is_active','created_at']
        df = df[df['contact_id'].notna() & df['contact_id'].astype(str).str.startswith('tc')]
        contacts_data = [(to_uuid(r['contact_id']), to_uuid(r['user_id']), clean(r['name']), clean(r['relationship']), clean(r['email']), clean(r['phone']), to_bool(r['is_active']), clean(r['created_at'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO trusted_contacts (id, user_id, name, relation_type, email, phone, is_active, created_at) VALUES %s ON CONFLICT (id) DO NOTHING", contacts_data)
        print(f"   ✓ {len(contacts_data)} contacts inserted")

        # ── 8. CRISIS ALERTS
        print("\n📥 Seeding Crisis Alerts...")
        df = read_sheet('08_Crisis Alerts')
        df.columns = ['alert_id','user_id','contact_id','trigger_text','status','sent_at','created_at']
        df = df[df['alert_id'].notna() & df['alert_id'].astype(str).str.startswith('ca')]
        alerts_data = [(to_uuid(r['alert_id']), to_uuid(r['user_id']), to_uuid(r['contact_id']), clean(r['trigger_text']), clean(r['status']), clean(r['sent_at']), clean(r['created_at'])) for _, r in df.iterrows()]
        execute_values(cur, "INSERT INTO crisis_alerts (id, user_id, contact_id, trigger_text, status, sent_at, created_at) VALUES %s ON CONFLICT (id) DO NOTHING", alerts_data)
        print(f"   ✓ {len(alerts_data)} crisis alerts inserted")

        # ── 9. ADMINS ─────────────────────────────────────────
        print("\n📥 Seeding Admins...")
        df = read_sheet('11_Admins')
        df.columns = ['admin_id','display_name','email','hashed_password','role','is_active','last_login','created_at']
        df = df[df['admin_id'].notna() & df['admin_id'].astype(str).str.startswith('a')]
        admins_data = [(
            to_uuid(r['admin_id']),
            clean(r['display_name']),
            clean(r['email']),
            clean(r['hashed_password']),
            clean(r['role']),
            to_bool(r['is_active']),
            clean(r['last_login']),
            clean(r['created_at'])
        ) for _, r in df.iterrows()]
        execute_values(cur, """
            INSERT INTO admins
                (id, display_name, email, hashed_password,
                 role, is_active, last_login, created_at)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, admins_data)
        print(f"   ✓ {len(admins_data)} admins inserted")

        # ── 10. ADMIN LOGS ────────────────────────────────────
        print("\n📥 Seeding Admin Logs...")
        df = read_sheet('12_Admin Logs')
        df.columns = ['log_id','admin_id','action','target_type','target_id','details','ip_address','created_at']
        df = df[df['log_id'].notna() & df['log_id'].astype(str).str.startswith('al')]
        admin_logs_data = [(
            to_uuid(r['log_id']),
            to_uuid(r['admin_id']),
            clean(r['action']),
            clean(r['target_type']),
            clean(r['target_id']),
            clean(r['details']),
            clean(r['ip_address']),
            clean(r['created_at'])
        ) for _, r in df.iterrows()]
        execute_values(cur, """
            INSERT INTO admin_logs
                (id, admin_id, action, target_type,
                 target_id, details, ip_address, created_at)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, admin_logs_data)
        print(f"   ✓ {len(admin_logs_data)} admin logs inserted")


        conn.commit()
        print("\n🎉 All data seeded successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed()