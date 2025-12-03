import os
import time
import subprocess as sp
from datetime import datetime


class Pusher:
    def __init__(self, folder_path=".", msg="push", interval=5, repo_url=""):
        self.folder_path = folder_path
        self.total_size = 0
        self.cur_size = 0
        self.change_threshold_kb = -2
        self.msg = msg
        self.interval = interval
        self.repo_url = repo_url
        self.last_push_time = None

        print(f"🔧 Pusher初始化:")
        print(f"   文件夹路径: {self.folder_path}")
        print(f"   变化阈值: {self.change_threshold_kb}KB")
        print(f"   检查间隔: {self.interval}秒")
        print(f"   远程仓库: {self.repo_url if self.repo_url else '未设置'}")

    def scan_files(self):
        self.cur_size = 0

        for root, dirs, files in os.walk(self.folder_path):
            if '.git' in root:
                continue

            for file in files:
                file_path = os.path.join(root, file)
                try:
                    self.cur_size += os.path.getsize(file_path)
                except Exception:
                    continue

        return self.cur_size

    def differ_checker(self):
        diff_bytes = abs(self.cur_size - self.total_size)
        diff_kb = diff_bytes / 1024
        return diff_kb > self.change_threshold_kb

    def polling_check(self):
        print(f"🔄 开始轮询检查，间隔: {self.interval}秒")

        while True:
            print(f"\n{'=' * 40}")
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"⏰ {timestamp}")

            current_size = self.scan_files()

            if self.total_size == 0:
                print(f"📝 首次扫描，记录初始大小")
                self.total_size = current_size
            else:
                if self.differ_checker():
                    print(f"🚨 检测到显著变化，触发推送")
                    if self.push():
                        self.total_size = current_size
                        print(f"✅ 推送成功，更新记录大小")
                else:
                    print(f"📭 变化未超过阈值，跳过推送")

            time.sleep(self.interval)

    def setup_gitrepo(self):
        print(f"⚙️ 检查Git仓库配置...")

        if not os.path.exists(".git"):
            print(f"   初始化Git仓库")
            sp.run(["git", "init"], capture_output=True, universal_newlines=True)
        else:
            print(f"   Git仓库已存在")

        result = sp.run(["git", "remote", "-v"], capture_output=True, universal_newlines=True)
        if not result.stdout.strip():
            if self.repo_url:
                print(f"   添加远程仓库: {self.repo_url}")
                sp.run(["git", "remote", "add", "origin", self.repo_url],
                       capture_output=True, universal_newlines=True)
            else:
                print(f"   ⚠️ 未提供远程仓库URL")
                return False

        return True

    def push(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚀 {timestamp} 开始推送操作")

        try:
            # 1. 添加文件
            print(f"   git add .")
            add_result = sp.run(["git", "add", "."], capture_output=True, universal_newlines=True)

            # 2. 提交
            print(f"   git commit -m '{self.msg}'")
            commit_result = sp.run(["git", "commit", "-m", self.msg],
                                   capture_output=True, universal_newlines=True)

            # 检查是否有需要提交的内容
            output = (commit_result.stdout or "") + (commit_result.stderr or "")
            if "nothing to commit" in output:
                print(f"   没有需要提交的更改")
                return True

            if commit_result.returncode != 0:
                print(f"   ❌ 提交失败")
                return False

            print(f"   提交成功")

            # 3. 获取当前分支
            branch_result = sp.run(["git", "branch", "--show-current"],
                                   capture_output=True, universal_newlines=True)
            current_branch = branch_result.stdout.strip() if branch_result.stdout else "main"

            # 4. 推送
            print(f"   git push origin {current_branch}")
            push_result = sp.run(["git", "push", "origin", current_branch],
                                 capture_output=True, universal_newlines=True)

            # 如果是首次推送，使用 -u 参数
            if push_result.returncode != 0:
                error_msg = push_result.stderr or ""
                if "no upstream" in error_msg or "fatal" in error_msg:
                    print(f"   首次推送，使用 -u 参数")
                    print(f"   git push -u origin {current_branch}")
                    push_result = sp.run(["git", "push", "-u", "origin", current_branch],
                                         capture_output=True, universal_newlines=True)

            if push_result.returncode == 0:
                print(f"✅ 推送成功!")
                self.last_push_time = timestamp
                return True
            else:
                print(f"❌ 推送失败")
                return False

        except Exception as e:
            print(f"❌ 异常: {e}")
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

    try:
        pusher.start()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")