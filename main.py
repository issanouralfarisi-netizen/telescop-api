from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "Telescop API is Live!"}

@app.get("/api/analyze-gold")
def analyze_gold():
    try:
        # جلب شموع الذهب (PAXG) من Binance
        url = "https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval=15m&limit=100"
        response = requests.get(url)
        data = response.json()

        if not isinstance(data, list) or len(data) == 0:
            return {"error": "Could not fetch data from Binance"}

        # تحويل البيانات إلى إطار بيانات (DataFrame)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
        df['close'] = df['close'].astype(float)

        # حساب مؤشر RSI (14 فترة)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        current_price = round(float(df['close'].iloc[-1]), 2)
        current_rsi = round(float(df['rsi'].iloc[-1]), 2)

        if current_rsi > 55:
            trend, action, grade = "Up", "Buy (Long)", "A"
        elif current_rsi < 45:
            trend, action, grade = "Down", "Sell (Short)", "B"
        else:
            trend, action, grade = "Neutral", "Wait", "C"

        return {
            "asset": "Gold / PAXG",
            "price": f"${current_price}",
            "rsi": current_rsi,
            "trend": trend,
            "action": action,
            "grade": grade,
            "time": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        return {"error": str(e)}
