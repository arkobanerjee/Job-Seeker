"""Private local dashboard. Loopback only, escaped content, same-origin mutations."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from html import escape
import json
import secrets
import threading
from .settings import ROOT
from .catalog import Catalog
from .registry import Registry

STYLE="""body{font:16px system-ui;background:#101820;color:#e8edf2;max-width:1100px;margin:40px auto;padding:0 24px}
a{color:#7cd6c4}h1{font-size:36px}nav{display:flex;gap:20px;margin:24px 0}article{background:#1b2935;padding:24px;margin:18px 0;border-radius:12px}
.meta{color:#acbecd}button,select,input,textarea{background:#243947;color:#fff;border:1px solid #78909c;padding:10px;border-radius:6px}button{cursor:pointer}
textarea{width:90%;margin:10px 0}label{margin-right:15px}.tag{background:#324955;border-radius:4px;padding:3px 8px}pre{white-space:pre-wrap}small{color:#acbecd}"""

def serve(port=8765):
    catalog=Catalog(ROOT/"runs"/"catalog.sqlite3")
    catalog.import_runs(ROOT/"runs")
    registry=Registry(ROOT/"runs/registry.sqlite3"); registry.import_runs(ROOT/"runs")
    csrf=secrets.token_urlsafe(32)
    origin=f"http://127.0.0.1:{port}"
    lock=threading.Lock(); running={"active":False,"status":"No run started from this dashboard"}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,status,body,kind="text/html; charset=utf-8"):
            self.send_response(status); self.send_header("Content-Type",kind)
            self.send_header("Cache-Control","no-store"); self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body.encode())
        def valid_host(self): return self.headers.get("Host")==f"127.0.0.1:{port}"
        def do_GET(self):
            if not self.valid_host(): return self.send(403,"Invalid host")
            path=urlsplit(self.path)
            import re
            match=re.fullmatch(r'/evaluation/([a-f0-9]{32})\.(json|csv)',path.path)
            if match:
                file=ROOT/'runs'/match[1]/'evaluation.json'
                if not file.exists():return self.send(404,'No evaluation log for this run')
                data=file.read_text(encoding='utf-8')
                if match[2]=='csv':
                    from .telemetry import csv_report
                    return self.send(200,csv_report(json.loads(data)),'text/csv; charset=utf-8')
                return self.send(200,data,'application/json; charset=utf-8')
            if path.path!="/": return self.send(404,"Not found")
            args=parse_qs(path.query); category=args.get("category",["all"])[0]; query=args.get("q",[""])[0].casefold()
            rows=catalog.list()
            counts={kind:sum(x.get("kind")==kind for x in rows) for kind in ("vacancy","excluded","watchlist")}
            content=f"<h1>Job Seeker</h1><p class=meta>Your opportunities, evidence, and decisions.</p><p class=meta>Fit and requirements are model assessments. Verify the listing before applying.</p><p>{counts['vacancy']} shortlist Â· {counts['excluded']} rejected / review Â· {counts['watchlist']} watchlist</p>"
            content+=''.join(f'<a href="/?category={k}">{label}</a> &nbsp; ' for k,label in [("all","All"),("vacancy","Shortlist"),("excluded","Rejected / apply anyway"),("watchlist","Companies")])
            content+=f'<form method=get><input name=q placeholder="Search company, role, reason" value="{escape(query,quote=True)}"><button>Search</button></form>'
            content+=f'<form method=post action=/run><input type=hidden name=csrf value="{csrf}"><button>Start a bounded search</button></form><p class=meta>{escape(running["status"])}</p><p><small>Edit config.toml and prompts/master.md to tune searches. Resume and profile stay in private/.</small></p>'
            memory=registry.export()
            content+='<details><summary>Companies and source history</summary><p>Discovered sources; employer identity and official ownership are unverified. Text changes do not prove hiring growth or closure.</p>'
            for signal in memory.get('signals',[]):
                content+='<h3>Company signal: '+escape(signal['company'])+' — '+escape(signal['title'])+'</h3><p>Not a confirmed vacancy.</p><p>'+escape(signal['evidence_quote'])+'</p><p>'+escape(signal['url'])+'</p>'
            for company in memory['companies']:
                content+='<h3>'+escape(company['name'])+'</h3>'
                for url in company['sources']: content+='<p>'+escape(url)+'</p>'
            for source in memory['sources']:
                content+='<h3>'+escape(source['host'])+'</h3><p>'+escape(source['url'])+' · '+escape(source['ats'] or 'ATS unknown')+'</p>'
                for observation in source['history']:
                    content+='<p>'+escape(' · '.join([observation['observed_at'] or 'Time unknown',observation['status'],observation['change']]))+'</p>'
            content+='</details>'
            content+='<details><summary>Search and API evaluation logs</summary><p>Saved search results, query revisions, API usage and attribution. Counts are not human-labelled quality scores.</p>'
            for file in sorted((ROOT/'runs').glob('*/evaluation.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:250]:
                ident=file.parent.name
                if re.fullmatch('[a-f0-9]{32}',ident):content+=f'<p>Run {ident}: <a href="/evaluation/{ident}.json">Full JSON log</a> · <a href="/evaluation/{ident}.csv">Search comparison CSV</a></p>'
            content+='</details>'
            for f in rows:
                if category!="all" and f.get("kind")!=category: continue
                if query and query not in json.dumps(f,ensure_ascii=False).casefold(): continue
                url=f.get("url",""); safe=url.startswith("https://")
                content+=f'<article><span class=tag>{escape(f.get("kind",""))}</span><h2>{escape(f["company"])} â€” {escape(f["title"])}</h2>'
                if safe: content+=f'<a target=_blank rel="noopener noreferrer" href="{escape(url,quote=True)}">Open listing</a>'
                for label,key in [("Fit","fit_reason"),("Company","company_details"),("Location","location"),("Language","language"),("Eligibility","eligibility"),("Evidence","evidence_quote")]:
                    content+=f'<p><b>{label}:</b> {escape(f.get(key,"Unknown"))}</p>'
                content+='<details><summary>How was this found?</summary>'
                if not f.get("discovery_trails"): content+='<p>Discovery trail unavailable for this older result.</p>'
                for trail in f.get("discovery_trails",[]):
                    content+='<p>Search: '+escape(trail["query"])+' · result '+str(trail["result_rank"])+'</p>'
                    content+='<p>Run: '+escape(trail["run_id"])+' · observed: '+escape(trail.get("observed_at") or "Unknown")+'</p><ol>'
                    for step in trail["path"]: content+='<li>'+escape(step)+'</li>'
                    content+='</ol>'
                content+='</details>'
                reasons=f.get("rejection_reasons") or f.get("concerns",[])
                content+='<p><b>Reasons / concerns:</b> '+escape('; '.join(reasons))+'</p>'
                content+=f'<form method=post action=/decision><input type=hidden name=csrf value="{csrf}"><input type=hidden name=id value="{f["id"]}"><select name=decision>'
                for d in ("unreviewed","saved","apply_anyway","applied","dismissed"):
                    content+=f'<option value="{d}" '+('selected' if f['decision']==d else '')+'>'+d.replace('_',' ').title()+'</option>'
                content+=f'</select><br><textarea name=note placeholder="Your notes">{escape(f["note"])}</textarea><br><button>Save decision</button></form></article>'
            self.send(200,'<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Job Seeker</title><style>'+STYLE+'</style></head><body>'+content+'</body></html>')
        def do_POST(self):
            if not self.valid_host() or self.headers.get("Origin")!=origin: return self.send(403,"Invalid origin")
            try: size=int(self.headers.get("Content-Length","0"))
            except ValueError: return self.send(400,"Invalid request")
            if not 0<size<=10000: return self.send(413,"Request too large")
            data=parse_qs(self.rfile.read(size).decode())
            if not secrets.compare_digest(data.get("csrf",[""])[0],csrf): return self.send(403,"Invalid token")
            if self.path=="/decision":
                try: catalog.decide(data.get("id",[""])[0],data.get("decision",[""])[0],data.get("note",[""])[0])
                except ValueError: return self.send(400,"Invalid decision")
            elif self.path=="/run":
                with lock:
                    if running["active"]: return self.send(409,"A run is already active")
                    running.update(active=True,status="Search running. Refresh to see new results.")
                def work():
                    try:
                        from .runner import run
                        _,result=run(); running["status"]="Search "+result["status"]
                    except Exception: running["status"]="Could not start. Check configuration and credentials."
                    finally: running["active"]=False
                threading.Thread(target=work,daemon=True).start()
            else: return self.send(404,"Not found")
            self.send_response(303); self.send_header("Location","/"); self.end_headers()
    print(f"Dashboard: {origin} (keep this process running)")
    ThreadingHTTPServer(("127.0.0.1",port),Handler).serve_forever()
