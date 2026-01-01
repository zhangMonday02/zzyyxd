# -*- coding: utf-8 -*-
import sys
import time
import json
import subprocess
import traceback
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# 尝试导入加密函数，假设 Utils.py 在同级目录
try:
    from Utils import pwdEncrypt
except ImportError:
    print("错误: 找不到 Utils.py 或 pwdEncrypt 方法。请确保 Utils.py 在同级目录下。")
    sys.exit(1)

# 全局配置
MEMBER_URL = "https://member.jlc.com/"
EXAM_PRE_URL = "https://member.jlc.com/integrated/exam-center/intermediary?examinationRelationUrl=https%3A%2F%2Fexam.kaoshixing.com%2Fexam%2Fbefore_answer_notice%2F1647581&examinationRelationId=1647581"

class JLCBot:
    def __init__(self):
        self.results = []
        self.driver = None

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def init_browser(self):
        """初始化 Selenium 浏览器 (无头模式 + 插件)"""
        if self.driver:
            return

        co = Options()
        co.add_argument("--headless=new") # 新版无头模式支持插件
        co.add_argument("--disable-gpu")
        co.add_argument("--no-sandbox")
        co.add_argument("--window-size=1920,1080")
        # 加载插件
        co.add_extension('JLCTK.crx')
        
        # 防止检测
        co.add_argument("--disable-blink-features=AutomationControlled")
        co.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.driver = webdriver.Chrome(options=co)
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(30) # 设置JS执行超时时间

    def close_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def step_1_check_init_session(self):
        """在浏览器控制台检查初始化会话"""
        for _ in range(3):
            try:
                self.init_browser()
                # 必须先打开网页，才能在控制台发送同域请求
                self.driver.get("https://passport.jlc.com/")
                
                # 使用 JS fetch 发送请求
                # 使用 execute_async_script 以便获取异步 fetch 的结果
                js_script = """
                var callback = arguments[arguments.length - 1];
                var url = "https://passport.jlc.com/api/cas/login/get-init-session";
                var data = {"appId":"JLC_PORTAL_PC","clientType":"PC-WEB"};
                
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                })
                .then(response => response.json())
                .then(data => callback(data))
                .catch(error => callback({"error": error.toString()}));
                """
                
                res = self.driver.execute_async_script(js_script)
                
                if res.get("success") is True and res.get("code") == 200:
                    self.log("Step 1: 初始化会话检查成功 (Browser Fetch)。")
                    return True
                else:
                    self.log(f"Step 1: 初始化响应异常: {res}")
            except Exception as e:
                self.log(f"Step 1: 请求失败: {e}")
            
            # 失败重试前关闭浏览器
            self.close_browser()
            time.sleep(2)
            
        self.log("Step 1: 超过3次初始化失败，退出程序。")
        sys.exit(1)

    def step_2_get_captcha(self):
        """调用 AliV3min.py 获取 captchaTicket"""
        for i in range(3):
            self.log(f"Step 2: 正在获取验证码 (第 {i+1} 次尝试)...")
            try:
                process = subprocess.Popen(
                    [sys.executable, 'AliV3min.py'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                
                try:
                    stdout, stderr = process.communicate(timeout=180) # 3分钟超时
                except subprocess.TimeoutExpired:
                    process.kill()
                    self.log("Step 2: AliV3min.py 运行超时 (3分钟)。")
                    if process.stdout: print(process.stdout.read())
                    continue

                output_lines = stdout.strip().split('\n')
                ticket = None
                
                # 从后往前找 ticket
                if len(output_lines) >= 1:
                    last_line = output_lines[-1].strip()
                    if len(last_line) > 20 and " " not in last_line:
                        ticket = last_line
                
                if ticket:
                    self.log(f"Step 2: 获取到 CaptchaTicket: {ticket}")
                    return ticket
                else:
                    self.log("Step 2: 未能从输出中解析出 Ticket。")
            
            except Exception as e:
                self.log(f"Step 2: 调用脚本异常: {e}")
        
        self.log("Step 2: 3次尝试获取验证码均失败，退出程序。")
        sys.exit(1)

    def step_3_login_browser_console(self, username, password, ticket):
        """通过浏览器控制台发送登录请求"""
        try:
            # Python端加密，因为JS端加密太复杂且 Utils.py 已经有了
            enc_user = pwdEncrypt(username)
            enc_pwd = pwdEncrypt(password)
        except Exception as e:
            self.log(f"加密失败: {e}")
            return "RETRY"

        # 确保浏览器是打开的并且在 passport 域名下
        if not self.driver:
            self.init_browser()
        
        # 检查当前 URL，如果不是 passport.jlc.com，则跳转
        # 这是为了解决跨域问题 (CORS)，必须在同源页面发送请求
        if "passport.jlc.com" not in self.driver.current_url:
            self.driver.get("https://passport.jlc.com/login")

        try:
            # 构造 JS 代码
            # 注意：这里直接将加密后的字符串和 ticket 拼接到 JS 中
            js_script = """
            var callback = arguments[arguments.length - 1];
            var url = "https://passport.jlc.com/api/cas/login/with-password";
            var payload = {
                'username': '%s',
                'password': '%s',
                'isAutoLogin': false,
                'captchaTicket': '%s'
            };
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => callback(data))
            .catch(error => callback({'error': error.toString()}));
            """ % (enc_user, enc_pwd, ticket)

            self.log("Step 3: 正在通过浏览器控制台发送登录请求...")
            res_json = self.driver.execute_async_script(js_script)
            
            # 处理返回结果
            if res_json.get("success") is True and res_json.get("code") == 2017:
                self.log("Step 3: 浏览器内登录成功 (Cookies已自动写入)。")
                return "SUCCESS"
            
            if res_json.get("code") == 10208:
                self.log(f"Step 3: 账号或密码错误: {res_json.get('message')}")
                return "SKIP"
            
            self.log(f"Step 3: 登录返回未知状态: {res_json}")
            return "RETRY"

        except Exception as e:
            self.log(f"Step 3: 浏览器执行登录JS异常: {e}")
            return "RETRY"

    def step_5_verify_login(self):
        """在浏览器中验证登录"""
        for _ in range(3):
            try:
                # 关键修改：因为 Step 3 是在浏览器里登录的，Cookies 已经在浏览器里了
                # 不需要再做任何 Cookie 同步操作，直接打开目标网页即可
                
                self.log("Step 5: 打开会员中心...")
                self.driver.get(MEMBER_URL)
                
                # 等待加载完毕
                WebDriverWait(self.driver, 20).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                time.sleep(5) # 硬性等待 5 秒
                
                # 检测客编
                page_source = self.driver.page_source
                if "客编" in page_source:
                    match = re.search(r'客编\s*([A-Z0-9]+)', page_source)
                    code = match.group(1) if match else "Unknown"
                    self.log(f"Step 5: 验证登录成功，客编: {code}")
                    return True
                else:
                    self.log("Step 5: 页面未找到'客编'字样。")
            except Exception as e:
                self.log(f"Step 5: 验证流程异常: {e}")
            
            self.log("Step 5: 验证失败，重试中...")
            time.sleep(2)
            
        return False

    def step_7_start_exam(self):
        """打开考试页面并点击开始"""
        for i in range(3):
            try:
                self.log(f"Step 7: 进入考试页面 (第 {i+1} 次)...")
                self.driver.get(EXAM_PRE_URL)
                
                try:
                    start_btn = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.ID, "startExamBtn"))
                    )
                    self.driver.execute_script("arguments[0].click();", start_btn)
                    self.log("Step 7: 点击了开始答题按钮。")
                    return True
                except TimeoutException:
                    self.log(f"Step 7: 未找到开始按钮。标题: {self.driver.title}")
                    self.driver.refresh()
                    time.sleep(3)
            except Exception as e:
                self.log(f"Step 7: 页面加载异常: {e}")
        
        return False

    def step_8_9_exam_process(self):
        """等待插件答题并检查分数"""
        start_time = time.time()
        
        while time.time() - start_time < 180: # 3分钟超时
            try:
                score_elements = self.driver.find_elements(By.CLASS_NAME, "score")
                if score_elements:
                    score_text = score_elements[0].text
                    # 确保获取到的是数字
                    if score_text.isdigit():
                        self.log(f"Step 9: 检测到分数: {score_text}")
                        return int(score_text)
                
                time.sleep(2)
            except Exception:
                pass
        
        self.log("Step 9: 等待结果超时 (3分钟)。")
        return -1 

    def process_account(self, idx, username, password):
        """单个账号处理流程"""
        self.log(f"=== 开始处理账号 {idx+1}: {username} ===")
        
        account_retry_count = 0
        while account_retry_count < 3:
            try:
                # 1. 初始化会话 (Browser Fetch)
                self.step_1_check_init_session() 
                
                # 2. 获取验证码
                ticket = self.step_2_get_captcha() 
                
                # 3. 登录 (Browser Fetch)
                # 注意：这一步执行完，浏览器就已经有登录状态了
                login_status = self.step_3_login_browser_console(username, password, ticket)
                
                if login_status == "SKIP":
                    self.results.append(f"账号{idx+1}: 立创题库答题失败❌原因:账号或密码不正确")
                    self.close_browser()
                    return 
                
                if login_status == "RETRY":
                    account_retry_count += 1
                    self.log(f"登录接口返回异常，重试账号全流程 ({account_retry_count}/3)")
                    self.close_browser()
                    continue

                # 5. 验证登录
                # 因为已经在浏览器里了，直接跳转页面验证即可
                if not self.step_5_verify_login():
                    account_retry_count += 1
                    self.log(f"登录验证失败，重试账号全流程 ({account_retry_count}/3)")
                    self.close_browser()
                    continue

                # 答题流程
                exam_retry_count = 0
                final_score = 0
                exam_success = False

                while exam_retry_count < 3:
                    if not self.step_7_start_exam():
                        self.log("无法找到开始考试按钮，跳过该账号。")
                        break 
                    
                    score = self.step_8_9_exam_process()
                    final_score = score
                    
                    if score >= 60:
                        exam_success = True
                        break 
                    else:
                        exam_retry_count += 1
                        self.log(f"答题失败 (分数: {score} 或 超时)，重试答题流程 ({exam_retry_count}/3)...")
                        time.sleep(2)

                self.close_browser()

                if exam_success:
                    self.results.append(f"账号{idx+1}: 立创题库答题成功✅分数:{final_score}")
                else:
                    reason = f"最高得分{final_score}" if final_score != -1 else "脚本超过3分钟未执行成功"
                    self.results.append(f"账号{idx+1}: 立创题库答题失败❌原因:{reason}")
                
                return 

            except Exception as e:
                self.log(f"账号处理发生未捕获异常: {e}")
                traceback.print_exc()
                account_retry_count += 1
                self.close_browser()
        
        self.results.append(f"账号{idx+1}: 立创题库答题失败❌原因: 流程重试超过3次")

    def run(self):
        if len(sys.argv) < 3:
            print("用法: python jlc.py 账号1,账号2... 密码1,密码2... [失败退出标志]")
            print("示例: python jlc.py user1,user2 pwd1,pwd2 true")
            sys.exit(0)

        users = sys.argv[1].split(',')
        pwds = sys.argv[2].split(',')
        
        fail_exit_enabled = False
        if len(sys.argv) > 3 and sys.argv[3].lower() == 'true':
            fail_exit_enabled = True

        if len(users) != len(pwds):
            print("错误: 账号数量与密码数量不匹配")
            sys.exit(1)

        print(f"失败退出标志: {'开启' if fail_exit_enabled else '关闭'}")

        for i in range(len(users)):
            self.process_account(i, users[i], pwds[i])
            self.close_browser()

        print("\n" + "="*30)
        print("运行总结")
        print("="*30)
        
        success_count = 0
        for res in self.results:
            print(res)
            if "答题成功" in res:
                success_count += 1
        
        total = len(users)
        pass_rate = (success_count / total) * 100 if total > 0 else 0
        print(f"\n通过率: {pass_rate:.2f}% ({success_count}/{total})")

        if fail_exit_enabled and pass_rate < 100:
            sys.exit(1)
        
        sys.exit(0)

if __name__ == "__main__":
    bot = JLCBot()
    bot.run()
