# 部署指南

## 系统要求

### 硬件要求
- CPU: 2核心以上
- 内存: 4GB以上（推荐8GB）
- 存储: 10GB以上可用空间
- GPU: 可选（用于加速DICOM处理）

### 软件要求
- Python 3.8 或更高版本
- pip 包管理器
- 现代浏览器（Chrome、Firefox、Edge等）

## 安装步骤

### 1. 环境准备

```bash
# 创建项目目录
mkdir medical-privacy-protection
cd medical-privacy-protection

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 2. 安装依赖

```bash
# 安装核心依赖
pip install -r requirements.txt

# 可选：安装GPU支持（如果有NVIDIA GPU）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# 可选：安装SPHINCS+签名支持
pip install pyspx
```

### 3. 配置系统

```bash
# 创建必要的目录
mkdir -p uploads output storage_repo/cas storage_repo/batches storage_repo/db

# 设置环境变量（可选）
export STORAGE_REPO="./storage_repo"
export MAX_FILE_SIZE="500"  # MB
```

### 4. 启动服务

```bash
# 方式1：使用批处理文件（Windows）
start_server.bat

# 方式2：命令行启动
python app.py --port 5000 --host 0.0.0.0

# 方式3：后台运行（Linux/Mac）
nohup python app.py --port 5000 > server.log 2>&1 &
```

## 生产环境部署

### 使用Gunicorn（推荐）

```bash
# 安装Gunicorn
pip install gunicorn

# 启动服务
gunicorn -w 4 -b 0.0.0.0:5000 app:create_app()
```

### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 文件上传大小限制
    client_max_body_size 500M;
}
```

### 使用Docker（可选）

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"]
```

```bash
# 构建镜像
docker build -t medical-privacy-protection .

# 运行容器
docker run -d -p 5000:5000 \
  -v $(pwd)/storage_repo:/app/storage_repo \
  -v $(pwd)/output:/app/output \
  medical-privacy-protection
```

## 配置说明

### 应用配置

在 `app.py` 中可以配置：

```python
app.config.update({
    'UPLOAD_FOLDER': './uploads',      # 上传目录
    'OUTPUT_DIR': './output',          # 输出目录
    'STORAGE_REPO': './storage_repo',  # 存储仓库
    'MAX_CONTENT_LENGTH': 500 * 1024 * 1024  # 最大文件大小（500MB）
})
```

### 安全配置

- **密钥管理**: 保护层密钥存储在内存中，重启后重新生成
- **文件清理**: 上传文件24小时后自动清理
- **访问控制**: 建议在生产环境中添加认证机制

## 性能优化

### 1. 启用GPU加速

```python
# 在 app.py 中
device = 'cuda' if torch.cuda.is_available() else 'cpu'
app.crossmodal_svc = CrossModalAttentionService(device=device)
```

### 2. 调整并发数

```bash
# Gunicorn工作进程数
gunicorn -w 4 -b 0.0.0.0:5000 app:create_app()
```

### 3. 数据库优化

```python
# 定期清理旧数据
python debug_database.py --cleanup
```

## 监控与日志

### 日志配置

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

### 健康检查

```bash
# 检查服务状态
curl http://localhost:5000/api/health

# 检查存储状态
python debug_database.py
```

## 备份与恢复

### 备份存储仓库

```bash
# 备份CAS存储
tar -czf storage_repo_backup.tar.gz storage_repo/

# 备份数据库
cp storage_repo/db/index.sqlite storage_repo_backup.sqlite
```

### 恢复数据

```bash
# 恢复存储仓库
tar -xzf storage_repo_backup.tar.gz

# 恢复数据库
cp storage_repo_backup.sqlite storage_repo/db/index.sqlite
```

## 故障恢复

### 服务无法启动

1. 检查端口是否被占用：`netstat -an | grep 5000`
2. 检查Python版本：`python --version`
3. 检查依赖是否安装：`pip list`
4. 查看错误日志：`tail -f app.log`

### 数据丢失

1. 检查备份文件
2. 从CAS存储恢复：`storage_repo/cas/`
3. 重建索引：`python debug_database.py --rebuild`

## 安全建议

1. **HTTPS**: 在生产环境中使用HTTPS
2. **认证**: 添加用户认证机制
3. **防火墙**: 限制访问IP
4. **密钥管理**: 使用密钥管理服务（KMS）
5. **审计日志**: 定期检查审计日志

## 更新升级

```bash
# 1. 备份数据
tar -czf backup_$(date +%Y%m%d).tar.gz storage_repo/ output/

# 2. 停止服务
pkill -f "python app.py"

# 3. 更新代码
git pull  # 或手动更新文件

# 4. 更新依赖
pip install -r requirements.txt --upgrade

# 5. 重启服务
python app.py
```

---

更多信息请参考 [故障排除指南](TROUBLESHOOTING.md)

