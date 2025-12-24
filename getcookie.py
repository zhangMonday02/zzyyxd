import json
import time
import uuid
import sys
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# ================= 配置区域 =================
GLOBAL_PUBLIC_KEY = "043b2759c70dab4718520cad55ac41eea6f8922c1309afb788f7578b3e585b167811023effefc2b9193cd93ae9c9a2a864e5fffbf7517c679f40cbf4c4630aa28c"
MAIN_URL = "https://www.jlc.com"
PASSPORT_URL = "https://passport.jlc.com/window/login?appId=JLC_PORTAL_PC&redirectUrl=https%3A%2F%2Fwww.jlc.com%2F"

# 定义输出顺序 (完全按照你的要求)
COOKIE_ORDER = [
    'device_id', 'HWWAFSESID', 'HWWAFSESTIME', 'Qs_lvt_290854', 'Qs_pv_290854',
    '__sameSiteCheck__', '_c_WBKFRo', '_nb_ioWEgULi', 'JSESSIONID', 'lsId'
]

HEADER_ORDER = [
    'accept', 'accept-language', 'cache-control', 'content-type', 'origin',
    'referer', 'user-agent', 'secretkey', 'x-jlc-clientuuid', 'jsec-x-df',
    'x-jlc-clientinfo', 'expires', 'pragma', 'priority', 'sec-ch-ua',
    'sec-ch-ua-mobile', 'sec-ch-ua-platform', 'sec-fetch-dest', 
    'sec-fetch-mode', 'sec-fetch-site', 'support-cookie-samesite'
]

# 静态补全数据 (防止Selenium未生成某些统计类Cookie导致缺失)
STATIC_COOKIES_FALLBACK = {
    'device_id': uuid.uuid4().hex,
    'Qs_lvt_290854': f'{int(time.time())}',
    'Qs_pv_290854': '2499244294467079700%2C852781256760664000',
    '__sameSiteCheck__': '1',
    '_c_WBKFRo': '03ctatXDH7wXL1GIRpFWI9AUfuGhSVMzyOf5q8oX',
    '_nb_ioWEgULi': '',
}

def log(msg):
    """日志输出到 stderr，以免干扰 AliV3.py 获取 stdout 结果"""
    sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

