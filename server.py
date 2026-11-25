#!/usr/bin/env python3
"""SpeakerDesigner 2.5.2 Online backend (stdlib, deployable)."""
import http.server, socketserver, urllib.parse, urllib.request, urllib.error, json, re, os, socket, ipaddress, html
from html.parser import HTMLParser
from pathlib import Path
BASE=Path(__file__).resolve().parent
PORT=int(os.environ.get('PORT','8080'))
USER_AGENT='Mozilla/5.0 (compatible; SpeakerDesigner/2.5.2)'
MAX_BYTES=12_000_000

class DDGParser(HTMLParser):
    """Parse DuckDuckGo HTML results without depending on brittle nested markup."""
    def __init__(self):
        super().__init__(); self.items=[]; self.current=None; self.capture=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); cls=a.get('class','')
        if tag=='a' and ('result__a' in cls or 'result__url' in cls):
            if self.current and self.current.get('title'): self.items.append(self.current)
            self.current={'title':'','url':a.get('href',''),'snippet':''}; self.capture='title'
        elif self.current and tag in ('div','span') and 'result__snippet' in cls:
            self.capture='snippet'
    def handle_endtag(self,tag):
        if tag=='a' and self.capture=='title': self.capture=None
        elif tag in ('div','span') and self.capture=='snippet': self.capture=None
    def handle_data(self,data):
        if self.current and self.capture in ('title','snippet'): self.current[self.capture]+=data
    def close(self):
        super().close()
        if self.current and self.current.get('title'): self.items.append(self.current)

def validate_public_url(url):
    u=urllib.parse.urlparse(url)
    if u.scheme not in ('http','https') or not u.hostname: raise ValueError('Alleen openbare http(s)-URL’s zijn toegestaan.')
    if u.username or u.password: raise ValueError('URL’s met login-gegevens zijn niet toegestaan.')
    try:
        ips=socket.getaddrinfo(u.hostname,None)
        for info in ips:
            ip=ipaddress.ip_address(info[4][0])
            if not ip.is_global: raise ValueError('URL naar een lokaal/privé netwerk geblokkeerd.')
    except socket.gaierror: raise ValueError('Hostnaam niet bereikbaar.')
    return u

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)
OPENER=urllib.request.build_opener(SafeRedirect())
def fetch_url(url,max_bytes=MAX_BYTES):
    validate_public_url(url)
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/pdf,text/html,*/*'})
    with OPENER.open(req,timeout=22) as r:
        ct=r.headers.get('Content-Type','').lower()
        cd=r.headers.get('Content-Disposition','')
        data=r.read(max_bytes+1)
        if len(data)>max_bytes: raise ValueError('Bestand te groot voor import (limiet 12 MB).')
        return ct,data,cd

def unwrap_search_url(link):
    """Decode search-engine redirect wrappers to the actual destination."""
    for _ in range(3):
        u=urllib.parse.urlparse(link)
        qs=urllib.parse.parse_qs(u.query)
        candidate=(qs.get('uddg') or qs.get('url') or qs.get('q') or [None])[0]
        if candidate and candidate.startswith(('http://','https://')):
            link=candidate
        else:
            break
    return link

def search(query):
    queries=[
        query+' loudspeaker driver datasheet T/S parameters',
        query+' Thiele Small parameters pdf',
        query+' speaker manufacturer datasheet',
    ]
    out=[]; seen=set()
    for term in queries:
        url='https://html.duckduckgo.com/html/?q='+urllib.parse.quote(term)
        req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT})
        with OPENER.open(req,timeout=20) as r:
            raw=r.read(3_000_000).decode('utf-8','replace')
        parser=DDGParser(); parser.feed(raw); parser.close()
        for x in parser.items:
            link=unwrap_search_url(x.get('url','').strip())
            title=re.sub(r'\s+',' ',x.get('title','')).strip()
            snip=re.sub(r'\s+',' ',x.get('snippet','')).strip()
            if not link or not title or link in seen: continue
            seen.add(link)
            pdfish=bool(re.search(r'\.pdf(?:$|[?#])',link,re.I) or 'pdf' in title.lower() or 'datasheet' in title.lower())
            out.append({'title':title,'url':link,'snippet':snip,'is_pdf':pdfish})
        if len(out)>=8: break
    return out[:15]
def html_text(data):
    raw=data.decode('utf-8','replace'); raw=re.sub(r'(?is)<script.*?</script>|<style.*?</style>', ' ', raw); raw=re.sub(r'(?is)<[^>]+>', ' ', raw)
    return html.unescape(re.sub(r'\s+',' ',raw))[:120000]
def pdf_text(data):
    try:
        import fitz
        doc=fitz.open(stream=data,filetype='pdf')
        return '\n'.join(p.get_text() for p in doc)[:200000]
    except Exception as e: raise RuntimeError('PDF uitlezen mislukt; server-dependency PyMuPDF ontbreekt mogelijk. '+str(e))
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(BASE),**kwargs)
    def _json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path)
        if p.path=='/api/health': return self._json({'ok':True,'service':'SpeakerDesigner Online API','version':'2.5.2-online'})
        if p.path=='/api/search':
            q=urllib.parse.parse_qs(p.query).get('q',[''])[0].strip()
            if not q: return self._json({'error':'Vul merk en model in.'},400)
            if len(q)>160: return self._json({'error':'Zoekterm is te lang.'},400)
            try: return self._json({'results':search(q)})
            except Exception as e: return self._json({'error':'Online zoeken is mislukt: '+str(e)},502)
        if p.path=='/api/pdf':
            url=urllib.parse.parse_qs(p.query).get('url',[''])[0]
            try:
                ct,data,cd=fetch_url(url)
                is_pdf=(b'%PDF' in data[:4096] or 'application/pdf' in ct or '.pdf' in cd.lower())
                is_html=('html' in ct or data[:512].lower().find(b'<html')>=0 or data[:512].lower().find(b'<!doctype html')>=0)
                if is_pdf: textout=pdf_text(data)
                elif is_html: textout=html_text(data)
                else: return self._json({'error':'Bron is geen herkenbare PDF of HTML. Content-Type: '+ct},400)
                return self._json({'text':textout,'bytes':len(data),'content_type':ct,'source_type':'pdf' if is_pdf else 'html'})
            except Exception as e: return self._json({'error':str(e)},502)
        if p.path in ('/','/index.html'):
            self.path='/index.html'
        return super().do_GET()
    def log_message(self,fmt,*args): print('[SpeakerDesigner Online]',fmt%args)
class Server(socketserver.ThreadingMixIn,http.server.HTTPServer):
    daemon_threads=True; allow_reuse_address=True
if __name__=='__main__':
    with Server(('0.0.0.0',PORT),Handler) as server:
        print(f'SpeakerDesigner Online 2.5.2 listening on 0.0.0.0:{PORT}',flush=True); server.serve_forever()
