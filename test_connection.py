import os
from dotenv import load_dotenv

load_dotenv(override=True)


def test_anthropic():
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[FAIL] ANTHROPIC_API_KEY が設定されていません")
        return False
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=32,
        messages=[{"role": "user", "content": "Hello"}]
    )
    print(f"[OK] Anthropic 接続成功: {message.content[0].text[:50]}")
    return True


def test_alpaca():
    import requests
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    if not api_key or not secret_key:
        print("[FAIL] ALPACA_API_KEY または ALPACA_SECRET_KEY が設定されていません")
        return False
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }
    resp = requests.get(f"{base_url}/v2/account", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print(f"[OK] Alpaca 接続成功: 口座 {data.get('account_number', 'N/A')}, 残高 ${data.get('portfolio_value', 'N/A')}")
        return True
    else:
        print(f"[FAIL] Alpaca 接続失敗: {resp.status_code} {resp.text[:100]}")
        return False


if __name__ == "__main__":
    print("=== 接続テスト ===")
    anthropic_ok = test_anthropic()
    alpaca_ok = test_alpaca()
    print("\n=== 結果 ===")
    print(f"Anthropic: {'OK' if anthropic_ok else 'FAIL'}")
    print(f"Alpaca:    {'OK' if alpaca_ok else 'FAIL'}")
