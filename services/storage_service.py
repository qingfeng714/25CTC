class StorageService:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_detection(self, case_id: str, data: dict):
        """保存检测结果到JSON文件"""
        output_path = self.output_dir / f"{case_id}.json"
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)