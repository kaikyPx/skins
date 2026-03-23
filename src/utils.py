import requests

def get_cny_to_usd_rate():
    try:
        response = requests.get("https://economia.awesomeapi.com.br/last/CNY-USD", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data["CNYUSD"]["bid"])
    except Exception as e:
        print(f"⚠️ Erro ao obter cotação CNY->USD: {e}")
    return 0.14 # Fallback seguro
