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
from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException, TimeoutException

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


def create_chrome_driver(with_extension=True):
    """
    创建Chrome浏览器实例 - 包含防检测配置和插件加载
    """
    chrome_options = Options()
    
    # --- 防检测核心配置 ---
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 禁用自动化控制特征
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 常规配置
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
    
    # --- 插件加载 ---
    if with_extension:
        extension_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'JLCTK.crx')
        if os.path.exists(extension_path):
            chrome_options.add_extension(extension_path)
            log(f"📦 已配置加载插件: {extension_path}")
        else:
            log(f"⚠ 警告: 未找到插件文件 {extension_path}，将不加载插件")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # --- CDP 命令防检测 ---
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
    })
    
    return driver


def call_aliv3min_with_timeout(timeout_seconds=180, max_retries=3):
    """调用 AliV3min.py 获取 captchaTicket"""
    for attempt in range(max_retries):
        log(f"📞 调用 AliV3min.py 获取 captchaTicket (尝试 {attempt + 1}/{max_retries})...")
        try:
            if not os.path.exists('AliV3min.py'):
                log("❌ 错误: 找不到 AliV3min.py")
                return None
            process = subprocess.Popen([sys.executable, 'AliV3min.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore')
            start_time = time.time()
            captcha_ticket = None
            while True:
                if time.time() - start_time > timeout_seconds:
                    log(f"⏰ AliV3min.py 超时，强制终止...")
                    process.kill()
                    break
                try:
                    line = process.stdout.readline()
                    if line:
                        if "SUCCESS: Obtained CaptchaTicket:" in line:
                            next_line = process.stdout.readline()
                            if next_line:
                                captcha_ticket = next_line.strip()
                                log(f"✅ 成功获取 captchaTicket: {captcha_ticket[:20]}...")
                                process.terminate()
                                return captcha_ticket
                        if "captchaTicket" in line:
                            match = re.search(r'"captchaTicket"\s*:\s*"([^"]+)"', line)
                            if match:
                                captcha_ticket = match.group(1)
                                log(f"✅ 从JSON提取到 captchaTicket: {captcha_ticket[:20]}...")
                                process.terminate()
                                return captcha_ticket
                    if process.poll() is not None:
                        break
                except Exception:
                    time.sleep(0.1)
            if captcha_ticket: return captcha_ticket
            else: log(f"❌ 本次尝试未获取到 Ticket")
        except Exception as e:
            log(f"❌ 调用 AliV3min.py 异常: {e}")
    return None


def send_request_via_browser(driver, url, method='POST', body=None):
    """通过浏览器控制台发送请求"""
    try:
        js_body = json.dumps(body, ensure_ascii=False) if body else "null"
        js_method = method
        js_code = f"""
        var done = arguments[arguments.length - 1];
        fetch('{url}', {{
            method: '{js_method}',
            headers: {{'Content-Type': 'application/json', 'Accept': 'application/json', 'AppId': 'JLC_PORTAL_PC', 'ClientType': 'PC-WEB'}},
            body: {js_body},
            credentials: 'include'
        }}).then(r => r.json().then(d => done(JSON.stringify(d))))
          .catch(e => done(JSON.stringify({{error: e.toString()}})));
        """
        result = driver.execute_async_script(js_code)
        return json.loads(result)
    except Exception as e:
        log(f"❌ 浏览器请求失败: {e}")
        return None


def perform_init_session(driver):
    log(f"📡 初始化会话...")
    response = send_request_via_browser(driver, "https://passport.jlc.com/api/cas/login/get-init-session", 'POST', {"appId": "JLC_PORTAL_PC", "clientType": "PC-WEB"})
    if response and response.get('success') == True:
        log("✅ 初始化会话成功")
        return True
    return False


def login_with_password(driver, username, password, captcha_ticket):
    try:
        enc_user = pwdEncrypt(username)
        enc_pwd = pwdEncrypt(password)
    except:
        return 'other_error', None
    
    body = {'username': enc_user, 'password': enc_pwd, 'isAutoLogin': False, 'captchaTicket': captcha_ticket}
    log(f"📡 发送登录请求...")
    res = send_request_via_browser(driver, "https://passport.jlc.com/api/cas/login/with-password", 'POST', body)
    if not res: return 'other_error', None
    log(f"📨 登录响应: {json.dumps(res, ensure_ascii=False)[:100]}...")
    if res.get('success'): return 'success', res
    if res.get('code') == 10208: return 'password_error', res
    return 'other_error', res


def verify_login_on_member_page(driver):
    log(f"🔍 验证登录状态...")
    try:
        driver.get("https://member.jlc.com/")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        if "客编" in driver.page_source or "customerCode" in driver.page_source:
            log(f"✅ 验证登录成功")
            return True
    except: pass
    return False


def switch_to_exam_iframe(driver):
    """切换到答题iframe"""
    try:
        driver.switch_to.default_content()
        iframe = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "client_context_frame")))
        driver.switch_to.frame(iframe)
        return True
    except:
        try:
            iframe = driver.find_element(By.NAME, "context_iframe")
            driver.switch_to.frame(iframe)
            return True
        except: return False


