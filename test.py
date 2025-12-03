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
        self.cur_size = 0  # 重置当前大小
        file_count = 0

        for root, dirs, files in os.walk(self.folder_path):
            if '.git' in root:
                print(f"   [DEBUG] 跳过.git目录: {root}")
                continue

            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    self.cur_size += size
                    file_count += 1
                    if file_count <= 5:  # 只显示前5个文件的调试信息
                        print(f"   [DEBUG] 文件: {file_path} - {size / 1024:.2f}KB")
                except Exception as e:
                    print(f"   [WARNING] 无法获取文件大小 {file_path}: {e}")
                    continue

        print(f"📊 [DEBUG] 扫描完成:")
        print(f"   文件总数: {file_count}")
        print(f"   当前大小: {self.cur_size / 1024:.2f}KB")
        print(f"   上次记录大小: {self.total_size / 1024:.2f}KB")

        return self.cur_size

    def differ_checker(self):
        diff_bytes = abs(self.cur_size - self.total_size)
        diff_kb = diff_bytes / 1024
        threshold_kb = self.change_threshold_kb

        print(f"📈 [DEBUG] 大小检查:")
        print(f"   差异: {diff_kb:.2f}KB")
        print(f"   阈值: {threshold_kb}KB")
        print(f"   是否超过阈值: {diff_kb > threshold_kb}")

        return diff_kb > threshold_kb

    # 轮询仓库
    def polling_check(self):
        print(f"🔄 [DEBUG] 开始轮询检查，间隔: {self.interval}秒")

        while True:
            print(f"\n{'=' * 50}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"⏰ [TIME] {timestamp}")

            old_size = self.cur_size
            current_size = self.scan_files()

            if self.total_size == 0:
                print(f"📝 [DEBUG] 首次扫描，记录初始大小")
                self.total_size = current_size
                print(f"   初始大小已设置为: {self.total_size / 1024:.2f}KB")
            else:
                if self.differ_checker():
                    print(f"🚨 [TRIGGER] 检测到显著变化，触发推送")
                    self.push()
                else:
                    print(f"📭 [SKIP] 变化未超过阈值，跳过推送")

            # 等待
            print(f"⏳ [WAIT] 等待 {self.interval} 秒...")
            time.sleep(self.interval)

    def setup_gitrepo(self):
        print(f"⚙️ [DEBUG] 检查Git仓库配置...")

        # 检查是否是git仓库
        if not os.path.exists(".git"):
            print(f"   [ACTION] 初始化Git仓库")
            result = sp.run(["git", "init"], capture_output=True, text=True)
            print(f"   [RESULT] git init: {result.returncode == 0}")
        else:
            print(f"   [INFO] Git仓库已存在")

        # 检查远程仓库
        result = sp.run(["git", "remote", "-v"], capture_output=True, text=True)
        print(f"   [DEBUG] 远程仓库状态: {'已配置' if result.stdout.strip() else '未配置'}")

        if not result.stdout.strip():
            if self.repo_url:
                print(f"   [ACTION] 添加远程仓库: {self.repo_url}")
                result = sp.run(["git", "remote", "add", "origin", self.repo_url],
                                capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"   [SUCCESS] 远程仓库已添加")
                else:
                    print(f"   [ERROR] 添加远程仓库失败: {result.stderr}")
            else:
                print(f"   [WARNING] 未提供远程仓库URL")
                return False
        else:
            print(f"   [INFO] 远程仓库已配置:")
            print(f"   {result.stdout.strip()}")

        return True

    # 推送
    def push(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚀 [PUSH] {timestamp} 开始推送操作")

        try:
            # 1. 添加文件
            print(f"   [STEP 1] git add .")
            result = sp.run(["git", "add", "."], capture_output=True, text=True)
            print(f"   [RESULT] returncode={result.returncode}")
            if result.returncode != 0:
                print(f"   [ERROR] git add失败: {result.stderr}")

            # 2. 提交
            print(f"   [STEP 2] git commit -m '{self.msg}'")
            result = sp.run(["git", "commit", "-m", self.msg], capture_output=True, text=True)
            print(f"   [RESULT] returncode={result.returncode}")

            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print(f"   [INFO] 没有需要提交的更改")
                self.total_size = self.cur_size  # 更新记录的大小
                return False

            if result.returncode != 0:
                print(f"   [ERROR] git commit失败: {result.stderr}")
                return False

            print(f"   [SUCCESS] 提交成功: {result.stdout.strip()}")

            # 3. 推送
            print(f"   [STEP 3] git push origin main")
            result = sp.run(["git", "push", "origin", "main"],
                            capture_output=True, text=True)
            print(f"   [RESULT] returncode={result.returncode}")

            # 检查是否是首次推送
            if result.returncode != 0:
                if "no upstream branch" in result.stderr or "fatal" in result.stderr:
                    print(f"   [INFO] 可能是首次推送，尝试使用 -u 参数")
                    print(f"   [STEP 3.1] git push -u origin main")
                    result = sp.run(["git", "push", "-u", "origin", "main"],
                                    capture_output=True, text=True)
                    print(f"   [RESULT] returncode={result.returncode}")

            if result.returncode == 0:
                print(f"✅ [SUCCESS] 推送成功!")
                print(f"   [OUTPUT] {result.stdout.strip()}")
                self.last_push_time = timestamp
                self.total_size = self.cur_size  # 推送成功后更新记录的大小
                return True
            else:
                print(f"❌ [ERROR] 推送失败:")
                print(f"   [STDERR] {result.stderr}")
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
        interval=10,  # 测试时用10秒间隔
        repo_url="https://github.com/frostnova-4ever/test.git"
    )

    # 先扫描一次看看
    print("\n🔍 测试扫描功能...")
    pusher.scan_files()
    pusher.push()
    # 启动
    try:
        pusher.start()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        import traceback

        traceback.print_exc()