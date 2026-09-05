import http.cookiejar
import re
import urllib.parse
import urllib.request

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
page = op.open("http://127.0.0.1:8000/login/").read().decode()
tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
data = urllib.parse.urlencode(
    {"username": "admin", "password": "DemoAdmin123!", "csrfmiddlewaretoken": tok}
).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/login/",
    data=data,
    headers={"Referer": "http://127.0.0.1:8000/login/"},
)
op.open(req)
html = op.open("http://127.0.0.1:8000/dashboard/").read().decode()
print("ollama_in_dashboard", "ollama" in html.lower())
print("has_table", "<table" in html)
print("max_w_7xl", "max-w-7xl" in html)
print("needs_attention", "Needs attention" in html)
m = re.search(r"/deal/(\d+)/", html)
print("deal_link", m.group(0) if m else None)
if m:
    det = op.open("http://127.0.0.1:8000" + m.group(0)).read().decode()
    print("ollama_in_detail", "ollama" in det.lower())
    print("rag_facts_label", "RAG facts" in det)
    print("save_reply_label", "Save reply" in det)
    print("email_to_send", "Email to send" in det)
    print("ai_log", "AI log" in det)
    print("policy_used", "Policy used" in det)
    print("human_notes", "Your notes" in det or "Human notes" in det)
    print("rag_facts_label", "RAG facts" in det)
    print("negotiation_history", "Negotiation history" in det)
