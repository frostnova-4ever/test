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

    def run_git(self, cmd):
        """运行git命令并处理编码"""
        try:
            # 使用universal_newlines解决Windows编码问题
            result = sp.run(["git"] + cmd,
                            capture_output=True,
                            universal_newlines=True,
                            text=True)
            return result
        except Exception as e:
            print(f"运行git命令失败: {' '.join(cmd)} - {e}")
            return type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': str(e)})()

    def scan_files(self):
        self.cur_size = 0
        for root, dirs, files in os.walk(self.folder_path):
            if '.git' in root:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    self.cur_size += os.path.getsize(file_path)
                except:
                    continue
        return self.cur_size

    def differ_checker(self):
        diff_kb = abs(self.cur_size - self.total_size) / 1024
        return diff_kb > self.change_threshold_kb

    # 轮询仓库
    def polling_check(self):
        print(f"开始监控，每{self.interval}秒检查一次")
        while True:
            self.scan_files()
            if self.differ_checker():
                print(f"检测到变化: {(abs(self.cur_size - self.total_size) / 1024):.1f}KB")
                self.push()
            time.sleep(self.interval)

    def setup_gitrepo(self):
        if not os.path.exists(".git"):
            print("初始化Git仓库")
            self.run_git(["init"])

        result = self.run_git(["remote", "-v"])
        if not result.stdout.strip():
            if self.repo_url:
                print(f"添加远程仓库: {self.repo_url}")
                self.run_git(["remote", "add", "origin", self.repo_url])
                return True
            else:
                print("未设置远程仓库URL")
                return False
        return True

    # 推送
    def push(self):
        try:
            # 1. 添加文件
            add_result = self.run_git(["add", "."])
            if add_result.returncode != 0:
                print("添加文件失败")
                return False

            # 2. 提交
            commit_result = self.run_git(["commit", "-m", self.msg])

            # 检查是否没有需要提交的内容
            output = (commit_result.stdout or "") + (commit_result.stderr or "")
            if "nothing to commit" in output:
                print("没有需要提交的更改")
                self.total_size = self.cur_size  # 更新记录的大小
                return True

            if commit_result.returncode != 0:
                print("提交失败")
                return False

            # 3. 尝试推送到main分支
            push_result = self.run_git(["push", "origin", "main"])

            # 如果main分支失败，尝试master分支
            if push_result.returncode != 0:
                error_msg = push_result.stderr or ""
                if "src refspec main does not match any" in error_msg:
                    print("尝试推送到master分支")
                    push_result = self.run_git(["push", "origin", "master"])

            # 如果是首次推送，使用-u参数
            if push_result.returncode != 0:
                error_msg = push_result.stderr or ""
                if "no upstream" in error_msg or "fatal" in error_msg:
                    print("首次推送，使用-u参数")
                    branch_result = self.run_git(["branch", "--show-current"])
                    current_branch = branch_result.stdout.strip() if branch_result.stdout else "main"
                    push_result = self.run_git(["push", "-u", "origin", current_branch])

            # 检查最终结果
            if push_result.returncode == 0:
                print(f"推送成功: {datetime.now().strftime('%H:%M:%S')}")
                self.total_size = self.cur_size  # 推送成功后更新记录的大小
                return True
            else:
                print("推送失败")
                return False

        except Exception as e:
            print(f"推送异常: {e}")
            return False

    def start(self):
        if self.setup_gitrepo():
            print(f"Git仓库配置完成，开始监控...")
            self.polling_check()
        else:
            print("Git仓库配置失败")


if __name__ == "__main__":
    pusher = Pusher(
        msg="自动推送",
        interval=10,
        repo_url="https://github.com/frostnova-4ever/test.git"
    )
    pusher.start()