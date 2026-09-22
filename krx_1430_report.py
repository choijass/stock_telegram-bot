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
def api_json(url):
 r=requests.get(url,headers=H,timeout=15); r.raise_for_status(); return r.json()
def themes():
 # Mobile theme list API; fallback to empty list if endpoint changes.
 for url in ["https://m.stock.naver.com/api/theme/local?page=1&pageSize=200","https://m.stock.naver.com/api/theme/domestic?page=1&pageSize=200"]:
  try:
   d=api_json(url); items=d.get("themes") or d.get("items") or d.get("result") or []
   out=[]
   for x in items:
    no=str(x.get("themeCode") or x.get("no") or x.get("code") or "")
    name=x.get("themeName") or x.get("name") or ""
    if no and name: out.append((name,no))
   if out:return out
  except:pass
 return []
def members(theme_code):
 for url in [f"https://m.stock.naver.com/api/theme/{theme_code}",f"https://m.stock.naver.com/api/theme/{theme_code}/stocks"]:
  try:
   d=api_json(url); items=d.get("stocks") or d.get("items") or d.get("result") or []
   out=[]
   for x in items:
    code=str(x.get("itemCode") or x.get("stockCode") or x.get("code") or "")
    if code:out.append(code)
   if out:return list(dict.fromkeys(out))
  except:pass
 return []
def idx(code):
 # Mobile index API first.
 for url in [f"https://m.stock.naver.com/api/index/{code}/basic",f"https://m.stock.naver.com/api/index/{code}"]:
  try:
   d=api_json(url)
   v=n(d.get("closePrice") or d.get("nowVal") or d.get("currentPrice"))
   p=n(d.get("fluctuationsRatio") or d.get("changeRate") or d.get("rate"))
   if v is not None:return v,p
  except:pass
 return None,None
