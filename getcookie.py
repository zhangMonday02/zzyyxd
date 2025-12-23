import requests
import execjs
import time
import uuid
import json
import os
import base64
import random
import string

# ================= 配置 =================
# SM2 公钥
GLOBAL_PUBLIC_KEY = "043b2759c70dab4718520cad55ac41eea6f8922c1309afb788f7578b3e585b167811023effefc2b9193cd93ae9c9a2a864e5fffbf7517c679f40cbf4c4630aa28c"

# 你的登录账号密码
USERNAME = "13800138000"
PASSWORD = "YourPassword123"

# 本地文件名
FILE_CRYPTO = 'crypto-js.min.js'
FILE_SM2 = 'sm2(2).js'

def get_js_ctx():
    """加载 JS 环境"""
    
    # 1. 读取文件内容
    if not os.path.exists(FILE_CRYPTO) or not os.path.exists(FILE_SM2):
        print(f"[!] 错误: 找不到 {FILE_CRYPTO} 或 {FILE_SM2}，请确保文件在当前目录下。")
        exit(1)

    with open(FILE_CRYPTO, 'r', encoding='utf-8') as f:
        crypto_js_code = f.read()
    
    with open(FILE_SM2, 'r', encoding='utf-8') as f:
        sm2_code = f.read()

    # 2. 构建浏览器环境 Polyfill
    # 关键点：将 exports/module 设为 undefined，强制 crypto-js 将对象挂载到 this/window 上
    shim = """
        var window = this;
        var navigator = { 
            appName: 'Netscape', 
            appVersion: '5.0', 
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' 
        };
        var document = { createElement: function() { return { getContext: function() {} } } };
        
        // 屏蔽 CommonJS 导出，强制浏览器模式
        var exports = undefined;
        var module = undefined;
        var define = undefined;
    """
    
    # 3. 组合代码
    # shim -> crypto-js -> 补丁(确保window.CryptoJS存在) -> sm2
    full_code = f"""
        {shim}
        {crypto_js_code}
        
        if (!window.CryptoJS && this.CryptoJS) {{
            window.CryptoJS = this.CryptoJS;
        }}
        
        {sm2_code}
    """
    
    return execjs.compile(full_code)

def sm2_encrypt(ctx, data):
    """调用 JS 的 sm2Encrypt 方法"""
    # 对应 JS: sm2Encrypt(data, key, mode=1) -> C1C3C2
    return ctx.call('sm2Encrypt', data, GLOBAL_PUBLIC_KEY, 1)

def generate_client_info():
    """生成 X-JLC-ClientInfo (Base64 JSON)"""
    info = {
        "clientType": "PC-WEB",
        "osName": "Windows",
        "osVersion": "10",
        "browserName": "Chrome",
        "browserVersion": "120.0.0.0",
        "browserEngine": "Blink",
        "screenWidth": 1920,
        "screenHeight": 1080,
        "dpr": 1,
        "deviceType": None,
        "netType": "4g"
    }
    # 使用紧凑格式 dump
    json_str = json.dumps(info, separators=(',', ':'))
    return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

def main():
    print("[-] 初始化 JS 环境...")
    try:
        ctx = get_js_ctx()
    except Exception as e:
        print(f"[!] JS 加载失败: {e}")
        return

    session = requests.Session()
    
    # 1. 准备指纹和 ID
    # X-JLC-ClientUuid: 格式为 UUID-时间戳
    client_uuid = f"{uuid.uuid4()}-{int(time.time() * 1000)}"
    
    # 模拟一个 32 位的 Visitor ID (通常由指纹库生成)
    visitor_id = ''.join(random.choices(string.hexdigits.lower(), k=32))
    
    # 计算 JSec-X-Df (加密的 visitor_id)
    jsec_x_df = sm2_encrypt(ctx, visitor_id)
    
    # Client Info
    client_info = generate_client_info()

    # 2. 基础 Headers
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

    # 3. 握手获取 SecretKey
    print("[-] 正在握手获取 SecretKey...")
    secret_key = ""
    try:
        url = 'https://passport.jlc.com/api/cas-auth/secret/update'
        # 必须带上这些 Header，否则后端会报 500
        resp = session.post(url, headers=base_headers, json={}, timeout=10)
        
        if resp.status_code != 200:
            print(f"[!] 握手失败: {resp.status_code}")
            print(f"响应: {resp.text}")
            return

        data = resp.json()
        if data.get('code') == 200:
            secret_key = data['data']['keyId']
            print(f"[+] 获取成功 SecretKey: {secret_key}")
        else:
            print(f"[!] API 错误: {data.get('message')}")
            return

    except Exception as e:
        print(f"[!] 请求异常: {e}")
        return

    # 4. 加密账号密码
    print("[-] 正在加密账号密码...")
    enc_username = sm2_encrypt(ctx, USERNAME)
    enc_password = sm2_encrypt(ctx, PASSWORD)

    # 5. 组装最终登录请求数据
    login_headers = base_headers.copy()
    login_headers['secretkey'] = secret_key
    
    login_payload = {
        "username": enc_username,
        "password": enc_password,
        "isAutoLogin": False,
        "appId": "JLC_PORTAL_PC"
    }

    # 6. 输出结果
    print("\n" + "="*40)
    print(" >>> 登录请求配置生成完毕 <<< ")
    print("="*40)
    
    print(f"\n请求 URL: https://passport.jlc.com/api/cas/login/with-password")
    
    print("\n[Headers]:")
    print(json.dumps(login_headers, indent=4, ensure_ascii=False))
    
    print("\n[Cookies] (Session由握手接口返回):")
    print(json.dumps(session.cookies.get_dict(), indent=4))
    
    print("\n[Payload (JSON Body)]:")
    print(json.dumps(login_payload, indent=4))

if __name__ == '__main__':
    main()
