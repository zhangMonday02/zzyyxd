import requests
import execjs
import time
import uuid
import json
import os
import base64
import random
import string

# ================= Configuration =================
# SM2 Public Key (from your request)
GLOBAL_PUBLIC_KEY = "043b2759c70dab4718520cad55ac41eea6f8922c1309afb788f7578b3e585b167811023effefc2b9193cd93ae9c9a2a864e5fffbf7517c679f40cbf4c4630aa28c"

# Target Credentials (REPLACE THESE)
USERNAME = "13800138000" 
PASSWORD = "YourPassword123"

# File paths
JS_SM2_FILE = 'sm2.js'
JS_CRYPTO_FILE = 'crypto-js.min.js'
CRYPTO_JS_URL = "https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"

def download_crypto_js():
    """Downloads crypto-js.min.js if it doesn't exist."""
    if not os.path.exists(JS_CRYPTO_FILE):
        print(f"Downloading {JS_CRYPTO_FILE}...")
        try:
            resp = requests.get(CRYPTO_JS_URL)
            with open(JS_CRYPTO_FILE, 'w', encoding='utf-8') as f:
                f.write(resp.text)
        except Exception as e:
            print(f"Failed to download crypto-js: {e}")
            exit(1)

def get_js_context():
    """Loads JS environment with CryptoJS and SM2."""
    download_crypto_js()
    
    with open(JS_CRYPTO_FILE, 'r', encoding='utf-8') as f:
        crypto_js_code = f.read()
    
    with open(JS_SM2_FILE, 'r', encoding='utf-8') as f:
        sm2_code = f.read()

    # Polyfill for browser environment
    shim = """
        var window = this;
        var navigator = { 
            appName: 'Netscape', 
            appVersion: '5.0', 
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' 
        };
        var document = { createElement: function() { return { getContext: function() {} } } };
    """
    
    full_code = shim + "\n" + crypto_js_code + "\n" + sm2_code
    return execjs.compile(full_code)

def sm2_encrypt(ctx, data):
    """Encrypts data using SM2 (C1C3C2 mode) via JS."""
    # The JS function sm2Encrypt adds '04' prefix and handles Base64 encoding internally
    return ctx.call('sm2Encrypt', data, GLOBAL_PUBLIC_KEY, 1)

def generate_client_uuid():
    """Generates X-JLC-ClientUuid: uuid-timestamp"""
    return f"{uuid.uuid4()}-{int(time.time() * 1000)}"

def generate_visitor_id():
    """Generates a random 32-char hex string to simulate a browser fingerprint."""
    return ''.join(random.choices(string.hexdigits.lower(), k=32))

def generate_client_info():
    """Generates X-JLC-ClientInfo (Base64 encoded JSON)."""
    info = {
        "clientType": "PC-WEB",
        "osName": "Windows",
        "osVersion": "10",
        "browserName": "Chrome",
        "browserVersion": "120.0.0.0",
        "browserEngine": "Blink",
        "screenWidth": 1920,
        "screenHeight": 1080,
        "netType": "4g"
    }
    json_str = json.dumps(info, separators=(',', ':'))
    return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

def main():
    ctx = get_js_context()
    session = requests.Session()
    
    # 1. Prepare Identifiers
    client_uuid = generate_client_uuid()
    visitor_id = generate_visitor_id()
    client_info = generate_client_info()
    
    # 2. Encrypt Visitor ID for JSec-X-Df header
    jsec_x_df = sm2_encrypt(ctx, visitor_id)
    
    # 3. Base Headers
    base_headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Origin': 'https://passport.jlc.com',
        'Referer': 'https://passport.jlc.com/login',
        'X-JLC-ClientUuid': client_uuid,
        'X-JLC-ClientInfo': client_info,
        'JSec-X-Df': jsec_x_df
    }
    
    # 4. Handshake to get secretkey
    print("[-] Performing handshake...")
    try:
        url = 'https://passport.jlc.com/api/cas-auth/secret/update'
        resp = session.post(url, headers=base_headers, json={}, timeout=10)
        
        if resp.status_code != 200:
            print(f"[!] Handshake failed: {resp.status_code} {resp.text}")
            return

        resp_json = resp.json()
        secret_key = resp_json.get('data', {}).get('keyId')
        
        if not secret_key:
            print(f"[!] No secretkey found in response: {resp_json}")
            return
            
        print(f"[+] Secret Key: {secret_key}")

    except Exception as e:
        print(f"[!] Request Error: {e}")
        return

    # 5. Encrypt Credentials
    enc_username = sm2_encrypt(ctx, USERNAME)
    enc_password = sm2_encrypt(ctx, PASSWORD)

    # 6. Prepare Final Headers
    final_headers = base_headers.copy()
    final_headers['secretkey'] = secret_key
    
    # 7. Prepare Request Body
    payload = {
        "username": enc_username,
        "password": enc_password,
        "isAutoLogin": False,
        "appId": "JLC_PORTAL_PC"
    }

    # 8. Output Results
    print("\n" + "="*30 + " LOGIN REQUEST DATA " + "="*30)
    print(f"URL: https://passport.jlc.com/api/cas/login/with-password")
    
    print("\n[Headers]:")
    print(json.dumps(final_headers, indent=4))
    
    print("\n[Cookies]:")
    cookies_dict = session.cookies.get_dict()
    print(json.dumps(cookies_dict, indent=4))
    
    print("\n[Body]:")
    print(json.dumps(payload, indent=4))
    
    # Optional: Actually perform the login request (commented out to just generate data)
    # login_url = 'https://passport.jlc.com/api/cas/login/with-password'
    # login_resp = session.post(login_url, headers=final_headers, json=payload)
    # print("\n[Login Response]:", login_resp.text)

if __name__ == '__main__':
    main()
