import json
import time
import uuid
import sys
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# ================= 配置区域 =================
# 全局固定公钥
GLOBAL_PUBLIC_KEY = "043b2759c70dab4718520cad55ac41eea6f8922c1309afb788f7578b3e585b167811023effefc2b9193cd93ae9c9a2a864e5fffbf7517c679f40cbf4c4630aa28c"
MAIN_URL = "https://www.jlc.com"
PASSPORT_URL = "https://passport.jlc.com/window/login?appId=JLC_PORTAL_PC&redirectUrl=https%3A%2F%2Fwww.jlc.com%2F"

# 必须与 AliV3.py 保持完全一致的 UA，否则 WAF 会拦截
TARGET_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0'

# 指定输出顺序
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

def log(msg):
    """日志输出到 stderr"""
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
    
    # 关键：设置 UA
    chrome_options.add_argument(f'user-agent={TARGET_USER_AGENT}')
    
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
    """执行特定的 WAF Cookie 获取流程"""
    log(f"正在访问主页: {MAIN_URL}")
    driver.get(MAIN_URL)
    time.sleep(2)

    waf_keys = ['HWWAFSESID', 'HWWAFSESTIME']
    
    def get_current_cookies():
        return {c['name']: c['value'] for c in driver.get_cookies()}

    cookies = get_current_cookies()
    # 检查是否同时存在
    has_waf = all(k in cookies for k in waf_keys)

    if has_waf:
        log(">>> 状态: Cookie 中已存在 WAF 值")
        log(">>> 操作: 手动删除 HWWAFSESID 和 HWWAFSESTIME，然后刷新")
        try:
            driver.delete_cookie('HWWAFSESID')
            driver.delete_cookie('HWWAFSESTIME')
        except:
            pass
        time.sleep(0.5)
        driver.refresh()
        log(">>> 页面已刷新，等待响应头 Set-Cookie 生效...")
        time.sleep(3)
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

    final_cookies = get_current_cookies()
    waf_result = {k: final_cookies.get(k) for k in waf_keys if final_cookies.get(k)}
    
    if len(waf_result) == 2:
        log(f"成功提取 WAF Cookie: {waf_result}")
    else:
        log("警告: 流程结束后仍未完整获取 WAF Cookie")
    
    return waf_result

def get_passport_params(driver):
    """跳转到 Passport 获取密钥和加密签名"""
    log(f"正在跳转至登录页: {PASSPORT_URL}")
    driver.get(PASSPORT_URL)
    
    log("等待握手接口及 JS 资源加载 (5秒)...")
    time.sleep(5)

    # 1. 提取 SecretKey (从 LocalStorage)
    secret_key = ""
    try:
        key_pair_str = driver.execute_script("return localStorage.getItem('keyPair');")
        if key_pair_str:
            key_pair = json.loads(key_pair_str)
            secret_key = key_pair.get('keyId', '')
            log(f"成功获取 SecretKey: {secret_key}")
        else:
            log("错误: LocalStorage 中 keyPair 为空，握手可能失败")
    except Exception as e:
        log(f"获取 SecretKey 异常: {e}")

    # 2. 提取 lsId (非常重要，缺失会导致超时)
    ls_id = ""
    try:
        ls_id = driver.execute_script("return localStorage.getItem('lsId');")
        if ls_id:
            log(f"成功获取 lsId: {ls_id}")
        else:
            # 如果 localStorage 没有，尝试生成一个或从 cookie 找
            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
            ls_id = cookies.get('lsId', uuid.uuid4().hex)
            log(f"LocalStorage 无 lsId，使用备用值: {ls_id}")
    except:
        ls_id = uuid.uuid4().hex

    # 3. 生成 Client UUID
    timestamp = int(time.time() * 1000)
    client_uuid = f"{uuid.uuid4()}-{timestamp}"
    log(f"生成 ClientUUID: {client_uuid}")

    # 4. 调用浏览器 SM2Utils 加密
    jsec_val = ""
    try:
        is_ready = driver.execute_script("return typeof window.SM2Utils !== 'undefined' && typeof window.SM2Utils.encs === 'function';")
        if is_ready:
            js_code = f"return window.SM2Utils.encs('{GLOBAL_PUBLIC_KEY}', '{client_uuid}', 1);"
            jsec_val = driver.execute_script(js_code)
            log("成功调用 SM2Utils.encs 生成 jsec-x-df")
        else:
            log("错误: SM2Utils 未加载")
    except Exception as e:
        log(f"JS 加密执行失败: {e}")

    return secret_key, client_uuid, jsec_val, ls_id