def daily_info(code):
 # Daily candles: today high, 20-day turnover avg, 52w/all-time high.
 try:
  d=api_json(f"https://m.stock.naver.com/api/stock/{code}/price?pageSize=400&page=1")
  items=d if isinstance(d,list) else (d.get("priceInfos") or d.get("items") or d.get("result") or [])
  rows=[]
  for x in items:
   close=n(x.get("closePrice") or x.get("close")); hi=n(x.get("highPrice") or x.get("high"))
   vol=n(x.get("accumulatedTradingVolume") or x.get("volume")); tv=n(x.get("accumulatedTradingValue") or x.get("tradingValue"))
   if close is None:continue
   if tv is not None and tv<1e9:tv*=1_000_000
   if tv is None and vol is not None:tv=close*vol
   rows.append((close,hi or close,tv or 0))
  if not rows:return {}
  hist20=[r[2] for r in rows[1:21] if r[2]>0]
  highs=[r[1] for r in rows]
  return {"high":rows[0][1],"avg20_turnover":sum(hist20)/len(hist20) if hist20 else 0,
          "high52":max(highs[:250]) if highs else 0,"high_all":max(highs) if highs else 0}
 except:return {}
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
 # Enrich relevant names with 20-day turnover and breakout flags.
 enrich_codes={x["code"] for x in sorted(stocks,key=lambda z:(z["pct"],z["turnover"]),reverse=True)[:120]}
 for r in leaders:
  enrich_codes.update(x["code"] for x in r[5])
 enrich={}
 for code in list(enrich_codes):
  enrich[code]=daily_info(code)
 for x in stocks:
  e=enrich.get(x["code"],{})
  avg=e.get("avg20_turnover",0)
  x["turnover_ratio"]=x["turnover"]/avg if avg else None
  x["surge"]=bool(x["turnover_ratio"] and x["turnover_ratio"]>=2.0)
  x["high52"]=bool(e.get("high52") and x["close"]>=e["high52"]*0.995)
  x["ath"]=bool(e.get("high_all") and x["close"]>=e["high_all"]*0.995)
  x["turnover20_break"]=bool(e.get("max20_turnover") and x["turnover"]>e["max20_turnover"])
  x["ma20_break"]=bool(e.get("ma20") and e.get("prev_close") and e["prev_close"]<e["ma20"]<=x["close"])
  x["vcp"]=bool(e.get("vcp_proxy") and x["close"]>=e.get("pivot20",1)*0.98)
  x["near52"]=((x["close"]/e["high52"]-1)*100) if e.get("high52") else None
 big=sorted([x for x in stocks if x["turnover"]>=MIN and x["pct"]>=2],key=lambda x:x["pct"],reverse=True)
 try:hist=json.loads(HIST.read_text(encoding="utf-8"))
 except:hist={}
 today=NOW.strftime("%Y-%m-%d"); prev=sorted(d for d in hist if d<today); d1=[]
 if prev:
  for old in hist[prev[-1]]:
   cur=by.get(old["code"])
   if cur and old["close"]:
    hi=daily_info(old["code"]).get("high"); cp=(cur["close"]/old["close"]-1)*100; hp=(hi/old["close"]-1)*100 if hi else cp; d1.append((hp,cp,cur,old))
  d1.sort(reverse=True)
 hist[today]=[{"code":x["code"],"name":x["name"],"close":x["close"],"turnover":round(x["turnover"]),"pct":x["pct"]} for x in big]
 for k in sorted(hist)[:-45]:hist.pop(k,None)
 HIST.parent.mkdir(exist_ok=True);HIST.write_text(json.dumps(hist,ensure_ascii=False,indent=2),encoding="utf-8")
 def ix(v,p):
  if v is None: return "데이터 확인중"
  return f"{(p or 0):+.2f}%·{v:,.2f}"
 up=sum(x["pct"]>0 for x in stocks); down=sum(x["pct"]<0 for x in stocks)
 L=[f"🇰🇷 [국내장] 실시간 지표 정리 — 확장판",f"{NOW:%Y-%m-%d} / 15:30 정규장 마감 기준","",f"KOSPI {ix(kp,kpp)} / KOSDAQ {ix(kd,kdp)}",f"시장 폭: 상승 {up}개 / 하락 {down}개",f"시장 색깔: "+("상승 확산형" if up>down*1.2 else "하락 우위·선택적 장세" if down>up*1.2 else "혼조·순환매"),"", "① 20영업일 최고거래대금 돌파"]
 t20=sorted([x for x in stocks if x.get("turnover20_break")],key=lambda x:x["turnover"],reverse=True)
 L += [f"[{x['pct']:+.2f}%/ {money(x['turnover'])}] {x['name']} / 20일 최고 거래대금" for x in t20[:20]] or ["신규 돌파 없음"]
 aths=sorted([x for x in stocks if x.get("ath")],key=lambda x:x["turnover"],reverse=True)
 h52=sorted([x for x in stocks if x.get("high52") and not x.get("ath")],key=lambda x:x["turnover"],reverse=True)
 near=sorted([x for x in stocks if x.get("near52") is not None and -10<=x["near52"]<0],key=lambda x:x["near52"],reverse=True)
 L+=["","② 역사적 신고가 돌파"]+[f"[{x['pct']:+.2f}%] {x['name']} / {money(x['turnover'])}" for x in aths[:15]]
 if not aths:L.append("신규 역사적 신고가 없음")
 L+=["","③ 52주 신고가 돌파"]+[f"[{x['pct']:+.2f}%] {x['name']} / {money(x['turnover'])}" for x in h52[:15]]
 if not h52:L.append("신규 52주 신고가 없음")
 L+=["","④ 역사적·52주 신고가 근접"]+[f"[{x['pct']:+.2f}%] {x['name']} / 52주고점 대비 {x['near52']:.2f}% / {money(x['turnover'])}" for x in near[:15]]
 for i,r in enumerate(leaders):
  _,name,pos,total,avg,top=r;L += [f"✅ {i+1}위 {name}",f"상승 {pos}/{total} · 평균 {avg:+.2f}%"]
  for x in top:
   flags=[]
   if x["turnover"]>=MIN:flags.append("2,000억 돌파")
   if x.get("surge"):flags.append(f"20일比 {x['turnover_ratio']:.1f}배")
   if x.get("ath"):flags.append("역사적 신고가")
   elif x.get("high52"):flags.append("52주 신고가")
   L.append(f"[{x['pct']:+.2f}%/ {money(x['turnover'])}] {x['name']}"+((" / "+" / ".join(flags)) if flags else ""))
  L.append("")
 vcp=sorted([x for x in stocks if x.get("vcp")],key=lambda x:x["turnover"],reverse=True)
 ma=sorted([x for x in stocks if x.get("ma20_break")],key=lambda x:x["turnover"],reverse=True)
 strongclose=sorted([x for x in stocks if enrich.get(x["code"],{}).get("high") and x["close"]/enrich[x["code"]]["high"]>=0.95 and x["pct"]>0],key=lambda x:x["turnover"],reverse=True)
 L+=["","⑤ VCP 구간 돌파시도"]+[f"[{x['pct']:+.2f}%] {x['name']} / 피벗근접·수축형 / {money(x['turnover'])}" for x in vcp[:15]]
 if not vcp:L.append("조건 충족 종목 없음")
 L+=["","⑥ 20MA 구간 돌파시도"]+[f"[{x['pct']:+.2f}%] {x['name']} / 신규 20MA 상향 / {money(x['turnover'])}" for x in ma[:15]]
 if not ma:L.append("조건 충족 종목 없음")
 L+=["","⑦ VWAP 대체: 종가 고가권 유지"]+[f"[{x['pct']:+.2f}%] {x['name']} / 종가÷고가 {x['close']/enrich[x['code']]['high']*100:.1f}% / {money(x['turnover'])}" for x in strongclose[:15]]
 if not strongclose:L.append("고가권 95% 이상 강세 종목 없음")
 L+=["","⑧ 🔥 거래대금 2,000억 이상 (+2% 이상)"]
 if big:
  for x in big[:30]:
   flags=["2,000억 돌파"]
   if x.get("surge"):flags.append(f"20일比 {x['turnover_ratio']:.1f}배")
   if x.get("ath"):flags.append("역사적 신고가")
   elif x.get("high52"):flags.append("52주 신고가")
   L.append(f"[{x['pct']:+.2f}%/ {money(x['turnover'])}] {x['name']} / "+" / ".join(flags))
 else:L.append("해당 종목 없음")
 L.append("")
 surge=sorted([x for x in stocks if x.get("surge") and x["pct"]>0],key=lambda x:x.get("turnover_ratio") or 0,reverse=True)
 L+=["","거래대금 폭증 상세"]
 L += [f"[{x['pct']:+.2f}%/ {money(x['turnover'])}] {x['name']} / {x['turnover_ratio']:.1f}배" for x in surge[:20]] or ["해당 종목 없음"]
 L.append("")
 br=[x for x in stocks if x.get("ath") or x.get("high52")]
 br.sort(key=lambda x:x["pct"],reverse=True)
 L+=["","신고가 상세"]
 L += [f"[{x['pct']:+.2f}%/ {money(x['turnover'])}] {x['name']} / "+("역사적 신고가" if x.get("ath") else "52주 신고가") for x in br[:20]] or ["해당 종목 없음"]
 L.append("")
 L.append("⑩ 📊 전일 2,000억 돌파 종목 D+1 성과")
 if d1:
  for hp,cp,cur,old in d1[:20]:L.append(f"[장중최고 {hp:+.2f}% / 현재 {cp:+.2f}%] {cur['name']} (전일 {money(old['turnover'])})")
  hs=[x[0] for x in d1];cs=[x[1] for x in d1];L+=["",f"대상 {len(d1)}종목 · 장중최고 평균 {sum(hs)/len(hs):+.2f}% · 중앙값 {pd.Series(hs).median():+.2f}%",f"종가 평균 {sum(cs)/len(cs):+.2f}% · 중앙값 {pd.Series(cs).median():+.2f}%",f"장중 +3% 도달률 {sum(x>=3 for x in hs)/len(hs)*100:.1f}% · 종가 플러스 유지율 {sum(x>0 for x in cs)/len(cs)*100:.1f}%"]
 else:L.append("누적 데이터 없음 — 오늘 저장 후 다음 거래일부터 자동 계산")
 if leaders:
  L+=["","# 🔥 오늘 SIGNAL",f"시장 색깔: 거래대금·상승폭·섹터 확산 기준 {leaders[0][1]} 중심 선택적 주도",
      "주도 섹터: "+ " → ".join(f"{i+1} {r[1]}" for i,r in enumerate(leaders)),
      f"거래대금 대장: {max(stocks,key=lambda x:x['turnover'])['name']} {money(max(stocks,key=lambda x:x['turnover'])['turnover'])}",
      f"모멘텀 거래대금 대장: {big[0]['name']} {money(big[0]['turnover'])} / {big[0]['pct']:+.2f}%" if big else "모멘텀 거래대금 대장: 없음",
      "신고가 확산: "+("확인" if br else "약함"),
      "","👀 다음 거래일 우선 체크 Top5"]
  picks=[]
  for r in leaders:
   for x in r[5]:
    if x["code"] not in {p["code"] for p in picks}:picks.append(x)
    if len(picks)>=5:break
   if len(picks)>=5:break
  for i,x in enumerate(picks,1):
   e=enrich.get(x["code"],{}); hi=e.get("high")
   L.append(f"{i}. {x['name']} — 종가 {x['close']:,.0f} / 당일고가 {hi:,.0f}" if hi else f"{i}. {x['name']} — 종가 {x['close']:,.0f}")
  L+=["",f"📌 최종 판단: {leaders[0][1]}이 거래대금과 상승 종목 확산에서 가장 강한 마감 주도 섹터. 다음 거래일에는 대장주 거래대금 승계와 신고가 확산 여부를 우선 확인."]
 msg="\n".join(L);Path("results").mkdir(exist_ok=True);Path(f"results/krx_1530_{NOW:%Y%m%d}.txt").write_text(msg,encoding="utf-8");send(msg);print(msg)
if __name__=="__main__":main()
