"""Owner-only status notifications; never accepts destinations from model output."""
import os
import httpx

def notify(result):
    token=os.getenv("TELEGRAM_BOT_TOKEN","")
    chat=os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat or not chat.lstrip("-").isdigit():
        raise ValueError("Set TELEGRAM_BOT_TOKEN and your TELEGRAM_CHAT_ID in .env")
    findings=result.get("findings",[])
    text=(f"Job Seeker: {result['status']}\n"
          f"Shortlist: {sum(x['kind']=='vacancy' for x in findings)}\n"
          f"Rejected / manual review: {sum(x['kind']=='excluded' for x in findings)}\n"
          f"Run: {result['run_id']}\nOpen your dashboard to review. No applications sent.")
    send(text)

def send(text,force_reply=False):
    token=os.getenv("TELEGRAM_BOT_TOKEN","")
    chat=os.getenv("TELEGRAM_CHAT_ID","")
    if not token or not chat or not chat.lstrip("-").isdigit(): raise ValueError("Telegram owner is not configured")
    try:
        with httpx.Client(timeout=20,trust_env=False) as client:
            response=client.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":chat,"text":text,**({"reply_markup":{"force_reply":True,"input_field_placeholder":"Type your answer"}} if force_reply else {})})
        if response.status_code!=200 or not response.json().get("ok"): raise ValueError("Telegram delivery failed")
        return response.json()["result"]["message_id"]
    except Exception:
        raise ValueError("Telegram delivery failed; check bot and owner chat configuration") from None
