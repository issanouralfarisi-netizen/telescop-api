from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

app = FastAPI()

# السماح للواجهة بالاتصال بالخادم
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
        # جلب بيانات الذهب
        ticker = "GC=F"
        data = yf.download(tickers=ticker, period="1d", interval="15m", progress=False)
        
        if data.empty:
            return {"error": "Could not fetch data"}

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        # حساب RSI
        data['RSI'] = ta.rsi(data['Close'], length=14)
        
        current_price = round(float(data['Close'].iloc[-1]), 2)
        current_rsi = round(float(data['RSI'].iloc[-1]), 2)
        
        # التوصية
        if current_rsi > 55:
            trend, action, grade = "Up", "Buy (Long)", "A"
        elif current_rsi < 45:
            trend, action, grade = "Down", "Sell (Short)", "B"
        else:
            trend, action, grade = "Neutral", "Wait", "C"

        return {
            "asset": "Gold / XAUUSD",
            "price": f"${current_price}",
            "rsi": current_rsi,
            "trend": trend,
            "action": action,
            "grade": grade,
            "time": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        return {"error": str(e)}
