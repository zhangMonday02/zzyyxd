import os
import sys
import time
import json
import tempfile
import subprocess
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 导入SM2加密方法
try:
    from Utils import pwdEncrypt
    print("✅ 成功加载 SM2 加密依赖 (Utils.pwdEncrypt)")
except ImportError:
    print("❌ 错误: 未找到 Utils.py 或 pwdEncrypt 函数，请确保同目录下存在该文件")
    sys.exit(1)


def log(msg):
    """带时间戳的日志输出"""
    full_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(full_msg, flush=True)


def call_aliv3min_with_timeout(timeout_seconds=180, max_retries=3):
    """
    调用 AliV3min.py 获取 captchaTicket
    超时3分钟则打印日志并强制结束，最多重试3次
    返回 captchaTicket 或 None
    """
    for attempt in range(max_retries):
        log(f"📞 调用 AliV3min.py 获取 captchaTicket (尝试 {attempt + 1}/{max_retries})...")
        
        try:
            process = subprocess.Popen(
                [sys.executable, 'AliV3min.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            output_lines = []
            start_time = time.time()
            captcha_ticket = None
            
            while True:
                # 检查超时
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    log(f"⏰ AliV3min.py 超过 {timeout_seconds} 秒未完成，强制终止...")
                    process.kill()
                    process.wait()
                    log("--- AliV3min.py 超时前的日志 ---")
                    for line in output_lines:
                        print(line, end='')
                    log("--- 日志结束 ---")
                    break
                
                # 非阻塞读取输出
                try:
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line)
                        # 实时打印，但过滤掉太长的无用信息
                        clean_line = line.rstrip()
                        if len(clean_line) < 200: 
                             print(f"  [AliV3min] {clean_line}")
                        
                        # 检查是否包含 captchaTicket
                        if "SUCCESS: Obtained CaptchaTicket:" in line:
                            next_line = process.stdout.readline()
                            if next_line:
                                output_lines.append(next_line)
                                captcha_ticket = next_line.strip()
                                log(f"✅ 成功获取 captchaTicket: {captcha_ticket[:20]}...")
                        
                        # 也尝试从JSON响应中提取
                        if '"captchaTicket"' in line:
                            try:
                                json_match = re.search(r'"captchaTicket"\s*:\s*"([^"]+)"', line)
                                if json_match:
                                    captcha_ticket = json_match.group(1)
                                    log(f"✅ 从JSON响应中提取到 captchaTicket: {captcha_ticket[:20]}...")
                            except:
                                pass
                    
                    # 检查进程是否结束
                    if process.poll() is not None:
                        remaining = process.stdout.read()
                        if remaining:
                            output_lines.append(remaining)
                        break
                        
                except Exception as e:
                    time.sleep(0.1)
                    continue
            
            if captcha_ticket:
                return captcha_ticket
            else:
                log(f"❌ 未能从 AliV3min.py 输出中提取到 captchaTicket")
                if attempt < max_retries - 1:
                    log(f"⏳ 等待 3 秒后重试...")
                    time.sleep(3)
                    
        except Exception as e:
            log(f"❌ 调用 AliV3min.py 异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
    
    return None


def send_request_via_browser(driver, url, method='POST', body=None):
    """
    通过浏览器控制台发送请求
    修复了 Unexpected token '.' 的问题，使用纯 ES5 语法
    """
    try:
        # 构建 JS 代码，显式传入参数，不使用 ... 扩展运算符
        if body:
            body_str = json.dumps(body, ensure_ascii=False)
            js_code = """
            var url = arguments[0];
            var bodyData = arguments[1];
            var callback = arguments[2];
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json, text/plain, */*'
                },
                body: bodyData,
                credentials: 'include' 
            })
            .then(function(response) { return response.json(); })
            .then(function(data) { callback(JSON.stringify(data)); })
            .catch(function(error) { callback(JSON.stringify({error: error.toString()})); });
            """
            # 执行异步脚本
            result = driver.execute_async_script(js_code, url, body_str)
        else:
            js_code = """
            var url = arguments[0];
            var callback = arguments[1];
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json, text/plain, */*'
                },
                credentials: 'include'
            })
            .then(function(response) { return response.json(); })
            .then(function(data) { callback(JSON.stringify(data)); })
            .catch(function(error) { callback(JSON.stringify({error: error.toString()})); });
            """
            result = driver.execute_async_script(js_code, url)
        
        if result:
            return json.loads(result)
        return None
    except Exception as e:
        log(f"❌ 浏览器请求失败: {e}")
        return None


def init_session(driver):
    """发送初始化会话请求"""
    log("📡 发送初始化会话请求 (get-init-session)...")
    response = send_request_via_browser(
        driver, 
        "https://passport.jlc.com/api/cas/login/get-init-session",
        'POST',
        {"appId": "JLC_PORTAL_PC", "clientType": "PC-WEB"}
    )
    
    if response:
        # log(f"📨 初始化响应: {json.dumps(response, ensure_ascii=False)}")
        if response.get('success') == True and response.get('code') == 200:
            log("✅ 初始化会话成功 (Cookie已写入)")
            return True
        else:
            log(f"⚠ 初始化会话响应异常: {response}")
    else:
        log("❌ 初始化会话请求无响应")
    return False


def login_with_password(driver, username, password, captcha_ticket):
    """使用账号密码登录"""
    url = "https://passport.jlc.com/api/cas/login/with-password"
    
    try:
        encrypted_username = pwdEncrypt(username)
        encrypted_password = pwdEncrypt(password)
        log(f"🔐 账号密码已加密")
    except Exception as e:
        log(f"❌ SM2加密失败: {e}")
        return 'other_error', None
    
    body = {
        'username': encrypted_username,
        'password': encrypted_password,
        'isAutoLogin': False,
        'captchaTicket': captcha_ticket
    }
    
    log(f"📡 发送登录请求 (with-password)...")
    response = send_request_via_browser(driver, url, 'POST', body)
    
    if response:
        log(f"📨 登录响应: {json.dumps(response, ensure_ascii=False)[:200]}...")
        
        if response.get('success') == True and (response.get('code') == 2017 or response.get('data', {}).get('authCode')):
            log(f"✅ 登录接口返回成功")
            return 'success', response
        
        if response.get('code') == 10208:
            log(f"❌ 账号或密码不正确: {response.get('message', '')}")
            return 'password_error', response
        
        log(f"⚠ 登录返回异常: code={response.get('code')}, message={response.get('message', '')}")
        return 'other_error', response
    
    return 'other_error', None


def verify_login_on_member_page(driver, max_retries=3):
    """验证登录成功"""
    for attempt in range(max_retries):
        log(f"🔍 验证登录状态 (尝试 {attempt + 1}/{max_retries})...")
        
        try:
            driver.get("https://member.jlc.com/")
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            log("⏳ 页面加载完成，额外等待5秒...")
            time.sleep(5)
            
            page_source = driver.page_source
            patterns = [r'客编\s*[A-Z0-9]+', r'customerCode.*?[A-Z0-9]{8}']
            
            for pattern in patterns:
                match = re.search(pattern, page_source)
                if match:
                    log(f"✅ 验证登录成功! 找到: {match.group()}")
                    return True
            
            # 尝试通过 DOM 查找
            try:
                # 查找包含“客编”的元素
                driver.find_element(By.XPATH, "//*[contains(text(),'客编')]")
                log(f"✅ 验证登录成功! 找到客编元素")
                return True
            except:
                pass

            log(f"⚠ 未找到客编信息")
            
        except Exception as e:
            log(f"❌ 验证登录异常: {e}")
        
        if attempt < max_retries - 1:
            log("🔄 刷新页面重试...")
            time.sleep(2)
    
    return False


def click_start_exam_button(driver, max_retries=3):
    """点击开始答题"""
    for attempt in range(max_retries):
        log(f"🔍 查找开始答题按钮 (尝试 {attempt + 1}/{max_retries})...")
        try:
            time.sleep(3)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 策略1：ID
            try:
                btn = driver.find_element(By.ID, "startExamBtn")
                driver.execute_script("arguments[0].click();", btn)
                log("✅ 找到并点击开始答题按钮(ID)")
                return True
            except:
                pass
            
            # 策略2：文字
            try:
                btn = driver.find_element(By.XPATH, "//span[contains(text(),'开始答题')]")
                driver.execute_script("arguments[0].click();", btn)
                log("✅ 找到并点击开始答题(Text)")
                return True
            except:
                pass

            log(f"⚠ 未找到按钮")
        except Exception as e:
            log(f"❌ 查找按钮异常: {e}")
        
        if attempt < max_retries - 1:
            driver.refresh()
            time.sleep(3)
    return False


def wait_for_exam_completion(driver, timeout_seconds=180):
    """等待答题完成"""
    log(f"⏳ 等待答题脚本执行 (限时 {timeout_seconds}s)...")
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        try:
            current_url = driver.current_url
            if 'result' in current_url or 'score' in current_url or 'finish' in current_url:
                log(f"✅ 检测到跳转至分数页面: {current_url}")
                return True
        except:
            pass
        time.sleep(2)
    
    log(f"⏰ 等待超时")
    return False


def get_exam_score(driver):
    """获取分数"""
    log("🔍 获取分数...")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)
        
        page_source = driver.page_source
        match = re.search(r'class="score"[^>]*>(\d+)', page_source)
        if match:
            score = int(match.group(1))
            log(f"📊 获取到分数: {score}")
            return score
        
        # 备选方案
        try:
            score_elem = driver.find_element(By.CSS_SELECTOR, ".score")
            score = int(re.search(r'\d+', score_elem.text).group())
            log(f"📊 获取到分数(DOM): {score}")
            return score
        except:
            pass

        log("⚠ 未能找到分数")
        return None
    except Exception as e:
        log(f"❌ 获取分数异常: {e}")
        return None


def create_chrome_driver():
    """创建浏览器，自动加载插件"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 自动加载同目录下的 JLCTK.crx
    extension_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'JLCTK.crx')
    if os.path.exists(extension_path):
        chrome_options.add_extension(extension_path)
        log(f"📦 已加载插件: {extension_path}")
    else:
        log(f"⚠ 未找到插件文件: {extension_path}，将不加载插件运行")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def process_single_account(username, password, account_index, total_accounts):
    """处理单个账号"""
    result = {
        'account_index': account_index,
        'username': username,
        'status': '未知',
        'success': False,
        'score': None,
        'highest_score': 0,
        'failure_reason': None
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        if attempt > 0:
            log(f"🔄 账号 {account_index} 流程重试 ({attempt+1}/{max_retries})...")
        
        driver = None
        try:
            # 1. 启动浏览器（带插件）
            log("🌐 步骤1: 启动浏览器并加载插件...")
            driver = create_chrome_driver()
            
            # 2. 打开passport并初始化Session
            log("🌐 步骤2: 打开护照页并初始化会话...")
            driver.get("https://passport.jlc.com")
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 尝试初始化Session，如果不成功则重试当前大循环
            if not init_session(driver):
                log("❌ 初始化会话失败，重试流程")
                driver.quit()
                continue
            
            # 3. 获取验证码 (此时保持浏览器打开，不关闭！)
            log("🌐 步骤3: 调用外部脚本获取验证码...")
            captcha_ticket = call_aliv3min_with_timeout()
            if not captcha_ticket:
                log("❌ 获取验证码失败，重试流程")
                driver.quit()
                continue
            
            # 4. 登录 (Cookie还在，可以正常登录)
            log("🌐 步骤4: 登录...")
            status, resp = login_with_password(driver, username, password, captcha_ticket)
            
            if status == 'password_error':
                log("❌ 密码错误，跳过此账号")
                result['status'] = '密码错误'
                result['failure_reason'] = '账号或密码不正确'
                driver.quit()
                return result # 密码错误不重试
            
            if status != 'success':
                log("❌ 登录失败，重试流程")
                driver.quit()
                continue
            
            # 5. 验证登录
            log("🌐 步骤5: 验证登录...")
            if not verify_login_on_member_page(driver):
                log("❌ 验证登录失败，重试流程")
                driver.quit()
                continue
            
            # 6. 答题流程
            log("🌐 步骤6: 开始答题流程...")
            exam_url = "https://member.jlc.com/integrated/exam-center/intermediary?examinationRelationUrl=https%3A%2F%2Fexam.kaoshixing.com%2Fexam%2Fbefore_answer_notice%2F1647581&examinationRelationId=1647581"
            
            # 答题子循环
            exam_success = False
            for exam_try in range(3):
                log(f"📝 答题轮次 {exam_try+1}/3...")
                driver.get(exam_url)
                
                # 点击开始
                if not click_start_exam_button(driver):
                    if exam_try < 2: continue
                    else: break
                
                # 等待完成
                log("⏳ 等待插件答题...")
                if not wait_for_exam_completion(driver):
                    result['failure_reason'] = '脚本3分钟未完成'
                    if exam_try < 2: continue
                    else: break
                
                # 获取分数
                score = get_exam_score(driver)
                if score is not None:
                    result['score'] = score
                    result['highest_score'] = max(result['highest_score'], score)
                    
                    if score >= 60:
                        log(f"🎉 答题通过! 分数: {score}")
                        result['success'] = True
                        result['status'] = '答题成功'
                        exam_success = True
                        break
                    else:
                        log(f"😢 分数未过: {score}")
                        result['failure_reason'] = f'最高分{result["highest_score"]}'
                else:
                    result['failure_reason'] = '无法获取分数'
            
            driver.quit()
            
            if exam_success:
                return result
            
            # 如果答题失败了，外层循环继续重试（除非是密码错误上面已经return了）
            
        except Exception as e:
            log(f"❌ 流程异常: {e}")
            if driver:
                try: driver.quit()
                except: pass
            result['failure_reason'] = str(e)
            
    return result


def main():
    if len(sys.argv) < 3:
        print("用法: python jlc.py 账号1,账号2... 密码1,密码2... [失败退出标志]")
        sys.exit(1)
    
    usernames = [u.strip() for u in sys.argv[1].split(',') if u.strip()]
    passwords = [p.strip() for p in sys.argv[2].split(',') if p.strip()]
    enable_exit_code = len(sys.argv) >= 4 and sys.argv[3].lower() == 'true'
    
    if len(usernames) != len(passwords):
        log("❌ 账号密码数量不匹配")
        sys.exit(1)
    
    log(f"🚀 启动任务，共 {len(usernames)} 个账号")
    
    success_count = 0
    failures = []
    
    for i, (user, pwd) in enumerate(zip(usernames, passwords), 1):
        log(f"\n{'='*40}\n正在处理账号 {i}/{len(usernames)}: {user[:3]}***\n{'='*40}")
        res = process_single_account(user, pwd, i, len(usernames))
        
        if res['success']:
            success_count += 1
            log(f"✅ 账号 {i} 完成")
        else:
            failures.append(f"账号{i}({res.get('failure_reason', '未知')})")
            log(f"❌ 账号 {i} 失败: {res.get('failure_reason')}")
    
    log("\n" + "="*40)
    log(f"📊 结果汇总: 成功 {success_count}/{len(usernames)}")
    if failures:
        log(f"❌ 失败列表: {', '.join(failures)}")
    
    if enable_exit_code and len(failures) > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
