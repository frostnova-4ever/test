import os
import time
import subprocess as sp


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
        """运行git命令，处理Windows编码问题"""
        try:
            result = sp.run(["git"] + cmd,
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='ignore')
            return result
        except:
            return type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': ''})()

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
        return abs(self.cur_size - self.total_size) > self.change_threshold_kb * 1024

    # 轮询仓库
    def polling_check(self):
        while True:
            self.scan_files()
            if self.differ_checker():
                self.push()
                self.total_size = self.cur_size  # 推送后更新大小
            print(1)
            time.sleep(self.interval)

    def setup_gitrepo(self):
        if not os.path.exists(".git"):
            self.run_git(["init"])

        result = self.run_git(["remote", "-v"])
        if not result.stdout.strip() and self.repo_url:
            self.run_git(["remote", "add", "origin", self.repo_url])

    # 推送
    def push(self):
        # 添加文件
        self.run_git(["add", "."])

        # 提交
        commit_result = self.run_git(["commit", "-m", self.msg])

        # 检查是否有更改
        output = commit_result.stdout + commit_result.stderr
        if "nothing to commit" in output:
            return True

        # 推送
        push_result = self.run_git(["push", "origin", "main"])

        # 如果失败，尝试master分支
        if push_result.returncode != 0:
            push_result = self.run_git(["push", "origin", "master"])

        # 如果还是失败，使用-u参数
        if push_result.returncode != 0:
            self.run_git(["push", "-u", "origin", "main"])

        return True

    def start(self):
        self.setup_gitrepo()
        self.polling_check()


if __name__ == "__main__":
    pusher = Pusher(repo_url="https://github.com/frostnova-4ever/test.git")
    pusher.start()