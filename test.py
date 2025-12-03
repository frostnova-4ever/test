import os
import time
import subprocess as sp
from datetime import datetime


class Pusher:
    def __init__(self, folder_path=".", msg="push", interval=5, repo_url=""):
        self.folder_path = folder_path
        self.total_size = 0
        self.cur_size = 0
        self.change_threshold_kb = -1
        self.msg = msg
        self.interval = interval
        self.repo_url = repo_url
        self.last_push_time = None

        print(f"🔧 [DEBUG] Pusher初始化:")
        print(f"   文件夹路径: {self.folder_path}")
        print(f"   变化阈值: {self.change_threshold_kb}KB")
        print(f"   检查间隔: {self.interval}秒")
        print(f"   远程仓库: {self.repo_url if self.repo_url else '未设置'}")

    def scan_files(self):
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

        return self.cur_size

    def differ_checker(self):
        diff_bytes = abs(self.cur_size - self.total_size)
        diff_kb = diff_bytes / 1024
        return diff_kb > self.change_threshold_kb

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

        if not os.path.exists(".git"):
            print(f"   [ACTION] 初始化Git仓库")
            sp.run(["git", "init"])
        else:
            print(f"   [INFO] Git仓库已存在")

        result = sp.run(["git", "remote", "-v"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if not result.stdout.strip():
            if self.repo_url:
                print(f"   [ACTION] 添加远程仓库: {self.repo_url}")
                sp.run(["git", "remote", "add", "origin", self.repo_url])
            else:
                print(f"   [WARNING] 未提供远程仓库URL")
                return False

        return True

    def push(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚀 [PUSH] {timestamp} 开始推送操作")

        try:
            # 1. 添加文件
            print(f"   [STEP 1] git add .")
            add_result = sp.run(["git", "add", "."], capture_output=True, text=True)
            print(f"   [RESULT] returncode={add_result.returncode}")

            # 2. 提交
            print(f"   [STEP 2] git commit -m '{self.msg}'")
            commit_result = sp.run(["git", "commit", "-m", self.msg], capture_output=True, text=True)
            print(f"   [RESULT] returncode={commit_result.returncode}")

            # 检查是否有需要提交的内容
            if (commit_result.stdout and "nothing to commit" in commit_result.stdout) or \
                    (commit_result.stderr and "nothing to commit" in commit_result.stderr):
                print(f"   [INFO] 没有需要提交的更改")
                return True

            if commit_result.returncode != 0:
                print(f"   [ERROR] git commit失败")
                if commit_result.stderr:
                    print(f"   [ERROR DETAIL] {commit_result.stderr[:200]}")
                return False

            print(f"   [SUCCESS] 提交成功")

            # 3. 推送 - 首先尝试普通推送
            print(f"   [STEP 3] git push origin main")
            push_result = sp.run(["git", "push", "origin", "main"], capture_output=True, text=True)
            print(f"   [RESULT] returncode={push_result.returncode}")

            # 显示详细的错误信息
            if push_result.returncode != 0:
                print(f"   [ERROR DETAIL] 推送失败原因:")
                if push_result.stderr:
                    print(f"   {push_result.stderr[:500]}")  # 显示前500个字符
                if push_result.stdout:
                    print(f"   stdout: {push_result.stdout[:200]}")

            # 检查并处理常见推送错误
            if push_result.returncode != 0:
                error_msg = push_result.stderr or ""

                # 情况1: 首次推送，需要设置上游分支
                if "no upstream branch" in error_msg or "当前分支没有对应的上游分支" in error_msg:
                    print(f"   [INFO] 首次推送，使用 -u 参数")
                    print(f"   [STEP 3.1] git push -u origin main")
                    push_result = sp.run(["git", "push", "-u", "origin", "main"], capture_output=True, text=True)

                # 情况2: 需要先拉取更新
                elif "non-fast-forward" in error_msg or "failed to push some refs" in error_msg:
                    print(f"   [INFO] 需要先拉取远程更新")
                    print(f"   [STEP 3.2] git pull origin main")
                    pull_result = sp.run(["git", "pull", "origin", "main", "--rebase"], capture_output=True, text=True)
                    print(f"   [PULL RESULT] returncode={pull_result.returncode}")
                    if pull_result.returncode == 0:
                        print(f"   [STEP 3.3] 重新推送")
                        push_result = sp.run(["git", "push", "origin", "main"], capture_output=True, text=True)

                # 情况3: 权限问题或仓库不存在
                elif "Permission denied" in error_msg or "repository not found" in error_msg:
                    print(f"   [ERROR] 权限不足或仓库不存在")
                    print(f"   请检查: 1.仓库URL是否正确 2.是否有推送权限 3.SSH密钥是否配置")

                # 情况4: 需要强制推送（谨慎使用）
                elif "would be overwritten" in error_msg:
                    print(f"   [WARNING] 有文件冲突，需要处理")
                    print(f"   建议手动解决冲突后再推送")

            # 检查最终推送结果
            if push_result.returncode == 0:
                print(f"✅ [SUCCESS] 推送成功!")
                self.last_push_time = timestamp
                return True
            else:
                print(f"❌ [ERROR] 推送最终失败")
                if push_result.stderr:
                    print(f"   [FINAL ERROR] {push_result.stderr[:300]}")
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

    try:
        pusher.start()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")