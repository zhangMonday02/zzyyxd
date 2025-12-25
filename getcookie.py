# -*- coding: utf-8 -*-
import json
import time
import uuid
import sys
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# ================= 配置区域 =================
# 全局固定公钥
GLOBAL_PUBLIC_KEY = "043b2759c70dab4718520cad55ac41eea6f8922c1309afb788f7578b3e585b167811023effefc2b9193cd93ae9c9a2a864e5fffbf7517c679f40cbf4c4630aa28c"

# 指定 User-Agent (需与 Headers 中保持一致)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0'

def log(msg):
    """日志输出到 stderr，避免污染 stdout 导致调用方解析失败"""
    sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()

def init_driver():
    """初始化浏览器"""
    log("正在启动 Chrome (无头模式)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 禁用图片加载，加速页面
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    # 设定加载策略为 eager (DOM加载完即算完成，不等资源)
    chrome_options.page_load_strategy = 'eager'
    
    chrome_options.add_argument(f'user-agent={USER_AGENT}')
    
    # 防检测
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

def get_waf_cookies(driver):
    """
    严格按照要求：访问 -> 删除 -> 刷新 -> 提取
    """
    url = "https://www.jlc.com/"
    log(f"1. 访问主页获取环境: {url}")
    driver.get(url)
    
    # 稍微等待一下首次加载
    time.sleep(1)

    log("2. 执行强制清理并刷新流程 (触发 Set-Cookie)")
    # 无论有没有，先执行删除操作，确保环境干净，触发服务器重新下发
    try:
        driver.delete_cookie('HWWAFSESID')
        driver.delete_cookie('HWWAFSESTIME')
    except:
        pass
    
    # 刷新页面
    driver.refresh()
    
    # 等待 WAF 计算和 Cookie 写入 (通常很快，给 1.5秒)
    time.sleep(1.5)
    
    cookies = {c['name']: c['value'] for c in driver.get_cookies()}
    
    waf_sid = cookies.get('HWWAFSESID', '')
    waf_time = cookies.get('HWWAFSESTIME', '')
    
    if waf_sid and waf_time:
        log(f"WAF Cookie 获取成功: {waf_sid}")
    else:
        log("警告: WAF Cookie 获取不完整，尝试继续...")
        
    return waf_sid, waf_time

def get_passport_data(driver):
    """
    跳转 Passport 获取 secretkey 和计算签名
    """
    url = "https://passport.jlc.com/window/login?appId=JLC_PORTAL_PC&redirectUrl=https%3A%2F%2Fwww.jlc.com%2F"
    log(f"3. 跳转登录页握手: {url}")
    driver.get(url)
    
    # 等待握手接口 /api/cas-auth/secret/update 完成
    # 前端代码会把结果写入 localStorage
    log("等待握手及加密库加载 (3秒)...")
    time.sleep(3)
    
    # 1. 获取 SecretKey
    secret_key = ""
    try:
        key_pair_str = driver.execute_script("return localStorage.getItem('keyPair');")
        if key_pair_str:
            key_pair = json.loads(key_pair_str)
            secret_key = key_pair.get('keyId', '')
            log("SecretKey 获取成功")
        else:
            log("错误: localStorage 无 keyPair 数据")
    except Exception as e:
        log(f"提取 SecretKey 出错: {e}")

    # 2. 生成 UUID 和 签名
    timestamp = int(time.time() * 1000)
    client_uuid = f"{uuid.uuid4()}-{timestamp}"
    jsec_val = ""
    
    try:
        # 调用页面内置函数加密
        js = f"return window.SM2Utils.encs('{GLOBAL_PUBLIC_KEY}', '{client_uuid}', 1);"
        jsec_val = driver.execute_script(js)
        if jsec_val:
            log("签名计算成功")
    except Exception as e:
        log(f"签名计算出错: {e}")
        
    return secret_key, client_uuid, jsec_val

def generate_static_cookies():
    """生成其他辅助 Cookie"""
    now = int(time.time())
    return {
        'device_id': uuid.uuid4().hex,
        'Qs_lvt_290854': f"{now-5000}%2C{now}",
        'Qs_pv_290854': '2499244294467079700%2C852781256760664000',
        '__sameSiteCheck__': '1',
        '_c_WBKFRo': '03ctatXDH7wXL16IRpFWI9UfuGhnVMzy0f5q8oX',
        '_nb_ioWEgULi': '',
        'lsId': uuid.uuid4().hex
    }

def print_result(waf_sid, waf_time, secret_key, client_uuid, jsec_val, static_cookies):
    """
    严格按照要求的格式输出 Python 代码
    """
    
    # 构造 Cookies 字典字符串
    cookies_code = f"""cookies = {{
    'JSESSIONID': '',
    'device_id': '{static_cookies['device_id']}',
    'HWWAFSESID': '{waf_sid}',
    'HWWAFSESTIME': '{waf_time}',
    'Qs_lvt_290854': '{static_cookies['Qs_lvt_290854']}',
    'Qs_pv_290854': '{static_cookies['Qs_pv_290854']}',
    '__sameSiteCheck__': '{static_cookies['__sameSiteCheck__']}',
    '_c_WBKFRo': '{static_cookies['_c_WBKFRo']}',
    '_nb_ioWEgULi': '{static_cookies['_nb_ioWEgULi']}',
    'lsId': '{static_cookies['lsId']}'
}}"""

    # 构造 Headers 字典字符串
    # x-jlc-clientinfo 使用固定的 Base64 (PC-WEB)
    client_info = "eyJjbGllbnRUeXBlIjoiUEMtV0VCIiwib3NOYW1lIjoiV2luZG93cyIsIm9zVmVyc2lvbiI6IjEwIiwiYnJvd3Nlck5hbWUiOiJFZGdlIiwiYnJvd3NlclZlcnNpb24iOiIxNDMuMC4wLjAiLCJicm93c2VyRW5naW5lIjoiQmxpbmsiLCJicm93c2VyRW5naW5lVmVyc2lvbiI6IjE0My4wLjAuMCIsInNjcmVlbldpZHRoIjoxNzA3LCJzY3JlZW5IZWlnaHQiOjEwNjcsImRwciI6MS41LCJjb2xvckRlcHRoIjoyNCwicGl4ZWxEZXB0aCI6MjQsImdwdVZlbmRvciI6Ikdvb2dsZSBJbmMuIChOVklESUEpIiwiZ3B1UmVuZGVyZXIiOiJBTkdMRSAoTlZJRElBLCBOVklESUEgR2VGb3JjZSBSVFggNTA2MCBMYXB0b3AgR1BVICgweDAwMDAyRDU5KSBEaXJlY3QzRDExIHZzXzVfMCBwc181XzAsIEQzRDExKSIsImNwdUFyY2hpdGVjdHVyZSI6ImFtZDY0IiwiaGFyZHdhcmVDb25jdXJyZW5jeSI6MjQsImxhbmd1YWdlIjoiemgtQ04iLCJ0aW1lWm9uZSI6IkFzaWEvU2hhbmdoYWkiLCJ0aW1lem9uZU9mZnNldCI6LTQ4MCwibmV0VHlwZSI6IjRnIn0="

    headers_code = f"""headers = {{
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,gb;q=0.7,en-US;q=0.6',
    'cache-control': 'no-cache, no-store, must-revalidate',
    'content-type': 'application/json',
    'expires': '0',
    'jsec-x-df': '{jsec_val}',
    'origin': 'https://passport.jlc.com',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://passport.jlc.com/window/login?appId=JLC_PORTAL_PC&redirectUrl=https%3A%2F%2Fwww.jlc.com%2F',
    'sec-ch-ua': '"Microsoft Edge";v="143", "Chromium";v="143", "Not A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'secretkey': '{secret_key}',
    'support-cookie-samesite': 'true',
    'user-agent': '{USER_AGENT}',
    'x-jlc-clientinfo': '{client_info}',
    'x-jlc-clientuuid': '{client_uuid}'
}}"""

    print(cookies_code)
    print("") # 空行
    print(headers_code)

def main():
    driver = init_driver()
    try:
        # 1. 获取 WAF Cookie
        waf_sid, waf_time = get_waf_cookies(driver)
        
        # 2. 获取加密参数
        secret_key, client_uuid, jsec_val = get_passport_data(driver)
        
        # 3. 生成静态参数
        static_cookies = generate_static_cookies()
        
        # 4. 输出结果
        if secret_key and jsec_val:
            print_result(waf_sid, waf_time, secret_key, client_uuid, jsec_val, static_cookies)
        else:
            log("获取参数失败，不输出结果")
            
    except Exception as e:
        log(f"运行异常: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
