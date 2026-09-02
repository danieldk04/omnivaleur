import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
sb = create_client(url, key)

uid = "26cf5471-8367-4669-b4c1-9ce3e36f6a5f"

# Only error-status jobs, across the whole window, paginated.
errors = []
start = 0
page = 1000
while True:
    r = (sb.table("jobs")
         .select("id,status,result,platform,action,created_at")
         .eq("user_id", uid)
         .eq("status", "error")
         .gte("created_at", "2026-08-25T00:00:00")
         .order("created_at", desc=False)
         .range(start, start + page - 1)
         .execute())
    errors.extend(r.data)
    if len(r.data) < page:
        break
    start += page

print(f"total error jobs since 08-25: {len(errors)}")
for j in errors:
    res = j.get("result")
    errtxt = json.dumps(res, default=str)[:250] if res else ""
    print(j.get("created_at"), j.get("platform"), j.get("action"), "|", errtxt)
