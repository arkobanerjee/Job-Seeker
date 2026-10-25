"""Read-only source tools. No shell, browser login, or arbitrary network destinations."""
import http.client
import ipaddress
import json
import os
import socket
import threading
import re
import hashlib
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.robotparser import RobotFileParser

class ServiceFailure(RuntimeError):
    pass

def normalized(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError("Only public HTTPS URLs on port 443 are supported")
    host = p.hostname.encode("idna").decode().lower().rstrip(".")
    if any(host == x or host.endswith("."+x) for x in ("linkedin.com", "localhost", "local", "internal")):
        raise ValueError("Unsupported source")
    return urlunsplit(("https",host,p.path or "/",p.query,""))

def public_addresses(host):
    addresses = list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("Non-public address blocked")
    return addresses

def public_get(url):
    from . import telemetry as audit
    state=audit.ACTIVE.get();started=time.monotonic()
    row=audit.start(state,'http','robots' if urlsplit(url).path=='/robots.txt' else 'public_retrieval',url=url)
    try:
        result=_public_get(url)
        audit.finish(state,row,'success' if result[1]==200 else 'unavailable',http_status=result[1],final_url=result[0],response_bytes=len(result[2].encode()),duration_ms=round((time.monotonic()-started)*1000,2))
        return result
    except Exception as exc:
        audit.finish(state,row,'failed',error_type=type(exc).__name__,duration_ms=round((time.monotonic()-started)*1000,2))
        raise

def _public_get(url):
    """Pin connection to a validated IP while retaining TLS hostname validation."""
    for _ in range(4):
        url = normalized(url)
        p = urlsplit(url)
        addr = public_addresses(p.hostname)[0]
        conn = http.client.HTTPSConnection(p.hostname, timeout=15)
        conn._create_connection = lambda address, timeout=None, source_address=None: socket.create_connection((addr,443), timeout, source_address)
        try:
            conn.request("GET", (p.path or "/") + ("?"+p.query if p.query else ""),
                         headers={"User-Agent":"JobSeekerPrototype/0.1", "Accept":"text/html,text/plain,application/json", "Accept-Encoding":"identity"})
            r = conn.getresponse()
            if r.status in (301,302,303,307,308):
                url = urljoin(url,r.getheader("Location") or "")
                continue
            content_type = r.getheader("Content-Type", "")
            if r.status != 200:
                return url,r.status,""
            if not any(x in content_type for x in ("text/html","text/plain","application/json")):
                raise ValueError("Unsupported content type")
            data = r.read(500_001)
            if len(data) > 500_000:
                raise ValueError("Page exceeds prototype size limit")
            return url,r.status,data.decode("utf-8",errors="replace")
        finally:
            conn.close()
    raise ValueError("Redirect limit reached")

class PageText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hrefs=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript","svg"):
            self.skip += 1
        if tag == "a" and not self.skip:
            self.hrefs.extend(v for k,v in attrs if k == "href" and v)
    def handle_endtag(self, tag):
        if tag in ("script","style","noscript","svg"):
            self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip: self.parts.append(data)

class SourceTools:
    def __init__(self, ledger, persist, max_searches=4, max_fetches=10):
        self.ledger=ledger; self.persist=persist
        self.searches=0; self.fetches=0; self.max_searches=max_searches; self.max_fetches=max_fetches
        self.records={}; self.allowed=set(); self.events=[]; self.cache={}; self.robots={}
        self.lock=threading.RLock()

    def search(self, query):
        from . import telemetry as audit
        state=getattr(self,'audit_state',None) or audit.ACTIVE.get()
        row=audit.search_start(state,query);started=time.monotonic()
        self._search_receipt=row
        try:
            cached=query in self.cache
            result=self._search(query)
            audit.finish(state,row,'cached' if cached else 'rejected' if isinstance(result,dict) else 'success',
                results=(row or {}).get('results',result if isinstance(result,list) else []),
                error=result.get('error') if isinstance(result,dict) else None,
                observed_estimate_usd=0 if cached or isinstance(result,dict) else .008,
                duration_ms=round((time.monotonic()-started)*1000,2))
            self.persist()
            return result
        except Exception as exc:
            if row is not None and 'reservation_id' not in row:row['observed_estimate_usd']=0
            audit.finish(state,row,'blocked' if type(exc).__name__.endswith('LimitExceeded') else 'failed',error_type=type(exc).__name__,duration_ms=round((time.monotonic()-started)*1000,2))
            self.persist();raise
        finally:self._search_receipt=None

    def _search(self, query):
        import httpx
        if not query.strip() or len(query)>350:
            return {"error":"Query must contain 1–350 characters"}
        if any("." not in domain or "/" in domain for domain in re.findall(r"site:([^\s)]+)",query)):
            return {"error":"A site: filter must name an actual domain, e.g. site:jobs.lever.co. Do not invent domains or use site:companies."}
        with self.lock:
            if query in self.cache: return self.cache[query]
            if self.searches>=self.max_searches: return {"error":"Search limit reached; use available evidence or finish"}
            self.searches+=1
            reservation=self.ledger.reserve("tavily_basic",0.008)
            if getattr(self,'_search_receipt',None) is not None:self._search_receipt.update(reservation_id=reservation,reserved_usd=.008)
            self.persist()
        try:
            with httpx.Client(timeout=35,trust_env=False) as client:
                r=client.post("https://api.tavily.com/search",
                    headers={"Authorization":"Bearer "+os.environ["TAVILY_API_KEY"]},
                    json={"query":query,"search_depth":"basic","max_results":5,
                          "include_answer":False,"include_raw_content":False,
                          "exclude_domains":["linkedin.com"],"auto_parameters":False,"include_usage":True})
                if r.status_code!=200: raise ServiceFailure("Tavily HTTP "+str(r.status_code))
                data=r.json()
            self.ledger.observe(reservation,0.008)
        except ServiceFailure: raise
        except Exception:
            raise ServiceFailure("Tavily request failed; inspect connection/configuration before retrying") from None
        with self.lock:
            results=[]
            returned=[]
            for item in data.get("results",[]):
                receipt={'rank':len(returned)+1,'url':str(item.get('url','')),'title':str(item.get('title','')),'snippet':str(item.get('content','')),'score':item.get('score')}
                try: url=normalized(item["url"])
                except (ValueError,KeyError):
                    returned.append({**receipt,'accepted':False,'rejection_reason':'Unsupported source URL'});continue
                returned.append({**receipt,'url':url,'accepted':True})
                self.allowed.add(url)
                results.append({"url":url,"title":str(item.get("title",""))[:250],"snippet":str(item.get("content",""))[:1500]})
            if getattr(self,'_search_receipt',None) is not None:self._search_receipt.update(results=returned,provider_usage=data.get('usage'),provider_request_id=data.get('request_id'))
            self.events.append({"type":"search","query":query,"count":len(results)})
            self.cache[query]=results; self.persist()
            return results

    def fetch(self,url):
        from . import telemetry as audit
        state=getattr(self,'audit_state',None) or audit.ACTIVE.get();started=time.monotonic()
        cached=url in self.records
        row=audit.start(state,'source','fetch',url=url)
        try:
            result=self._fetch(url)
            status='cached' if cached else 'success' if result.get('http_status')==200 else 'unavailable' if url in self.records else 'rejected'
            audit.finish(state,row,status,http_status=result.get('http_status'),source_id=result.get('source_id'),
                ats_provider=result.get('ats_provider'),api_url=result.get('api_url'),
                text_bytes=len(result.get('text','').encode()),duration_ms=round((time.monotonic()-started)*1000,2))
            self.persist();return result
        except Exception as exc:
            audit.finish(state,row,'failed',error_type=type(exc).__name__,duration_ms=round((time.monotonic()-started)*1000,2));raise

    def _fetch(self,url):
        try: url=normalized(url)
        except ValueError: return {"error":"Unsupported URL"}
        with self.lock:
            if url in self.records: return self.records[url]
            if url not in self.allowed: return {"error":"URL must come from search or an observed page link"}
            if self.fetches>=self.max_fetches: return {"error":"Source-fetch limit reached"}
            self.fetches+=1
            self.persist()
        try:
            from .ats import endpoint,parse
            ats=endpoint(url)
            target=ats[3] if ats else url
            p=urlsplit(target); origin=f"https://{p.netloc}"
            with self.lock:
                if origin not in self.robots:
                    _,status,text=public_get(origin+"/robots.txt")
                    if status not in (200,404):
                        raise ValueError("Could not establish robots permission")
                    robot=RobotFileParser(); robot.parse(text.splitlines() if status==200 else [])
                    self.robots[origin]=robot
                if not self.robots[origin].can_fetch("JobSeekerPrototype",target):
                    raise ValueError("Source disallows automated retrieval")
            final,status,html=public_get(target)
            if urlsplit(final).netloc!=p.netloc:
                # Recheck the new origin's robots policy via a new tool call.
                self.allowed.add(final)
                return {"redirect":final,"note":"Fetch this destination separately to check its policy"}
            structured=parse(ats,html) if ats and status==200 else None
            parser=PageText(); parser.feed(html if not structured else '')
            text=" ".join(" ".join(parser.parts).split())[:18000]
            links=[]
            for href in parser.hrefs:
                try: link=normalized(urljoin(final,href))
                except ValueError: continue
                if link not in links and len(links)<30: links.append(link)
            if structured:
                text=structured["text"];links=structured["links"]
            closed_quote=next((text[text.lower().index(x):text.lower().index(x)+len(x)] for x in ("this job is no longer available","this position has been filled","job not found","this job has expired","the vacancy is closed","expired job","this position is closed","this role is no longer available","no longer accepting applications","applications for this position are closed") if x in text.lower()),None)
            closed=closed_quote is not None
            record={"url":url,"final_url":final,"http_status":status,"text":text,
                    "source_id":hashlib.sha256(url.encode()).hexdigest()[:16],
                    "observed_at":datetime.now(timezone.utc).isoformat(),"closed_marker":closed,"closed_marker_quote":closed_quote,"links":links}
            if structured: record.update(structured)
        except (ValueError,TypeError,AttributeError,OSError,http.client.HTTPException):
            record={"url":url,"observed_at":datetime.now(timezone.utc).isoformat(),"error":"Retrieval unavailable, blocked by policy, too large, or unsupported; no closure inference"}
        with self.lock:
            self.allowed.update(record.get("links",[])); self.records[url]=record
            self.events.append({"type":"fetch","url":url,"ok":record.get("http_status")==200})
            self.persist()
        return record