def click_start_exam_button(driver):
    """点击开始答题"""
    log(f"🔍 检查开始答题按钮...")
    switch_to_exam_iframe(driver)
    try:
        btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "startExamBtn")))
        driver.execute_script("arguments[0].click();", btn)
        log("✅ 点击开始答题按钮")
        return True
    except:
        log("❌ 未找到开始答题按钮")
        return False


def force_submit_exam(driver):
    """主动提交试卷"""
    log("⚡ Python 介入，执行主动交卷...")
    try:
        # 此时应该已经在主窗口了，不需要切 iframe
        end_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "endExamBtn")))
        if end_btn.get_attribute("disabled"):
            driver.execute_script("arguments[0].removeAttribute('disabled');", end_btn)
        end_btn.click()
        log("✅ 点击[提交试卷]")
        
        confirm_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "confirmEndExamBtn")))
        confirm_btn.click()
        log("✅ 点击[确认交卷]")
        return True
    except Exception as e:
        log(f"⚠ 主动交卷失败: {e}")
        return False


def wait_for_exam_logic(driver):
    """
    处理答题全流程：
    1. 监控 Iframe 直到进入 exam_start
    2. 提取 URL 并跳出 Iframe (Driver.get) -> 确保插件运行
    3. 等待插件答题
    4. 强制交卷
    5. 等待结果
    """
    log("⏳ 正在监控进入答题页面...")
    
    exam_url = None
    
    # 步骤 1: 等待进入答题页并获取 URL
    for _ in range(20): # 最多等20次检查
        try:
            switch_to_exam_iframe(driver)
            current_url = driver.execute_script("return window.location.href;")
            if "exam_start" in current_url:
                exam_url = current_url
                log(f"✅ 检测到答题页面: {exam_url}")
                break
        except: pass
        time.sleep(1)
        
    if not exam_url:
        log("❌ 超时：未检测到进入答题页面")
        return False

    # 步骤 2: 跳出 Iframe，在主窗口打开答题页
    log("🚀 跳出 Iframe，在主窗口打开答题页以激活插件...")
    driver.switch_to.default_content()
    driver.get(exam_url)
    
    # 步骤 3: 等待插件答题 (25秒)
    log("⏳ 页面已加载，等待 25 秒让插件自动答题...")
    # 可以在这里检测页面元素确保加载
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "question-content")))
    time.sleep(25) 
    
    # 步骤 4: 强制交卷
    force_submit_exam(driver)
    
    # 步骤 5: 等待跳转到结果页
    log("⏳ 等待跳转至分数页面...")
    for _ in range(10):
        if "result" in driver.current_url or "score" in driver.current_url:
            log(f"✅ 已跳转结果页: {driver.current_url}")
            return True
        time.sleep(1)
        
    return False


