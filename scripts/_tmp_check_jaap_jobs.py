import os, sys, json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
sb = create_client(url, key)

# Known from memory: Jaap / zilverwebsite.nl user_id starts with 26cf5471
try:
    subs = sb.table("subscriptions").select("*").ilike("id", "26cf5471%").execute()
    print("SUBS by id prefix:", json.dumps(subs.data, indent=2, default=str)[:2000])
except Exception as e:
    print("subs query failed:", e)

try:
    admin_user = sb.auth.admin.get_user_by_id.__doc__
except Exception:
    pass

# try admin list to map email -> id
try:
    res = sb.auth.admin.list_users()
    for u in res:
        if "zilverwebsite" in (getattr(u, "email", "") or ""):
            print("AUTH USER:", u.id, u.email)
except Exception as e:
    print("admin list_users failed:", e)

uid_candidates = set()
for row in subs.data if 'subs' in dir() else []:
    uid_candidates.add(row.get("id") or row.get("user_id"))

for uid in uid_candidates:
    if not uid:
        continue
    print(f"\n=== jobs for user_id={uid} since 2026-08-27 ===")
    jobs = (sb.table("jobs")
            .select("id,status,error,platform,created_at,completed_at,job_type")
            .eq("user_id", uid)
            .gte("created_at", "2026-08-27T00:00:00")
            .order("created_at", desc=True)
            .limit(100)
            .execute())
    for j in jobs.data:
        print(j.get("created_at"), j.get("job_type"), j.get("platform"), j.get("status"), "|", (j.get("error") or "")[:160])
