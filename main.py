from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from vnstock import Trading, Quote
import pandas as pd
from typing import List
import time

app = FastAPI(title="SkyStock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = {}
CACHE_TIME = 25

def get_cached(key):
    if key in cache:
        data, ts = cache[key]
        if time.time() - ts < CACHE_TIME:
            return data
    return None

def set_cached(key, data):
    cache[key] = (data, time.time())

@app.get("/")
def home():
    return {"message": "SkyStock API đang chạy", "status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/board")
def get_board(symbols: str = Query(...)):
    cache_key = f"board_{symbols}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    result = []

    try:
        trading = Trading(source="VCI")
        df = trading.price_board(symbols_list=symbol_list)

        if df is not None and not df.empty:
            # Làm phẳng cột nếu là MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ['_'.join(col).strip() for col in df.columns.values]

            for _, row in df.iterrows():
                try:
                    
                    symbol = str(row.get("listing_symbol") or row.get("symbol") or row.get("Mã CP") or "")
                    price = float(row.get("match_match_price") or row.get("match_price") or row.get("Giá") or row.get("close_price") or 0)
                    
                    # Thử nhiều tên cột khác nhau cho phần thay đổi giá
                    change = float(
                        row.get("match_price_change") or 
                        row.get("price_change") or 
                        row.get("match_change") or
                        row.get("change") or
                        row.get("+/-") or 0
                    )
                    percent = float(
                        row.get("match_percent_price_change") or 
                        row.get("percent_change") or 
                        row.get("match_percent_change") or
                        row.get("percent") or
                        row.get("%") or 0
                    )
                    
                    volume = int(float(row.get("match_accumulated_volume") or row.get("total_volume") or row.get("Tổng KL") or 0))
                    ceiling = float(row.get("listing_ceiling") or row.get("ceiling") or row.get("Trần") or 0)
                    floor = float(row.get("listing_floor") or row.get("floor") or row.get("Sàn") or 0)
                    
                    # Nếu vẫn bằng 0 thì tính tạm từ giá và giá tham chiếu
                    ref_price = float(row.get("listing_ref_price") or row.get("ref_price") or row.get("Giá TC") or 0)
                    if change == 0 and ref_price > 0 and price > 0:
                        change = price - ref_price
                        percent = (change / ref_price) * 100
                    if symbol:
                        result.append({
                            "symbol": symbol,
                            "price": price,
                            "change": change,
                            "percent": percent,
                            "volume": volume,
                            "ceiling": ceiling,
                            "floor": floor
                        })
                except Exception as e:
                    print("Row error:", e)
                    continue
    except Exception as e:
        print("Board error:", e)

    set_cached(cache_key, result)
    return result

@app.get("/api/history/{symbol}")
def get_history(symbol: str, days: int = 60):
    symbol = symbol.upper()
    cache_key = f"history_{symbol}_{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        quote = Quote(symbol=symbol, source="VCI")
        df = quote.history(start="2024-01-01", interval="1D")

        if df is not None and not df.empty:
            df = df.tail(days)
            data = []
            for _, row in df.iterrows():
                t = row.get("time") or row.get("date")
                if hasattr(t, "timestamp"):
                    ts = int(t.timestamp())
                else:
                    ts = int(pd.Timestamp(t).timestamp())
                data.append({
                    "time": ts,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                })
            set_cached(cache_key, data)
            return data
    except Exception as e:
        print("History error:", e)

    return []
