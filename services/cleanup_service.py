"""
上传文件清理服务
自动清理超过指定时间的上传文件
"""
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
import threading

class CleanupService:
    """文件清理服务"""
    
    def __init__(self, upload_dir='uploads', max_age_hours=24):
        """
        初始化清理服务
        :param upload_dir: 上传目录
        :param max_age_hours: 文件最大保留时间（小时）
        """
        self.upload_dir = Path(upload_dir)
        self.max_age_hours = max_age_hours
        self.is_running = False
        self.cleanup_thread = None
    
    def cleanup_old_files(self):
        """清理超过指定时间的文件"""
        if not self.upload_dir.exists():
            print(f"[CLEANUP] 目录不存在: {self.upload_dir}")
            return
        
        cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
        deleted_count = 0
        total_size = 0
        
        try:
            # 遍历所有文件
            for file_path in self.upload_dir.glob('**/*'):
                if file_path.is_file():
                    try:
                        # 获取文件修改时间
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        
                        # 如果文件过期，删除它
                        if file_mtime < cutoff_time:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            deleted_count += 1
                            total_size += file_size
                            print(f"[CLEANUP] 删除过期文件: {file_path.name} ({file_size / 1024 / 1024:.2f} MB)")
                    except Exception as e:
                        print(f"[CLEANUP] 删除文件失败 {file_path}: {e}")
            
            # 删除空目录
            for dir_path in sorted(self.upload_dir.glob('**/*'), reverse=True):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                        print(f"[CLEANUP] 删除空目录: {dir_path}")
                    except Exception as e:
                        print(f"[CLEANUP] 删除目录失败 {dir_path}: {e}")
            
            if deleted_count > 0:
                print(f"[CLEANUP] 清理完成: 删除 {deleted_count} 个文件，释放 {total_size / 1024 / 1024:.2f} MB空间")
            else:
                print(f"[CLEANUP] 无需清理，没有过期文件")
                
        except Exception as e:
            print(f"[CLEANUP] 清理过程出错: {e}")
    
    def start_periodic_cleanup(self, interval_hours=1):
        """
        启动定期清理任务
        :param interval_hours: 清理间隔（小时）
        """
        if self.is_running:
            print("[CLEANUP] 清理服务已在运行")
            return
        
        self.is_running = True
        
        def cleanup_loop():
            print(f"[CLEANUP] 启动定期清理服务，间隔={interval_hours}小时，最大文件年龄={self.max_age_hours}小时")
            while self.is_running:
                self.cleanup_old_files()
                time.sleep(interval_hours * 3600)  # 转换为秒
        
        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        print("[CLEANUP] 清理服务线程已启动")
    
    def stop(self):
        """停止清理服务"""
        if self.is_running:
            self.is_running = False
            print("[CLEANUP] 清理服务已停止")
    
    def get_upload_stats(self):
        """获取上传目录统计信息"""
        if not self.upload_dir.exists():
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'oldest_file': None
            }
        
        files = list(self.upload_dir.glob('**/*'))
        files = [f for f in files if f.is_file()]
        
        if not files:
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'oldest_file': None
            }
        
        total_size = sum(f.stat().st_size for f in files)
        oldest_file = min(files, key=lambda f: f.stat().st_mtime)
        oldest_time = datetime.fromtimestamp(oldest_file.stat().st_mtime)
        
        return {
            'total_files': len(files),
            'total_size_mb': total_size / 1024 / 1024,
            'oldest_file': oldest_file.name,
            'oldest_time': oldest_time.strftime('%Y-%m-%d %H:%M:%S'),
            'upload_dir': str(self.upload_dir)
        }

