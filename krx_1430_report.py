#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os,json,re,time,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
import requests,pandas as pd
from bs4 import BeautifulSoup
KST=timezone(timedelta(hours=9)); NOW=datetime.now(KST)
BASE="https://finance.naver.com"; H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36","Referer":"https://finance.naver.com/"}
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN",""); CHAT=os.getenv("TELEGRAM_CHAT_ID","@sang_red")
HIST=Path("data/turnover_2000_history.json"); MIN=200_000_000_000
def n(v):
 s=str(v).replace(",","").replace("%","").replace("+","").strip()
 try:return float(s)
 except:return None
def market(sosok):
 out=[]
 # Naver's legacy HTML can return an empty body to GitHub-hosted runners.
 # Use the mobile JSON endpoint first; it is stable on Actions.
 page=1
 while page<=60:
  url=f"https://m.stock.naver.com/api/stocks/marketValue/{'KOSPI' if sosok==0 else 'KOSDAQ'}?page={page}&pageSize=50"
  resp=requests.get(url,headers=H,timeout=15)
  resp.raise_for_status()
  data=resp.json()
  items=data.get("stocks") or data.get("items") or []
  if not items: break
  for x in items:
   code=str(x.get("itemCode") or x.get("stockCode") or "")
   name=x.get("stockName") or x.get("itemName") or ""
   close=n(x.get("closePrice") or x.get("nowVal") or x.get("currentPrice"))
   pct=n(x.get("fluctuationsRatio") or x.get("changeRate") or x.get("rate"))
   vol=n(x.get("accumulatedTradingVolume") or x.get("accumulatedTradingVolumeValue") or x.get("volume"))
   turnover=n(x.get("accumulatedTradingValue") or x.get("tradingValue"))
   if not code or close is None or pct is None: continue
   if turnover is not None:
    # API trading value is commonly reported in million KRW.
    if turnover < 1e9: turnover*=1_000_000
   elif vol is not None: turnover=close*vol
   else: continue
   out.append({"code":code,"name":name,"close":close,"pct":pct,"volume":vol or 0,"turnover":turnover})
  if len(items)<50: break
  page+=1
 return out
def themes():
 out=[]
 for p in range(1,8):
  soup=BeautifulSoup(requests.get(f"{BASE}/sise/theme.naver?page={p}",headers=H,timeout=15).text,"html.parser")
  for a in soup.select("td.col_type1 a"):
   if "no=" in a.get("href",""):out.append((a.get_text(strip=True),BASE+a["href"]))
 return out
def members(url):
 soup=BeautifulSoup(requests.get(url,headers=H,timeout=12).text,"html.parser"); out=[]
 for a in soup.select("table.type_5 a"):
  m=re.search(r"code=(\d+)",a.get("href",""))
  if m:out.append(m.group(1))
 return list(dict.fromkeys(out))
def idx(code):
 soup=BeautifulSoup(requests.get(f"{BASE}/sise/sise_index.naver?code={code}",headers=H,timeout=12).text,"html.parser")
 v=n(soup.select_one("#now_value").get_text(strip=True)) if soup.select_one("#now_value") else None
 t=soup.select_one("#change_value_and_rate"); pct=None
 if t:
  z=re.findall(r"[-+]?\d+(?:\.\d+)?%",t.get_text(" ",strip=True))
  if z:pct=n(z[-1])
 return v,pct
def high(code):
 soup=BeautifulSoup(requests.get(f"{BASE}/item/main.naver?code={code}",headers=H,timeout=10).text,"html.parser")
 for td in soup.select("table.no_info td"):
  s=td.get_text(" ",strip=True)
  if "고가" in s:
   z=re.findall(r"[\d,]+",s)
   if z:return n(z[-1])
def send(msg):
 if not TOKEN:raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
 while msg:
  cut=min(3900,len(msg))
  if len(msg)>3900:
   q=msg.rfind("\n",0,3900); cut=q if q>1000 else 3900
  part,msg=msg[:cut],msg[cut:].lstrip()
  r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHAT,"text":part,"disable_web_page_preview":True},timeout=20);r.raise_for_status()