def get_exam_score(driver):
    """获取分数 (在主窗口)"""
    log("🔍 获取分数...")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "score")))
        score_text = driver.find_element(By.CLASS_NAME, "score").text
        score = int(re.search(r'\d+', score_text).group())
        log(f"📊 分数: {score}")
        return score
    except:
        log("❌ 未获取到分数元素")
        return None


def process_single_account(username, password, account_index, total_accounts):
    result = {'account_index': account_index, 'username': username, 'status': '未知', 'success': False, 'score': 0, 'highest_score': 0, 'failure_reason': None}
    
    for process_attempt in range(3):
        if process_attempt > 0: log(f"\n🔄 账号 {account_index} 重试 ({process_attempt+1}/3)...")
        driver = None
        try:
            log("🌐 启动浏览器...")
            driver = create_chrome_driver(with_extension=True)
            driver.get("https://passport.jlc.com")
            
            if not perform_init_session(driver): raise Exception("Session初始化失败")
            ticket = call_aliv3min_with_timeout()
            if not ticket: raise Exception("Ticket获取失败")
            
            status, res = login_with_password(driver, username, password, ticket)
            if status == 'password_error':
                result['status'] = '密码错误'; return result
            if status != 'success': raise Exception("登录失败")
            
            if not verify_login_on_member_page(driver): raise Exception("验证登录失败")
            
            # 答题循环
            exam_entry = "https://member.jlc.com/integrated/exam-center/intermediary?examinationRelationUrl=https%3A%2F%2Fexam.kaoshixing.com%2Fexam%2Fbefore_answer_notice%2F1647581&examinationRelationId=1647581"
            
            for exam_retry in range(3):
                log(f"📝 答题尝试 {exam_retry+1}/3...")
                driver.get(exam_entry)
                log("⏳ 等待页面加载 (20s)...")
                time.sleep(20)
                
                if not click_start_exam_button(driver):
                    log("❌ 未能点击开始按钮")
                    continue
                
                # 执行跳出+答题+交卷逻辑
                if not wait_for_exam_logic(driver):
                    log("❌ 答题流程未完成")
                    result['failure_reason'] = '流程异常'
                    continue
                
                score = get_exam_score(driver)
                if score is not None:
                    result['score'] = score
                    result['highest_score'] = max(result['highest_score'], score)
                    if score >= 60:
                        log(f"🎉 通过! 分数: {score}")
                        result['success'] = True
                        result['status'] = '答题成功'
                        driver.quit()
                        return result
                    else:
                        log(f"😢 分数未达标: {score}")
                        result['failure_reason'] = f"最高分{result['highest_score']}"
            
            raise Exception("多次答题未通过")

        except Exception as e:
            log(f"❌ 异常: {e}")
            result['failure_reason'] = str(e)
        finally:
            if driver: driver.quit()
            
    result['status'] = '失败'
    return result

def main():
    if len(sys.argv) < 3:
        print("Usage: python jlc.py user1,user2 pwd1,pwd2 [true]")
        sys.exit(1)
    
    users = sys.argv[1].split(',')
    pwds = sys.argv[2].split(',')
    fail_exit = len(sys.argv) >= 4 and sys.argv[3].lower() == 'true'
    
    all_res = []
    for i, (u, p) in enumerate(zip(users, pwds), 1):
        log(f"\n{'='*40}\n账号 {i}/{len(users)}: {u}\n{'='*40}")
        all_res.append(process_single_account(u, p, i, len(users)))
        if i < len(users): time.sleep(5)
        
    log("\n" + "="*40 + "\n📊 结果总结\n" + "="*40)
    has_fail = False
    for r in all_res:
        u_mask = r['username'][:3] + "***"
        if r['success']: log(f"账号{r['account_index']} ({u_mask}): 成功✅ 分数:{r['score']}")
        else: has_fail = True; log(f"账号{r['account_index']} ({u_mask}): 失败❌ 原因:{r['failure_reason']}")
    
    sys.exit(1 if fail_exit and has_fail else 0)

if __name__ == "__main__":
    main()
