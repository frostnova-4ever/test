import os
import time
import subprocess as sp
import threading
from typing import Optional, Dict, List, Union, Callable


class GitPusher:
    """
    Git自动推送工具类

    使用方法:
    >>> pusher = GitPusher(repo_url="https://github.com/username/repo.git")
    >>> pusher.setup_repository()  # 设置仓库
    >>> pusher.start_monitoring()  # 开始监控推送
    >>> # 或者手动推送
    >>> pusher.push_files("提交说明")
    """

    def __init__(self,
                 folder_path: str = ".",
                 repo_url: Optional[str] = None,
                 default_commit_msg: str = "自动提交",
                 change_threshold_kb: int = 10,
                 poll_interval: int = 5):
        """
        初始化Git推送器

        Args:
            folder_path: 监控的文件夹路径
            repo_url: Git远程仓库URL
            default_commit_msg: 默认提交信息
            change_threshold_kb: 变化阈值(KB)
            poll_interval: 轮询间隔(秒)
        """
        self.folder_path = os.path.abspath(folder_path)
        self.repo_url = repo_url
        self.default_commit_msg = default_commit_msg
        self.change_threshold_bytes = change_threshold_kb * 1024
        self.poll_interval = poll_interval

        self.total_size = 0
        self.current_size = 0
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        # 回调函数
        self.on_push_start: Optional[Callable] = None
        self.on_push_success: Optional[Callable] = None
        self.on_push_fail: Optional[Callable] = None
        self.on_monitoring_start: Optional[Callable] = None
        self.on_monitoring_stop: Optional[Callable] = None

    # ==================== 基础工具方法 ====================

    def run_git_command(self,
                        cmd: List[str],
                        cwd: Optional[str] = None) -> sp.CompletedProcess:
        """
        运行Git命令

        Args:
            cmd: Git命令参数列表
            cwd: 工作目录，默认为self.folder_path

        Returns:
            subprocess.CompletedProcess对象
        """
        working_dir = cwd or self.folder_path
        try:
            result = sp.run(["git"] + cmd,
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='ignore',
                            cwd=working_dir)
            return result
        except Exception as e:
            # 返回一个模拟的CompletedProcess对象
            return sp.CompletedProcess(
                args=["git"] + cmd,
                returncode=1,
                stdout="",
                stderr=str(e)
            )

    def is_git_repository(self) -> bool:
        """检查当前目录是否为Git仓库"""
        git_dir = os.path.join(self.folder_path, ".git")
        return os.path.exists(git_dir)

    def get_current_branch(self) -> str:
        """获取当前分支名称"""
        result = self.run_git_command(["branch", "--show-current"])
        branch = result.stdout.strip()
        return branch if branch else "main"

    def has_remote_configured(self) -> bool:
        """检查是否配置了远程仓库"""
        result = self.run_git_command(["remote", "-v"])
        return bool(result.stdout.strip())

    def get_file_changes(self) -> Dict[str, List[str]]:
        """获取文件变更状态"""
        result = self.run_git_command(["status", "--porcelain"])
        changes = {
            "modified": [],
            "added": [],
            "deleted": [],
            "renamed": []
        }

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            status = line[:2].strip()
            filename = line[3:]

            if status == 'M':
                changes["modified"].append(filename)
            elif status == 'A' or status == '??':
                changes["added"].append(filename)
            elif status == 'D':
                changes["deleted"].append(filename)
            elif status == 'R':
                changes["renamed"].append(filename)

        return changes

    # ==================== 仓库设置方法 ====================

    def setup_repository(self,
                         repo_url: Optional[str] = None,
                         username: Optional[str] = None,
                         email: Optional[str] = None) -> bool:
        """
        设置Git仓库

        Args:
            repo_url: 远程仓库URL
            username: Git用户名
            email: Git邮箱

        Returns:
            bool: 设置是否成功
        """
        repo_url = repo_url or self.repo_url

        # 1. 初始化仓库（如果未初始化）
        if not self.is_git_repository():
            print(f"初始化Git仓库: {self.folder_path}")
            result = self.run_git_command(["init"])
            if result.returncode != 0:
                print(f"初始化失败: {result.stderr}")
                return False

        # 2. 配置用户信息（如果提供）
        if username and email:
            self.run_git_command(["config", "user.name", username])
            self.run_git_command(["config", "user.email", email])

        # 3. 配置远程仓库（如果提供URL）
        if repo_url:
            # 检查是否已配置远程仓库
            if not self.has_remote_configured():
                print(f"添加远程仓库: {repo_url}")
                result = self.run_git_command(["remote", "add", "origin", repo_url])
                if result.returncode != 0:
                    print(f"添加远程仓库失败: {result.stderr}")
                    return False
            else:
                # 更新远程仓库URL
                print(f"更新远程仓库URL: {repo_url}")
                self.run_git_command(["remote", "set-url", "origin", repo_url])

        return True

    # ==================== 文件监控方法 ====================

    def calculate_folder_size(self) -> int:
        """
        计算文件夹总大小（排除.git目录）

        Returns:
            总大小（字节）
        """
        total_size = 0

        for root, dirs, files in os.walk(self.folder_path):
            # 排除.git目录
            if '.git' in root:
                continue

            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                except (OSError, PermissionError):
                    continue

        return total_size

    def check_size_changes(self) -> bool:
        """
        检查文件夹大小是否发生变化

        Returns:
            bool: 是否超过阈值
        """
        self.current_size = self.calculate_folder_size()

        if self.total_size == 0:
            self.total_size = self.current_size
            return False

        size_diff = abs(self.current_size - self.total_size)
        return size_diff >= self.change_threshold_bytes

    # ==================== 推送操作方法 ====================

    def stage_files(self, file_pattern: str = ".") -> bool:
        """
        将文件添加到暂存区

        Args:
            file_pattern: 文件模式，默认为所有文件

        Returns:
            bool: 是否成功
        """
        result = self.run_git_command(["add", file_pattern])
        return result.returncode == 0

    def commit_changes(self, message: Optional[str] = None) -> bool:
        """
        提交更改

        Args:
            message: 提交信息

        Returns:
            bool: 是否成功
        """
        msg = message or self.default_commit_msg
        result = self.run_git_command(["commit", "-m", msg])

        # 检查是否没有更改
        output = result.stdout + result.stderr
        if "nothing to commit" in output or "no changes added to commit" in output:
            return False

        return result.returncode == 0

    def push_to_remote(self,
                       branch: Optional[str] = None,
                       force: bool = False,
                       set_upstream: bool = False) -> bool:
        """
        推送到远程仓库

        Args:
            branch: 分支名称，默认为当前分支
            force: 是否强制推送
            set_upstream: 是否设置上游分支

        Returns:
            bool: 是否成功
        """
        branch = branch or self.get_current_branch()

        # 构建推送命令
        cmd = ["push", "origin", branch]
        if force:
            cmd.append("--force")
        if set_upstream:
            cmd.append("-u")

        result = self.run_git_command(cmd)

        # 如果是首次推送失败，自动设置上游分支重试
        if result.returncode != 0 and "no upstream branch" in result.stderr:
            print(f"首次推送 {branch} 分支，设置上游分支...")
            result = self.run_git_command(["push", "-u", "origin", branch])

        return result.returncode == 0

    def push_files(self,
                   commit_message: Optional[str] = None,
                   branch: Optional[str] = None,
                   force: bool = False) -> bool:
        """
        完整的推送流程

        Args:
            commit_message: 提交信息
            branch: 分支名称
            force: 是否强制推送

        Returns:
            bool: 是否成功
        """
        # 触发开始回调
        if self.on_push_start:
            self.on_push_start()

        try:
            # 1. 添加文件
            if not self.stage_files():
                print("添加文件失败")
                if self.on_push_fail:
                    self.on_push_fail("添加文件失败")
                return False

            # 2. 提交更改
            if not self.commit_changes(commit_message):
                print("没有需要提交的更改")
                if self.on_push_fail:
                    self.on_push_fail("没有需要提交的更改")
                return False

            # 3. 推送到远程
            if not self.push_to_remote(branch, force, True):
                print("推送失败")
                if self.on_push_fail:
                    self.on_push_fail("推送失败")
                return False

            # 成功回调
            if self.on_push_success:
                self.on_push_success()

            return True

        except Exception as e:
            print(f"推送过程中出错: {e}")
            if self.on_push_fail:
                self.on_push_fail(str(e))
            return False

    # ==================== 监控控制方法 ====================

    def _monitoring_loop(self):
        """监控循环"""
        if self.on_monitoring_start:
            self.on_monitoring_start()

        print(f"开始监控文件夹: {self.folder_path}")
        print(f"变化阈值: {self.change_threshold_bytes / 1024}KB")
        print(f"检查间隔: {self.poll_interval}秒")

        while self.monitoring:
            try:
                # 检查大小变化
                if self.check_size_changes():
                    print(f"检测到文件变化，开始推送...")

                    # 执行推送
                    success = self.push_files()

                    if success:
                        print(f"推送成功，更新文件大小记录")
                        self.total_size = self.current_size
                    else:
                        print(f"推送失败")

                # 等待下次检查
                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"监控过程中出错: {e}")
                time.sleep(self.poll_interval)

    def start_monitoring(self, background: bool = True):
        """
        开始监控文件夹变化

        Args:
            background: 是否在后台运行
        """
        if self.monitoring:
            print("监控已在运行中")
            return

        self.monitoring = True

        if background:
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitor_thread.start()
            print("监控已在后台启动")
        else:
            # 前台运行
            self._monitoring_loop()

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

        if self.on_monitoring_stop:
            self.on_monitoring_stop()

        print("监控已停止")

    # ==================== 状态查询方法 ====================

    def get_status(self) -> Dict[str, Union[str, int, bool]]:
        """获取当前状态"""
        return {
            "folder_path": self.folder_path,
            "is_git_repo": self.is_git_repository(),
            "has_remote": self.has_remote_configured(),
            "current_branch": self.get_current_branch(),
            "monitoring": self.monitoring,
            "total_size_kb": self.total_size / 1024,
            "current_size_kb": self.current_size / 1024,
            "poll_interval": self.poll_interval,
            "change_threshold_kb": self.change_threshold_bytes / 1024
        }

    def print_status(self):
        """打印当前状态"""
        status = self.get_status()
        print("\n" + "=" * 50)
        print("GitPusher 状态:")
        print("=" * 50)
        for key, value in status.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        print("=" * 50)


# ==================== 示例使用 ====================
if __name__ == "__main__":
    # 示例1: 基本使用
    def example_basic():
        pusher = GitPusher(
            folder_path=".",
            repo_url="https://github.com/frostnova-4ever/test.git",
            default_commit_msg="自动提交更新",
            change_threshold_kb=10,
            poll_interval=30
        )

        # 设置仓库
        pusher.setup_repository()

        # 打印状态
        pusher.print_status()

        # 手动推送一次
        pusher.push_files("手动提交测试")

        # 开始监控
        pusher.start_monitoring()

        # 主线程保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pusher.stop_monitoring()


    # 示例2: 使用回调函数
    def example_with_callbacks():
        def on_push_start():
            print("🚀 开始推送...")

        def on_push_success():
            print("✅ 推送成功!")

        def on_push_fail(reason):
            print(f"❌ 推送失败: {reason}")

        pusher = GitPusher(repo_url="https://github.com/frostnova-4ever/test.git")
        pusher.on_push_start = on_push_start
        pusher.on_push_success = on_push_success
        pusher.on_push_fail = on_push_fail

        # 设置并推送
        pusher.setup_repository()
        pusher.push_files("使用回调函数的推送测试")


    # 运行示例
    example_basic()
    # example_with_callbacks()