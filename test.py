import os
import time
import subprocess as sp
from datetime import datetime


class Pusher:
    def __init__(self, folder_path=".", msg="push", interval=5, repo_url=""):
        self.folder_path = folder_path
        self.total_size = 0
        self.cur_size = 0
        self.change_threshold_kb = 10
        self.msg = msg
        self.interval = interval
        self.repo_url = repo_url
        self.last_push_time = None

        # 调试信息
        print(f"🔧 [DEBUG] Pusher初始化:")
        print(f"   文件夹路径: {self.folder_path}")
        print(f"   变化阈值: {self.change_threshold_kb}KB")
        print(f"   检查间隔: {self.interval}秒")
        print(f"   远程仓库: {self.repo_url if self.repo_url else '未设置'}")

    def scan_files(self):
        print(f"🔍 [DEBUG] 开始扫描文件: {self.folder_path}")
        self.cur_size = 0
        file_count = 0

        for root, dirs, files in os.walk(self.folder_path):
            if '.git' in root:
                continue

            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    self.cur_size += size
                    file_count += 1
                except Exception:
                    continue

        print(f"📊 [DEBUG] 扫描完成: {file_count}个文件, {self.cur_size / 1024:.2f}KB")
        return self.cur_size

    def differ_checker(self):
        diff_bytes = abs(self.cur_size - self.total_size)
        diff_kb = diff_bytes / 1024
        return diff_kb > self.change_threshold_kb

    # 轮询仓库
    def polling_check(self):
        print(f"🔄 [DEBUG] 开始轮询检查，间隔: {self.interval}秒")

        while True:
            print(f"\n{'=' * 40}")
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"⏰ [TIME] {timestamp}")

            current_size = self.scan_files()

            if self.total_size == 0:
                print(f"📝 [DEBUG] 首次扫描，记录初始大小")
                self.total_size = current_size
            else:
                if self.differ_checker():
                    print(f"🚨 [TRIGGER] 检测到显著变化，触发推送")
                    if self.push():
                        self.total_size = current_size
                        print(f"✅ [SUCCESS] 推送成功，更新记录大小")
                else:
                    print(f"📭 [SKIP] 变化未超过阈值，跳过推送")

            time.sleep(self.interval)

    def setup_gitrepo(self):
        print(f"⚙️ [DEBUG] 检查Git仓库配置...")

        # 检查是否是git仓库
        if not os.path.exists(".git"):
            print(f"   [ACTION] 初始化Git仓库")
            result = sp.run(["git", "init"], capture_output=True, text=True, encoding='utf-8')
            print(f"   [RESULT] git init: {result.returncode == 0}")
        else:
            print(f"   [INFO] Git仓库已存在")

        # 检查远程仓库
        result = sp.run(["git", "remote", "-v"], capture_output=True, text=True, encoding='utf-8')
        print(f"   [DEBUG] 远程仓库状态: {'已配置' if result.stdout.strip() else '未配置'}")

        if not result.stdout.strip():
            if self.repo_url:
                print(f"   [ACTION] 添加远程仓库: {self.repo_url}")
                result = sp.run(["git", "remote", "add", "origin", self.repo_url],
                                capture_output=True, text=True, encoding='utf-8')
                if result.returncode == 0:
                    print(f"   [SUCCESS] 远程仓库已添加")
                else:
                    print(f"   [ERROR] 添加远程仓库失败")
            else:
                print(f"   [WARNING] 未提供远程仓库URL")
                return False

        return True

    def safe_run_git(self, command):
        """安全运行git命令，避免编码问题"""
        try:
            result = sp.run(command, capture_output=True, text=True,
                            encoding='utf-8', errors='ignore')
            # 确保返回的stdout和stderr是字符串
            result.stdout = result.stdout or ""
            result.stderr = result.stderr or ""
            return result
        except Exception as e:
            print(f"   [ERROR] 运行命令失败: {' '.join(command)} - {e}")
            return type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': str(e)})()

    # 推送
    def push(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚀 [PUSH] {timestamp} 开始推送操作")

        try:
            # 1. 添加文件
            print(f"   [STEP 1] git add .")
            result = self.safe_run_git(["git", "add", "."])
            print(f"   [RESULT] returncode={result.returncode}")

            # 2. 提交
            print(f"   [STEP 2] git commit -m '{self.msg}'")
            result = self.safe_run_git(["git", "commit", "-m", self.msg])
            print(f"   [RESULT] returncode={result.returncode}")

            # 安全检查"nothing to commit"
            if result.stdout and "nothing to commit" in result.stdout:
                print(f"   [INFO] 没有需要提交的更改")
                return True
            if result.stderr and "nothing to commit" in result.stderr:
                print(f"   [INFO] 没有需要提交的更改")
                return True

            if result.returncode != 0:
                print(f"   [ERROR] git commit失败")
                return False

            print(f"   [SUCCESS] 提交成功")

            # 3. 推送
            print(f"   [STEP 3] git push origin main")
            result = self.safe_run_git(["git", "push", "origin", "main"])
            print(f"   [RESULT] returncode={result.returncode}")

            # 检查是否是首次推送
            if result.returncode != 0:
                if result.stderr and ("no upstream branch" in result.stderr or "fatal" in result.stderr):
                    print(f"   [INFO] 可能是首次推送，尝试使用 -u 参数")
                    print(f"   [STEP 3.1] git push -u origin main")
                    result = self.safe_run_git(["git", "push", "-u", "origin", "main"])
                    print(f"   [RESULT] returncode={result.returncode}")

            if result.returncode == 0:
                print(f"✅ [SUCCESS] 推送成功!")
                self.last_push_time = timestamp
                return True
            else:
                print(f"❌ [ERROR] 推送失败")
                return False

        except Exception as e:
            print(f"❌ [EXCEPTION] 推送过程中出现异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start(self):
        print(f"\n{'=' * 50}")
        print(f"🚀 启动Pusher自动推送系统")
        print(f"{'=' * 50}")

        if self.setup_gitrepo():
            print(f"\n✅ Git仓库配置完成，开始轮询监控...")
            self.polling_check()
        else:
            print(f"\n❌ Git仓库配置失败，程序退出")


if __name__ == "__main__":
    print("🔧 调试模式启动")

    # 测试配置
    pusher = Pusher(
        folder_path=".",
        msg="自动推送",
        interval=10,
        repo_url="https://github.com/frostnova-4ever/test.git"
    )
    pusher.push()
    try:
        pusher.start()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")