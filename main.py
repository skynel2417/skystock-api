from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from vnstock import Vnstock
import pandas as pd
from typing import List
import time

app = FastAPI(title="SkyStock API")

# Cho phép website của bạn gọi API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache đơn giản để tránh gọi quá nhiều
cache = {}
CACHE_TIME = 20  # giây

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

@app.get("/api/board")
def get_board(symbols: str = Query(..., description="Danh sách mã, cách nhau bởi dấu phẩy")):
    """
    Lấy bảng giá theo danh sách mã
    Ví dụ: /api/board?symbols=VCB,FPT,HPG
    """
    cache_key = f"board_{symbols}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    result = []

    try:
        stock = Vnstock().stock(symbol=symbol_list[0], source="VCI")
        # Lấy bảng giá
        df = stock.trading.price_board(symbol_list)

        if df is not None and not df.empty:
            for _, row in df.iterrows():
                try:
                    item = {
                        "symbol": str(row.get("Mã CP", row.get("symbol", ""))),
                        "price": float(row.get("Giá", row.get("match_price", 0)) or 0),
                        "change": float(row.get("+/-", row.get("price_change", 0)) or 0),
                        "percent": float(row.get("%", row.get("percent_change", 0)) or 0),
                        "volume": int(row.get("Tổng KL", row.get("total_volume", 0)) or 0),
                        "ceiling": float(row.get("Trần", row.get("ceiling", 0)) or 0),
                        "floor": float(row.get("Sàn", row.get("floor", 0)) or 0),
                    }
                    result.append(item)
                except Exception:
                    continue
    except Exception as e:
        # Nếu lỗi, trả về rỗng
        print("Error:", e)

    set_cached(cache_key, result)
    return result

@app.get("/api/history/{symbol}")
def get_history(symbol: str, days: int = 30):
    """
    Lấy dữ liệu nến lịch sử
    """
    symbol = symbol.upper()
    cache_key = f"history_{symbol}_{days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    try:
        stock = Vnstock().stock(symbol=symbol, source="VCI")
        df = stock.quote.history(start="2024-01-01", end=None, interval="1D")

        if df is not None and not df.empty:
            df = df.tail(days)
            data = []
            for _, row in df.iterrows():
                data.append({
                    "time": int(pd.Timestamp(row["time"]).timestamp()),
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

@app.get("/health")
def health():
    return {"status": "healthy"}
