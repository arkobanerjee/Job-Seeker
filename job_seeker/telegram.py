"""Owner-only status notifications; never accepts destinations from model output."""
import os
import httpx

class DeliveryRejected(ValueError):
    pass

class DeliveryUncertain(ValueError):
    pass

def notify(result,on_checkpoint=None):
    token=os.getenv("TELEGRAM_BOT_TOKEN","")
    chat=os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat or not chat.lstrip("-").isdigit():
        raise ValueError("Set TELEGRAM_BOT_TOKEN and your TELEGRAM_CHAT_ID in .env")
    findings=result.get("findings",[])
    if result.get("scheduled"): findings=[f for f in findings if f.get("opportunity_change") in ("new","changed")]
    text=(f"Job Seeker: {result['status']}\n"
          f"Shortlist: {sum(x['kind']=='vacancy' for x in findings)}\n"
          f"Rejected / manual review: {sum(x['kind']=='excluded' for x in findings)}\n"
          f"Run: {result['run_id']}\nOpen your dashboard to review. No applications sent.")
    if result.get("scheduled"):
        text+="\nNew/changed opportunities:\n"+"\n".join((f.get("company","")+" — "+f.get("title","")+" ("+f.get("opportunity_change","")+")")[:250] for f in findings[:5])
    from .outbox import Outbox
    from .settings import ROOT
    outbox=Outbox(ROOT/"runs/outbox.sqlite3")
    import hashlib
    ident="completion:"+result["run_id"]+":"+hashlib.sha256(text.encode()).hexdigest()[:16]
    outbox.enqueue(ident,text)
    return outbox.deliver(ident,before_send=on_checkpoint)

def send(text,force_reply=False):
    from . import telemetry as audit
    import time
    state=audit.ACTIVE.get();started=time.monotonic()
    row=audit.start(state,'telegram','delivery',message_bytes=len(text.encode()),force_reply=force_reply)
    try:
        result=_send(text,force_reply)
        audit.finish(state,row,'success',duration_ms=round((time.monotonic()-started)*1000,2))
        return result
    except Exception as exc:
        audit.finish(state,row,'uncertain' if isinstance(exc,DeliveryUncertain) else 'failed',error_type=type(exc).__name__,duration_ms=round((time.monotonic()-started)*1000,2));raise

def _send(text,force_reply=False):
    token=os.getenv("TELEGRAM_BOT_TOKEN","")
    chat=os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat or not chat.lstrip("-").isdigit(): raise ValueError("Telegram owner is not configured")
    try:
        with httpx.Client(timeout=20,trust_env=False) as client:
            response=client.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":chat,"text":text,**({"reply_markup":{"force_reply":True,"input_field_placeholder":"Type your answer"}} if force_reply else {})})
        if response.status_code!=200 or not response.json().get("ok"): raise DeliveryRejected("Telegram delivery failed")
        return response.json()["result"]["message_id"]
    except httpx.HTTPError:
        raise DeliveryUncertain("Telegram outcome uncertain; check delivery before retrying") from None
    except DeliveryRejected:
        raise
    except Exception:
        raise DeliveryUncertain("Telegram outcome uncertain") from None
