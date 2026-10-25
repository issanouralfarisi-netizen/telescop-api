from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
from groq import Groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# قائمة الأصول المدعومة (الفوركس عبر Binance + الذهب + الكريبتو)
SUPPORTED_ASSETS = {
    "XAUUSD": {"binance": "PAXGUSDT", "name": "Gold (XAU/USD)"},
    "EURUSD": {"binance": "EURUSDT", "name": "EUR/USD"},
    "GBPUSD": {"binance": "GBPUSDT", "name": "GBP/USD"},
    "AUDUSD": {"binance": "AUDUSDT", "name": "AUD/USD"},
    "USDCAD": {"binance": "USDCAD", "name": "USD/CAD"}, # قد لا يكون متاحاً دائماً في Binance، سنضع بديلاً
    "BTCUSD": {"binance": "BTCUSDT", "name": "Bitcoin (BTC/USD)"},
    "ETHUSD": {"binance": "ETHUSDT", "name": "Ethereum (ETH/USD)"},
    "SOLUSD": {"binance": "SOLUSDT", "name": "Solana (SOL/USD)"}
}

@app.get("/")
def read_root():
    return {"status": "Telescop Multi-Asset API is Live!"}

@app.get("/api/assets")
def get_assets():
    # إرجاع قائمة الأصول للواجهة لتعرضها في القائمة المنسدلة
    return [{"symbol": k, "name": v["name"]} for k, v in SUPPORTED_ASSETS.items()]

@app.get("/api/analyze/{asset_symbol}")
def analyze_asset(asset_symbol: str):
    try:
        # التحقق من أن الأصل مدعوم، وإلا نستخدم الذهب كافتراضي
        asset_info = SUPPORTED_ASSETS.get(asset_symbol.upper(), SUPPORTED_ASSETS["XAUUSD"])
        binance_symbol = asset_info["binance"]
        asset_name = asset_info["name"]

        # جلب البيانات
        url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval=15m&limit=100"
        response = requests.get(url)
        data = response.json()

        # إذا لم يكن الزوج موجوداً في Binance (مثل USDCAD)، نرجع خطأ
        if isinstance(data, dict) and "code" in data:
            return {"error": f"Asset {asset_name} is not available right now."}

        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'ct', 'qav', 'nt', 'tb', 'tq', 'i'])
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)

        # المؤشرات
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        
        df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())))
        df['atr'] = df['tr'].rolling(window=14).mean()

        current_price = float(df['close'].iloc[-1])
        current_rsi = float(df['rsi'].iloc[-1])
        current_atr = float(df['atr'].iloc[-1])

        # مناطق السيولة
        window = 5
        df['is_high'] = df['high'] == df['high'].rolling(window=window*2+1, center=True).max()
        df['is_low'] = df['low'] == df['low'].rolling(window=window*2+1, center=True).min()
        highs = df[df['is_high']]['high'].tail(3).tolist()
        lows = df[df['is_low']]['low'].tail(3).tolist()
        liquidity_zones = sorted(list(set([round(h, 5 if current_price < 10 else 2) for h in highs] + [round(l, 5 if current_price < 10 else 2) for l in lows])))

        # الذكاء الاصطناعي
        ai_action, ai_grade = "Wait", "C"
        ai_rationale = "AI offline."
        ai_plan = {
            "entry": round(current_price, 5 if current_price < 10 else 2), 
            "stop_loss": round(current_price, 5 if current_price < 10 else 2),
            "tp1": round(current_price, 5 if current_price < 10 else 2), 
            "tp2": round(current_price, 5 if current_price < 10 else 2), 
            "tp3": round(current_price, 5 if current_price < 10 else 2)
        }

        if GROQ_API_KEY:
            try:
                client = Groq(api_key=GROQ_API_KEY)
                prompt = f"""
                You are an expert trader. Analyze the asset: {asset_name}.
                Current Price: {current_price}
                RSI (14): {current_rsi:.2f}
                ATR (Volatility): {current_atr:.5f}
                Key Liquidity Zones: {liquidity_zones}

                Decide whether to go Long (Buy), Short (Sell), or Wait. 
                Calculate exact prices for Entry, Stop Loss, and 3 Take Profit targets based on the volatility.
                
                Respond in STRICT JSON format ONLY:
                {{
                    "action": "Long" or "Short" or "Wait",
                    "grade": "A+", "A", "B", or "C",
                    "rationale": "Brief 1-sentence reason",
                    "plan": {{
                        "entry": float,
                        "stop_loss": float,
                        "tp1": float,
                        "tp2": float,
                        "tp3": float
                    }}
                }}
                """
                
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama3-8b-8192",
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                
                ai_response = json.loads(chat_completion.choices[0].message.content)
                ai_action = ai_response.get("action", "Wait")
                ai_grade = ai_response.get("grade", "B")
                ai_rationale = ai_response.get("rationale", "")
                if "plan" in ai_response and ai_response["plan"]:
                    ai_plan = ai_response["plan"]
                
            except Exception as e:
                print(f"AI Error: {e}")
                ai_rationale = "AI rate limit. Using safe default."

        trend = "Up" if ai_action == "Long" else ("Down" if ai_action == "Short" else "Neutral")
        
        # تحديد عدد الخانات العشرية (للعملات الرقمية 2، للفوركس 4 أو 5)
        decimals = 2 if current_price > 100 else 5

        return {
            "asset": asset_name,
            "price": round(current_price, decimals),
            "rsi": round(current_rsi, 2),
            "action": ai_action,
            "trend": trend,
            "grade": ai_grade,
            "rationale": ai_rationale,
            "liquidity_zones": [round(z, decimals) for z in liquidity_zones],
            "plan": {
                "stop_loss": round(float(ai_plan.get("stop_loss", current_price)), decimals),
                "entry": round(float(ai_plan.get("entry", current_price)), decimals),
                "tp1": round(float(ai_plan.get("tp1", current_price)), decimals),
                "tp2": round(float(ai_plan.get("tp2", current_price)), decimals),
                "tp3": round(float(ai_plan.get("tp3", current_price)), decimals)
            }
        }
    except Exception as e:
        return {"error": str(e)}
