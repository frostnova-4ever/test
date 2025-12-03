import os
import time
import subprocess as sp
from datetime import datetime

class Pusher:
    def __init__(self,folder_path = ".",msg="push",interval=30):
        self.folder_path = folder_path
        self.total_size = 0
        self.cur_size = 0
        self.change_threshold_kb = 10
        self.msg = msg
        self.interval = interval

    def scan_files(self):
        for root,dirs,files in os.walk(self.folder_path):
            if '.git' in root:
                continue
            for file in files:
                file_path = os.path.join(root,file)
                try:
                    self.cur_size+=os.path.getsize(file_path)
                except:
                    continue
        return self.cur_size

    def differ_checker(self):
        return abs(self.cur_size-self.total_size)>self.change_threshold_kb

    #轮询仓库
    def polling_check(self):
        while True:
            self.scan_files()
            if(self.differ_checker()):
                self.push()
            time.sleep(self.interval)

    def setup_gitrepo(self):
        if not os.path.exists("git"):
            sp.run(["git","init"])
        result = sp.run(["git", "remote", "-v"],
                                capture_output=True, text=True)
    #推送
    def push(self):
        try:
            sp.run(["git","add","."],check=True,capture_output=True)
            sp.run(["git","commit","-m",self.msg],check=True,capture_output=True)
            sp.run(["git","push"],check=True,capture_output=True)
            return True
        except sp.CalledProcessError as e:
            if "nothing to commit" not in str(e.output):
                print(f"推送失败: {e}")
            return False
        except Exception as e:
            print(f"异常: {e}")
            return False

    def start(self):
        self.setup_gitrepo()
        self.polling_check()

if __name__ == "__main__":
    pusher = Pusher()
    pusher.start()