def init_driver():
    """初始化浏览器"""
    log("正在启动 Chrome 浏览器 (无头模式)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 保持 UA 一致
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0')
    
    # 防检测
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

def get_waf_cookies_logic(driver):
    """
    执行特定的 WAF Cookie 获取流程
    """
    log(f"正在访问主页: {MAIN_URL}")
    driver.get(MAIN_URL)
    time.sleep(2)

    waf_keys = ['HWWAFSESID', 'HWWAFSESTIME']
    
    # 获取当前 Cookies
    def get_current_cookies():
        return {c['name']: c['value'] for c in driver.get_cookies()}

    cookies = get_current_cookies()
    has_waf = all(k in cookies for k in waf_keys)

    if has_waf:
        log(">>> 状态: Cookie 中已存在 WAF 值")
        log(">>> 操作: 手动删除 HWWAFSESID 和 HWWAFSESTIME，然后刷新")
        
        driver.delete_cookie('HWWAFSESID')
        driver.delete_cookie('HWWAFSESTIME')
        time.sleep(0.5)
        
        driver.refresh()
        log(">>> 页面已刷新，等待响应头 Set-Cookie 生效...")
        time.sleep(3) # 等待网络请求完成和Cookie写入
    else:
        log(">>> 状态: Cookie 中不存在 WAF 值")
        log(">>> 操作: 尝试刷新页面 (最多3次)")
        
        for i in range(3):
            log(f"    正在进行第 {i+1} 次刷新...")
            driver.refresh()
            time.sleep(3)
            cookies = get_current_cookies()
            if all(k in cookies for k in waf_keys):
                log("    WAF Cookie 获取成功！")
                break
            else:
                log("    未获取到，继续重试...")

    # 最终检查
    final_cookies = get_current_cookies()
    waf_result = {k: final_cookies.get(k) for k in waf_keys if final_cookies.get(k)}
    
    if len(waf_result) == 2:
        log(f"成功提取 WAF Cookie: {waf_result}")
    else:
        log("警告: 流程结束后仍未完整获取 WAF Cookie")
    
    return waf_result

def get_passport_params(driver):
    """
    跳转到 Passport 获取密钥和加密签名
    """
    log(f"正在跳转至登录页: {PASSPORT_URL}")
    driver.get(PASSPORT_URL)
    
    log("等待握手接口及 JS 资源加载 (5秒)...")
    time.sleep(5)

    # 1. 提取 SecretKey
    secret_key = ""
    try:
        # 嘉立创将密钥存储在 LocalStorage 的 keyPair 字段
        # 格式 {"keyId": "...", "publicHexKey": "...", ...}
        key_pair_str = driver.execute_script("return localStorage.getItem('keyPair');")
        if key_pair_str:
            key_pair = json.loads(key_pair_str)
            secret_key = key_pair.get('keyId', '')
            log(f"成功获取 SecretKey: {secret_key}")
        else:
            log("错误: LocalStorage 中 keyPair 为空，握手可能失败")
    except Exception as e:
        log(f"获取 SecretKey 异常: {e}")

    # 2. 生成 Client UUID
    timestamp = int(time.time() * 1000)
    client_uuid = f"{uuid.uuid4()}-{timestamp}"
    log(f"生成 ClientUUID: {client_uuid}")

    # 3. 调用浏览器 SM2Utils 加密
    jsec_val = ""
    try:
        # 检查函数是否存在
        is_ready = driver.execute_script("return typeof window.SM2Utils !== 'undefined' && typeof window.SM2Utils.encs === 'function';")
        if is_ready:
            # cipherMode = 1 (C1C3C2)
            js_code = f"return window.SM2Utils.encs('{GLOBAL_PUBLIC_KEY}', '{client_uuid}', 1);"
            jsec_val = driver.execute_script(js_code)
            log("成功调用 SM2Utils.encs 生成 jsec-x-df")
        else:
            log("错误: SM2Utils 未加载")
    except Exception as e:
        log(f"JS 加密执行失败: {e}")

    return secret_key, client_uuid, jsec_val

def format_output(final_cookies, final_headers):
    """
    严格按照要求格式化输出
    """
    output = []
    
    # ---------------- 输出 Cookies ----------------
    output.append("        cookies = {")
    
    # 1. 先按指定顺序输出
    for key in COOKIE_ORDER:
        if key in final_cookies:
            output.append(f"            '{key}': '{final_cookies[key]}',")
    
    # 2. 输出剩余未在顺序表中的 Cookie (如果有)
    for key, val in final_cookies.items():
        if key not in COOKIE_ORDER:
            output.append(f"            '{key}': '{val}',")
            
    output.append("        }")
    output.append("") # 空行

    # ---------------- 输出 Headers ----------------
    output.append("        headers = {")
    
    # 1. 先按指定顺序输出
    for key in HEADER_ORDER:
        if key in final_headers:
            output.append(f"            '{key}': '{final_headers[key]}',")
            
    # 2. 输出剩余 Header
    for key, val in final_headers.items():
        if key not in HEADER_ORDER:
            output.append(f"            '{key}': '{val}',")
            
    output.append("        }")
    
    return "\n".join(output)

def main():
    driver = init_driver()
    try:
        # 步骤 1: 获取 WAF Cookie
        get_waf_cookies_logic(driver)
        
        # 步骤 2: 获取登录参数
        secret_key, client_uuid, jsec_val = get_passport_params(driver)

        if not secret_key or not jsec_val:
            log("获取关键参数失败，无法继续")
            return

        # 步骤 3: 整理数据
        
        # 整理 Cookies
        selenium_cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        
        # 合并 Static Fallback (如果在 Selenium 中没获取到，使用静态替补)
        final_cookies = STATIC_COOKIES_FALLBACK.copy()
        final_cookies.update(selenium_cookies)
        
        # 获取 UA
        user_agent = driver.execute_script("return navigator.userAgent;")

        # 整理 Headers
        final_headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache, no-store, must-revalidate',
            'content-type': 'application/json',
            'origin': 'https://passport.jlc.com',
            'referer': PASSPORT_URL,
            'user-agent': user_agent,
            'secretkey': secret_key,
            'x-jlc-clientuuid': client_uuid,
            'jsec-x-df': jsec_val,
            # 固定值 PC-WEB Base64
            'x-jlc-clientinfo': 'eyJjbGllbnRUeXBlIjoiUEMtV0VCIiwib3NOYW1lIjoiV2luZG93cyIsIm9zVmVyc2lvbiI6IjEwIiwiYnJvd3Nlck5hbWUiOiJFZGdlIiwiYnJvd3NlclZlcnNpb24iOiIxNDMuMC4wLjAiLCJicm93c2VyRW5naW5lIjoiQmxpbmsiLCJicm93c2VyRW5naW5lVmVyc2lvbiI6IjE0My4wLjAuMCIsInNjcmVlbldpZHRoIjoxNzA3LCJzY3JlZW5IZWlnaHQiOjEwNjcsImRwciI6MS41LCJjb2xvckRlcHRoIjoyNCwicGl4ZWxEZXB0aCI6MjQsImdwdVZlbmRvciI6Ikdvb2dsZSBJbmMuIChOVklESUEpIiwiZ3B1UmVuZGVyZXIiOiJBTkdMRSAoTlZJRElBLCBOVklESUEgR2VGb3JjZSBSVFggNTA2MCBMYXB0b3AgR1BVICgweDAwMDAyRDU5KSBEaXJlY3QzRDExIHZzXzVfMCBwc181XzAsIEQzRDExKSIsImNwdUFyY2hpdGVjdHVyZSI6ImFtZDY0IiwiaGFyZHdhcmVDb25jdXJyZW5jeSI6MjQsImxhbmd1YWdlIjoiemgtQ04iLCJ0aW1lWm9uZSI6IkFzaWEvU2hhbmdoYWkiLCJ0aW1lem9uZU9mZnNldCI6LTQ4MCwibmV0VHlwZSI6IjRnIn0=',
            'expires': '0',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'support-cookie-samesite': 'true'
        }

        # 步骤 4: 打印结果到 stdout (供 AliV3.py 读取)
        print(format_output(final_cookies, final_headers))
        
        log("数据已输出到 stdout")

    except Exception as e:
        log(f"发生错误: {e}")
    finally:
        driver.quit()
        log("浏览器已关闭")

if __name__ == "__main__":
    main()
