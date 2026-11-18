from __future__ import annotations
import json, math, re, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

def clayton_copula(u, v, theta):
    if not (0 < u <= 1 and 0 < v <= 1) or not math.isfinite(theta) or theta <= 0:
        raise ValueError("u and v must be in (0,1], theta must be > 0")
    if u == v == 1: return 1.0
    a,b=-theta*math.log(u),-theta*math.log(v); z=np.logaddexp(a,b)
    return float(math.exp(-(z+math.log1p(-math.exp(-z)))/theta))

def _log_density(t,u,v):
    z=np.logaddexp(-t*np.log(u),-t*np.log(v)); s=z+np.log1p(-np.exp(-z))
    return math.log1p(t)-(1+t)*(np.log(u)+np.log(v))-(2+1/t)*s

def estimate_clayton_theta(u,v):
    u=np.clip(np.asarray(u,float),1e-10,1-1e-10); v=np.clip(np.asarray(v,float),1e-10,1-1e-10)
    if len(u)!=len(v) or len(u)<30: raise ValueError("Need at least 30 paired observations")
    f=minimize_scalar(lambda x:-float(_log_density(math.exp(x),u,v).sum()),bounds=(math.log(.001),math.log(50)),method="bounded")
    if not f.success or not np.isfinite(f.fun): raise RuntimeError("Clayton fit failed")
    return math.exp(float(f.x)),-float(f.fun)

def analyze_prices(path,asset_x="BTC",asset_y="ETH",q=.05):
    if not 0<q<.5: raise ValueError("q must be in (0,.5)")
    d=pd.read_csv(path)
    if not {"date",asset_x,asset_y}.issubset(d.columns): raise ValueError("CSV needs date and selected asset columns")
    d["date"]=pd.to_datetime(d.date,errors="coerce",utc=True)
    for c in (asset_x,asset_y): d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=["date",asset_x,asset_y]).sort_values("date").drop_duplicates("date")
    if (d[[asset_x,asset_y]]<=0).any().any(): raise ValueError("Prices must be positive")
    r=np.log(d[[asset_x,asset_y]]).diff().dropna(); n=len(r)
    if n<100: raise ValueError("At least 101 aligned price rows required")
    u=r[asset_x].rank(method="average").to_numpy()/(n+1); v=r[asset_y].rank(method="average").to_numpy()/(n+1)
    theta,ll=estimate_clayton_theta(u,v); x=float(r[asset_x].quantile(q)); y=float(r[asset_y].quantile(q))
    empirical=float(((r[asset_x]<=x)&(r[asset_y]<=y)).mean()); model=clayton_copula(q,q,theta)
    return {"assets":[asset_x,asset_y],"observations":n,"start":str(d.date.iloc[1]),"end":str(d.date.iloc[-1]),"theta_mle":theta,"log_likelihood":ll,"quantile":q,"joint_tail_probability_model":model,"joint_tail_probability_independence":q*q,"joint_tail_frequency_empirical":empirical,"lower_tail_dependence_coefficient":2**(-1/theta),"model_to_independence_ratio":model/(q*q),"warning":"Market dependence estimate, not exploit probability. Validate out-of-sample."}

RULES=[
("ORACLE-001","Legacy latestAnswer call","HIGH",r"\.latestAnswer\s*\(","Review freshness, positivity, decimals and round completeness."),
("AUTH-001","tx.origin used","HIGH",r"\btx\.origin\b","Do not use tx.origin as sole authorization."),
("CALL-001","Low-level call","REVIEW",r"\.call\s*(?:\{|\()","Review checks-effects-interactions and reentrancy protection."),
("CALL-002","delegatecall used","HIGH",r"\.delegatecall\s*\(","Review target allowlisting, authorization and storage layout."),
("AUTH-002","Sensitive function candidate","REVIEW",r"function\s+(?:withdraw|borrow|liquidate|setPrice|setOracle|upgrade|mint|pause)\s*\(","Review access control and invariants."),
("TOKEN-001","Potential privileged token controls","REVIEW",r"function\s+(?:mint|blacklist|setFee|setTax|setMaxTx|pause|setWhitelist)\s*\(","Review roles, limits and event emission."),
("PROXY-001","Proxy upgrade pattern","REVIEW",r"upgradeTo|_authorizeUpgrade|implementation\s*\(","Review upgrade authorization and storage compatibility.")]

def scan_solidity_source(src):
    src=re.sub(r"/\*.*?\*/",lambda m:"\n"*m.group(0).count("\n"),src,flags=re.S); src=re.sub(r"//[^\n]*","",src); lines=src.splitlines(); out=[]
    for rid,title,sev,pat,why in RULES:
        for m in re.finditer(pat,src,flags=re.I):
            n=src.count("\n",0,m.start())+1
            out.append({"id":rid,"title":title,"severity":sev,"line":n,"evidence":lines[n-1].strip() if n<=len(lines) else "","explanation":why,"status":"REVIEW_REQUIRED"})
    return out

