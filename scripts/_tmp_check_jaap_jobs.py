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

uid_candidates = {"26cf5471-8367-4669-b4c1-9ce3e36f6a5f"}

for uid in uid_candidates:
    if not uid:
        continue
    print(f"\n=== jobs for user_id={uid} since 2026-08-27 ===")
    jobs = (sb.table("jobs")
            .select("id,status,result,platform,action,created_at,claimed_at,done_at")
            .eq("user_id", uid)
            .gte("created_at", "2026-08-27T00:00:00")
            .order("created_at", desc=True)
            .limit(300)
            .execute())
    from collections import Counter
    status_counts = Counter()
    for j in jobs.data:
        status_counts[j.get("status")] += 1
    print("STATUS COUNTS:", dict(status_counts))
    print(f"total rows: {len(jobs.data)}")
    print("\n--- failed/error jobs ---")
    for j in jobs.data:
        st = j.get("status")
        if st in ("error", "failed"):
            res = j.get("result")
            errtxt = json.dumps(res, default=str)[:300] if res else ""
            print(j.get("created_at"), j.get("platform"), j.get("action"), st, "|", errtxt)

    dates = sorted(j.get("created_at") for j in jobs.data)
    print("\noldest in this page:", dates[0] if dates else None)
    print("newest in this page:", dates[-1] if dates else None)

    # full count via head request
    cnt = (sb.table("jobs").select("id", count="exact")
           .eq("user_id", uid).gte("created_at", "2026-08-27T00:00:00").execute())
    print("TOTAL matching rows (exact count):", cnt.count)