def money(x):return f"{x/1e8:,.0f}억"
def main():
 stocks=market(0)+market(1)
 if len(stocks)<1000:raise RuntimeError(f"snapshot too small {len(stocks)}")
 by={x["code"]:x for x in stocks}; kp,kpp=idx("KOSPI"); kd,kdp=idx("KOSDAQ")
 scored=[]
 for name,url in themes():
  ms=[by[c] for c in members(url) if c in by]
  if len(ms)<2:continue
  pos=sum(x["pct"]>0 for x in ms); avg=sum(x["pct"] for x in ms)/len(ms); top=sorted(ms,key=lambda x:(x["pct"],x["turnover"]),reverse=True)[:8]
  score=avg*2+pos/len(ms)*4+math.log10(max(sum(x["turnover"] for x in top),1))/10
  scored.append((score,name,pos,len(ms),avg,top))
 scored.sort(reverse=True); leaders=[];used=[]
 for r in scored:
  codes={x["code"] for x in r[5]}
  if any(len(codes&u)/max(1,len(codes|u))>.55 for u in used):continue
  leaders.append(r);used.append(codes)
  if len(leaders)==5:break
 big=sorted([x for x in stocks if x["turnover"]>=MIN and x["pct"]>=2],key=lambda x:x["pct"],reverse=True)
 try:hist=json.loads(HIST.read_text(encoding="utf-8"))
 except:hist={}
 today=NOW.strftime("%Y-%m-%d"); prev=sorted(d for d in hist if d<today); d1=[]
 if prev:
  for old in hist[prev[-1]]:
   cur=by.get(old["code"])
   if cur and old["close"]:
    hi=high(old["code"]); cp=(cur["close"]/old["close"]-1)*100; hp=(hi/old["close"]-1)*100 if hi else cp; d1.append((hp,cp,cur,old))
  d1.sort(reverse=True)
 hist[today]=[{"code":x["code"],"name":x["name"],"close":x["close"],"turnover":round(x["turnover"]),"pct":x["pct"]} for x in big]
 for k in sorted(hist)[:-45]:hist.pop(k,None)
 HIST.parent.mkdir(exist_ok=True);HIST.write_text(json.dumps(hist,ensure_ascii=False,indent=2),encoding="utf-8")
 def ix(v,p):
  if v is None: return "데이터 확인중"
  return f"{(p or 0):+.2f}%·{v:,.2f}"
 L=[f"📌 {NOW:%m/%d} 14:30 주도 섹터/테마 현황","",f"코스피 {ix(kp,kpp)}, 코스닥 {ix(kd,kdp)}","※ 14:30 전후 현재가 기준. 거래대금은 현재가×누적거래량 추정치.",""]
 for i,r in enumerate(leaders):
  _,name,pos,total,avg,top=r;L += [f"✅ {i+1}위 {name}",f"상승 {pos}/{total} · 평균 {avg:+.2f}%"]
  for x in top:L.append(f"[{x['pct']:+.2f}%/ {money(x['turnover'])}] {x['name']}"+(" / 거래대금 2,000억 돌파" if x["turnover"]>=MIN else ""))
  L.append("")
 L+=["🔥 거래대금 2,000억 돌파 (+2% 이상)"]
 L += [f"[{x['pct']:+.2f}%/ {money(x['turnover'])}] {x['name']}" for x in big[:20]] or ["해당 종목 없음"];L.append("")
 L.append("📊 전일 2,000억 돌파 종목 D+1 성과")
 if d1:
  for hp,cp,cur,old in d1[:20]:L.append(f"[장중최고 {hp:+.2f}% / 현재 {cp:+.2f}%] {cur['name']} (전일 {money(old['turnover'])})")
  hs=[x[0] for x in d1];cs=[x[1] for x in d1];L+=["",f"대상 {len(d1)}종목 · 장중최고 평균 {sum(hs)/len(hs):+.2f}% · 중앙값 {pd.Series(hs).median():+.2f}%",f"현재 평균 {sum(cs)/len(cs):+.2f}% · 중앙값 {pd.Series(cs).median():+.2f}%",f"장중 +3% 도달률 {sum(x>=3 for x in hs)/len(hs)*100:.1f}% · 현재 플러스 유지율 {sum(x>0 for x in cs)/len(cs)*100:.1f}%"]
 else:L.append("누적 데이터 없음 — 오늘 저장 후 다음 거래일부터 자동 계산")
 if leaders:L+=["",f"🏆 현재 대장 섹터: {leaders[0][1]}","유지 체크: 대장주 상승 유지 + 2,000억 거래대금 종목 확산","이탈 체크: 대장주 동반 음전 + 고거래대금 종목 상승분 반납"]
 msg="\n".join(L);Path("results").mkdir(exist_ok=True);Path(f"results/krx_1430_{NOW:%Y%m%d}.txt").write_text(msg,encoding="utf-8");send(msg);print(msg)
if __name__=="__main__":main()