def analyze_oracle_data(rows,now=None,max_age_seconds=3600,max_deviation=.03):
    now=int(time.time()) if now is None else int(now); out=[]; valid=[]
    for x in rows:
        src=str(x.get("source","unknown")); p=float(x.get("price",0)); ts=int(x.get("timestamp",0)); age=now-ts
        if p<=0: out.append({"id":"ORACLE-PRICE-001","severity":"HIGH","source":src,"detail":"Non-positive price"})
        if ts<=0 or age<0 or age>max_age_seconds: out.append({"id":"ORACLE-FRESH-001","severity":"HIGH","source":src,"age_seconds":age,"detail":"Missing, future or stale observation"})
        if p>0 and 0<=age<=max_age_seconds: valid.append((src,p))
    if len(valid)>=2:
        med=float(np.median([p for _,p in valid]))
        for src,p in valid:
            dev=abs(p-med)/med if med else float("inf")
            if dev>max_deviation: out.append({"id":"ORACLE-DEVIATION-001","severity":"HIGH","source":src,"price":p,"median_price":med,"deviation":dev,"detail":"Price deviates from supplied-source median"})
    return out

def analyze_pool_data(rows,max_drop=.30):
    groups={}
    for x in rows: groups.setdefault(str(x["pool"]),[]).append(x)
    out=[]
    for pool,items in groups.items():
        items.sort(key=lambda x:int(x["timestamp"]))
        for a,b in zip(items,items[1:]):
            old=float(a.get("reserve_usd",0)); new=float(b.get("reserve_usd",0))
            if old>0 and (old-new)/old>=max_drop: out.append({"id":"LIQUIDITY-DROP-001","severity":"HIGH","pool":pool,"drop_fraction":(old-new)/old,"from_timestamp":a["timestamp"],"to_timestamp":b["timestamp"],"detail":"Large reserve/TVL decline"})
            x=float(b.get("token0_reserve",0)); y=float(b.get("token1_reserve",0))
            if x>0 and y>0 and max(x,y)/min(x,y)>=10: out.append({"id":"LIQUIDITY-IMBALANCE-001","severity":"REVIEW","pool":pool,"reserve_ratio":max(x,y)/min(x,y),"detail":"Raw reserve ratio; normalize token units and prices"})
    return out

def analyze_transaction_data(rows,large_value_usd=100000,max_calls=20):
    out=[]
    for x in rows:
        h=str(x.get("tx_hash","unknown")); val=float(x.get("value_usd",0)); calls=int(x.get("calls_in_tx",0)); bor=int(x.get("borrow_events",0)); rep=int(x.get("repay_events",0)); prot=int(x.get("unique_protocols",0))
        if val>=large_value_usd: out.append({"id":"TX-LARGE-VALUE-001","severity":"REVIEW","tx_hash":h,"value_usd":val,"detail":"Large normalized transaction value"})
        if calls>=max_calls: out.append({"id":"TX-CALL-COUNT-001","severity":"REVIEW","tx_hash":h,"calls_in_tx":calls,"detail":"High internal call count"})
        if bor>0 and rep>0: out.append({"id":"TX-FLASHLIKE-001","severity":"REVIEW","tx_hash":h,"detail":"Borrow and repay in one transaction; may be legitimate flash liquidity"})
        if prot>=3 and calls>=8: out.append({"id":"TX-MULTIPROTOCOL-001","severity":"REVIEW","tx_hash":h,"detail":"Multi-protocol transaction with many calls"})
    return out

def build_report(market=None,contract=None,oracle=None,pools=None,transactions=None):
    groups={"market":market,"smart_contract":contract or [],"oracle":oracle or [],"liquidity":pools or [],"transactions":transactions or []}
    high=sum(1 for g in groups.values() if isinstance(g,list) for x in g if x.get("severity")=="HIGH")
    review=sum(1 for g in groups.values() if isinstance(g,list) for x in g if x.get("severity")=="REVIEW")
    signal=bool(market and market.get("joint_tail_probability_model",0)>.02); score=high*2+review+(2 if signal else 0)
    level="CRITICAL_REVIEW" if score>=8 else "HIGH_REVIEW" if score>=4 else "ELEVATED_REVIEW" if score>=2 else "BASELINE_REVIEW"
    return {"product":"DeFi & Token Intelligence Scanner","version":"0.2.0-vercel","investigation_priority_score":score,"investigation_priority":level,"high_severity_findings":high,"review_findings":review,"market_joint_tail_signal":signal,"exploit_confirmed":False,"groups":groups,"limitations":["Heuristics require manual review.","No finding proves exploitability.","Transaction signals require decoded, normalized chain data.","Clayton measures market dependence, not exploit probability.","This deployment does not automatically ingest live RPC data."]}
