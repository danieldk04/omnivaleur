"""
Videometing: wat gebeurt er met de mensen aan wie Daniel de Marktplaats-video stuurde?

Alleen lezen. Draaien met:  scripts/run_leadgen_mail.sh video_meting.py
(of met IMAP_HOST, MAIL_USER, MAIL_PASS en de Supabase-sleutels in de omgeving).

Bron: de map Verzonden in Zoho (elke mail met de videolink), de inkomende mappen
(wie antwoordde), en de Supabase-accountlijst (wie een account nam). Wat dit NIET kan
meten: of de video-mail geopend is, want Daniels eigen mails dragen geen pixel, en wie
de video op de pagina bekeek. Dat staat per lead nergens, alleen anoniem in GA4.
"""
import imaplib, os, re, sys, json, collections, email
from email.utils import parseaddr, parsedate_to_datetime
sys.path.insert(0,'.')
import scripts.leadgen_mail as lm
im=imaplib.IMAP4_SSL(os.environ["IMAP_HOST"]); im.login(os.environ["MAIL_USER"],os.environ["MAIL_PASS"])
def kop(ids,velden,map_):
    im.select(f'"{map_}"',readonly=True); uit=[]
    ids=list(ids)
    for i in range(0,len(ids),100):
        s=b",".join(ids[i:i+100])
        t,d=im.fetch(s,f"(BODY.PEEK[HEADER.FIELDS ({velden})])")
        for x in d:
            if isinstance(x,tuple): uit.append(email.message_from_bytes(x[1]))
    return uit
def ts(m):
    try: return parsedate_to_datetime(m.get("Date","")).timestamp()
    except Exception: return None
# 1 alle verzonden mails: adres -> lijst tijdstippen
im.select('"Verzonden"',readonly=True)
alle=im.search(None,"ALL")[1][0].split()
verz=collections.defaultdict(list)
for m in kop(alle,"TO DATE","Verzonden"):
    a=parseaddr(m.get("To",""))[1].lower(); t=ts(m)
    if a and t: verz[a].append(t)
# 2 video-mails
im.select('"Verzonden"',readonly=True)
ids=set()
for q in ("omnivaleur.com/mp","ymDeS37aBW4"):
    ids|=set(im.search(None,"BODY",f'"{q}"')[1][0].split())
video={}  # adres -> eerste videotijd
vorm={}
for i in sorted(ids,key=int):
    im.select('"Verzonden"',readonly=True)
    t,d=im.fetch(i,"(BODY.PEEK[])"); m=email.message_from_bytes(d[0][1])
    body=""
    for p in m.walk():
        if p.get_content_type()=="text/plain":
            body+=p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8","replace")
    a=parseaddr(m.get("To",""))[1].lower(); t_=ts(m)
    if not a or not t_ or a.endswith("omnivaleur.nl") or a.endswith("omnivaleur.com"): continue
    if "omnivaleur.com/mp-video" in body: v="lang"
    elif re.search(r"omnivaleur\.com/mp(?!-)",body): v="kort"
    else: v="youtube"
    if a not in video or t_<video[a]: video[a]=t_; vorm[a]=v
print("unieke ontvangers video:",len(video), collections.Counter(vorm.values()))
# 3 inkomende mail
eerste=min(video.values())
inkomend=collections.defaultdict(list)
for map_ in ("INBOX","Beantwoord","Archive","Klanten","Automatisch","Spam"):
    r=im.select(f'"{map_}"',readonly=True)
    if r[0]!="OK": continue
    d=im.search(None,"SINCE",(__import__("datetime").datetime.fromtimestamp(eerste-40*86400)).strftime("%d-%b-%Y"))[1][0].split()
    for m in kop(d,"FROM DATE",map_):
        a=parseaddr(m.get("From",""))[1].lower(); t=ts(m)
        if a in video and t: inkomend[a].append((t,map_))
st=lm._state(); opens=lm._db_lees("mail_opens",{}) or {}
from backend.database import get_admin_db
db=get_admin_db(); klanten={}
pg=1
while True:
    us=db.auth.admin.list_users(page=pg,per_page=200)
    us=us if isinstance(us,list) else getattr(us,'users',us)
    if not us: break
    for u in us: klanten[(u.email or '').lower()]=str(u.created_at)
    if len(us)<200: break
    pg+=1
print('accounts',len(klanten))
import time
rij=[]
for a,t0 in sorted(video.items(),key=lambda x:x[1]):
    antw=[t for t,_ in inkomend[a] if t>t0]
    volg=[t for t in verz[a] if t>t0+60]
    s=st.get(a,{})
    o=opens.get(a,{})
    rij.append(dict(verz=sorted(verz[a]),inkom=sorted(t for t,_ in inkomend[a]),a=a,t0=t0,vorm=vorm[a],antw=len(antw),eerste_antw_u=(min(antw)-t0)/3600 if antw else None,
        volg=len(volg),opens=sum(v.get("aantal",0) for v in o.values()) if o else 0,opens_opvolg=(o.get("opvolg",{}) or {}).get("aantal",0),
        klant=a in klanten,klant_op=klanten.get(a),afgemeld=bool(s.get("afgemeld")),afgewezen=bool(s.get("afgewezen")),vo=s.get("video_opvolg"),
        wachtdagen=(time.time()-t0)/86400))

import datetime as D
def pct(a,b): return f"{a} van {b} ({100*a//b if b else 0}%)"
for r in rij:
    r["antw_na"]=[t for t in r["inkom"] if t>r["t0"]]
    r["vroeg"]=any(r["t0"]-30*86400<t<r["t0"] for t in r["inkom"])
print(f"\nVideo gestuurd aan {len(rij)} adressen, waarvan {sum(r['vroeg'] for r in rij)} hadden er zelf om gevraagd")
print("Link: ",dict(collections.Counter(r["vorm"] for r in rij)))
print("Reactie na de video:", pct(sum(1 for r in rij if r["antw_na"]),len(rij)))
print("Account genomen:", pct(sum(r["klant"] for r in rij),len(rij)))
print("Geopend (pixel):", sum(1 for r in rij if r["opens"]),"(Daniels eigen mails hebben geen pixel)")
zk=[r for r in rij if not r["klant"]]
tot=collections.Counter(); reac=collections.Counter()
for r in zk:
    ev=sorted([(t,"u") for t in r["verz"] if t>r["t0"]+60]+[(t,"i") for t in r["inkom"] if t>r["t0"]])
    laatste="u"; nr=0
    for k,(t,s) in enumerate(ev):
        if s=="u" and laatste=="u":
            nr+=1; n=min(nr,3); tot[n]+=1
            nxt=[e for e in ev[k+1:] if e[0]<t+7*86400]
            if nxt and nxt[0][1]=="i": reac[n]+=1
        if s=="u" and laatste=="i": nr=0
        laatste=s
print("\nOpvolging bij wie nog geen account had (reactie = antwoord binnen 7 dagen erna):")
for n in (1,2,3): print(f"  opvolging {n if n<3 else '3+'}: {tot[n]} verstuurd, {reac[n]} reacties")
stil=[r for r in zk if not r["antw_na"]]
r0=[r for r in stil if not any(t>r["t0"]+60 for t in r["verz"])]
print(f"\nStil en geen account: {len(stil)}; daarvan nog nooit opgevolgd: {len(r0)} (oudste {max((round(r['wachtdagen']) for r in r0),default=0)} dagen)")
