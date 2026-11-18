from http.server import BaseHTTPRequestHandler
from pathlib import Path
import json, sys, tempfile, time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scanner import (analyze_prices,scan_solidity_source,analyze_oracle_data,
                     analyze_pool_data,analyze_transaction_data,build_report)

MAX_BODY=2_000_000

class handler(BaseHTTPRequestHandler):
    def send_json(self,status,obj):
        raw=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.rstrip("/") not in ("/api/scan",""):
            return self.send_json(404,{"error":"Not found"})
        self.send_json(200,{"service":"DeFi & Token Intelligence Scanner","version":"0.2.0","status":"ok","method":"POST","demo_available":True})

    def do_POST(self):
        if self.path.rstrip("/")!="/api/scan":
            return self.send_json(404,{"error":"Not found"})
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size<=0 or size>MAX_BODY:
                return self.send_json(413,{"error":"Request body must be between 1 byte and 2 MB"})
            data=json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(data,dict):
                return self.send_json(400,{"error":"JSON body must be an object"})

            if data.get("demo") is True:
                import numpy as np, pandas as pd
                rng=np.random.default_rng(42); n=400
                common=rng.normal(0,.012,n)
                btc=50000*np.exp(np.cumsum(common+rng.normal(0,.009,n)))
                eth=2500*np.exp(np.cumsum(.75*common+rng.normal(0,.010,n)))
                with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",encoding="utf-8") as f:
                    pd.DataFrame({"date":pd.date_range("2025-01-01",periods=n,freq="D"),"BTC":btc,"ETH":eth}).to_csv(f.name,index=False)
                    market=analyze_prices(f.name)
                now=int(time.time())
                contract=scan_solidity_source("contract Demo { function withdraw() public { require(tx.origin == msg.sender); } function pay(address a) public { a.call(\"\"); } }")
                oracle=analyze_oracle_data([{"source":"oracle_A","price":100,"timestamp":now-60},{"source":"market_B","price":104,"timestamp":now-60},{"source":"oracle_C","price":0,"timestamp":now-60}],now)
                pools=analyze_pool_data([{"pool":"demo-pool","timestamp":now-7200,"reserve_usd":1000000},{"pool":"demo-pool","timestamp":now-3600,"reserve_usd":600000}])
                txs=analyze_transaction_data([{"tx_hash":"0xdemo","value_usd":250000,"calls_in_tx":22,"borrow_events":1,"repay_events":1,"unique_protocols":3}])
            else:
                source=data.get("solidity_source",""); csv_text=data.get("prices_csv","")
                if not isinstance(source,str) or not isinstance(csv_text,str):
                    return self.send_json(400,{"error":"solidity_source and prices_csv must be strings"})
                if len(source)>500000 or len(csv_text)>1500000:
                    return self.send_json(413,{"error":"Source or CSV exceeds size limit"})
                market=None
                if csv_text.strip():
                    with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",encoding="utf-8") as f:
                        f.write(csv_text); f.flush()
                        market=analyze_prices(f.name,str(data.get("asset_x","BTC")),str(data.get("asset_y","ETH")),float(data.get("quantile",.05)))
                contract=scan_solidity_source(source) if source.strip() else []
                oracle_data=data.get("oracle_observations",[])
                pool_data=data.get("pool_snapshots",[])
                tx_data=data.get("transactions",[])
                for name,rows in (("oracle_observations",oracle_data),("pool_snapshots",pool_data),("transactions",tx_data)):
                    if not isinstance(rows,list):
                        return self.send_json(400,{"error":name+" must be a JSON array"})
                    if len(rows)>10000:
                        return self.send_json(413,{"error":name+" exceeds 10000 records"})
                oracle=analyze_oracle_data(oracle_data,max_age_seconds=int(data.get("max_oracle_age_seconds",3600)),max_deviation=float(data.get("max_oracle_deviation",.03)))
                pools=analyze_pool_data(pool_data,max_drop=float(data.get("max_pool_drop",.30)))
                txs=analyze_transaction_data(tx_data,large_value_usd=float(data.get("large_value_usd",100000)),max_calls=int(data.get("max_calls",20)))
            if not any((market,contract,oracle,pools,txs)):
                return self.send_json(400,{"error":"Provide at least one data source or set demo=true"})
            self.send_json(200,build_report(market,contract,oracle,pools,txs))
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
            self.send_json(400,{"error":str(exc)})
        except Exception as exc:
            self.send_json(500,{"error":"Analysis failed","detail":str(exc)[:400]})