def format_output(final_cookies, final_headers):
    """
    格式化输出：严格按照指定顺序，无缩进
    """
    output = []
    
    # Cookies
    output.append("cookies = {")
    
    # 1. 按照 COOKIE_ORDER 的顺序输出
    for key in COOKIE_ORDER:
        val = final_cookies.get(key, '')
        output.append(f"    '{key}': '{val}',")
    
    # 2. 输出剩余的 (如果有)
    for key, val in final_cookies.items():
        if key not in COOKIE_ORDER:
            output.append(f"    '{key}': '{val}',")
            
    output.append("}")
    output.append("")

    # Headers
    output.append("headers = {")
    
    # 1. 按照 HEADER_ORDER 的顺序输出
    for key in HEADER_ORDER:
        val = final_headers.get(key, '')
        output.append(f"    '{key}': '{val}',")
        
    # 2. 输出剩余的
    for key, val in final_headers.items():
        if key not in HEADER_ORDER:
            output.append(f"    '{key}': '{val}',")
            
    output.append("}")
    
    return "\n".join(output)

def main():
    driver = init_driver()
    try:
        # 1. 获取 WAF Cookie
        get_waf_cookies_logic(driver)
        
        # 2. 获取登录参数
        secret_key, client_uuid, jsec_val, ls_id = get_passport_params(driver)

        if not secret_key or not jsec_val:
            log("获取关键参数失败，无法继续")
            return

        # 3. 整理 Cookies
        selenium_cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        
        # 构造静态/动态混合 Cookie
        # 注意：这里不仅要包含 Selenium 抓到的，还要补全 lsId 和 device_id
        final_cookies = {
            'device_id': selenium_cookies.get('device_id', uuid.uuid4().hex),
            'HWWAFSESID': selenium_cookies.get('HWWAFSESID', ''),
            'HWWAFSESTIME': selenium_cookies.get('HWWAFSESTIME', ''),
            'Qs_lvt_290854': selenium_cookies.get('Qs_lvt_290854', f'{int(time.time())}'),
            'Qs_pv_290854': selenium_cookies.get('Qs_pv_290854', '2499244294467079700%2C852781256760664000'),
            '__sameSiteCheck__': '1',
            '_c_WBKFRo': selenium_cookies.get('_c_WBKFRo', '03ctatXDH7wXL1GIRpFWI9AUfuGhSVMzyOf5q8oX'),
            '_nb_ioWEgULi': '',
            'JSESSIONID': selenium_cookies.get('JSESSIONID', ''),
            'lsId': ls_id # 这是一个非常重要的值，必须和 header 环境匹配
        }

        # 4. 整理 Headers
        # 注意：user-agent 必须和 init_driver 里设置的一模一样
        final_headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache, no-store, must-revalidate',
            'content-type': 'application/json',
            'origin': 'https://passport.jlc.com',
            'referer': PASSPORT_URL,
            'user-agent': TARGET_USER_AGENT, 
            'secretkey': secret_key,
            'x-jlc-clientuuid': client_uuid,
            'jsec-x-df': jsec_val,
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

        # 5. 输出
        print(format_output(final_cookies, final_headers))
        log("数据已输出到 stdout")

    except Exception as e:
        log(f"发生错误: {e}")
    finally:
        driver.quit()
        log("浏览器已关闭")

if __name__ == "__main__":
    main()
