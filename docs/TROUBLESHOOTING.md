# 故障排除指南

## 🎯 常见问题快速索引

| 问题 | 解决方案 | 详见 |
|------|---------|------|
| 单文件显示"需要批量处理" | 清除缓存+重启 | [问题1](#问题1单文件处理报错需要先批量处理) |
| 存储数量显示0 | 重启服务+检查文件名 | [问题2](#问题2存储入库后显示0) |
| 置信度都是98% | 清除缓存 | [问题3](#问题3置信度固定98) |
| 速度超过2秒 | 优化配置 | [问题4](#问题4速度超过2秒) |
| 导入错误 | 检查类名 | [问题5](#问题5导入错误) |

---

## 问题1：单文件处理报错"需要先批量处理"

### 症状

点击"执行保护"时显示：
```
请先执行检测（单文件或批量）
```

或浏览器Alert弹窗：
```
先批量处理
```

### 根本原因

**浏览器缓存了旧版本的JavaScript**，未保存检测结果到全局变量。

### 解决方案

#### 方法1：强制刷新浏览器（最快）⭐

**Windows/Linux:**
```
Ctrl + Shift + R
或
Ctrl + F5
```

**macOS:**
```
Cmd + Shift + R
```

#### 方法2：清空缓存并硬刷新（推荐）⭐⭐

**Chrome/Edge:**
1. 按 `F12` 打开开发者工具
2. **右键点击**刷新按钮
3. 选择"**清空缓存并硬性重新加载**"

**Firefox:**
1. 按 `Ctrl + Shift + Delete`
2. 勾选"缓存"
3. 点击"立即清除"
4. 刷新页面 `F5`

#### 方法3：一键脚本（全自动）⭐⭐⭐

**双击运行**：
```
一键清缓存测试.bat
```

或

```
start_server.bat
```

### 验证修复

1. 按 `F12` 打开开发者工具
2. 切换到"Console"标签
3. 上传文件并检测
4. **应该看到**：
   ```javascript
   [DEBUG] 单文件检测完成，已保存结果: {...}
   ```
5. 点击"执行保护"
6. **应该看到**：
   ```javascript
   [DEBUG] 执行保护函数调用，当前状态: {...}
   ```

### 如果还是不行

**完全重启**：
1. 关闭所有浏览器窗口
2. 停止Flask服务（Ctrl+C）
3. 双击运行 `start_server.bat`
4. 使用无痕模式打开浏览器（Ctrl+Shift+N）
5. 访问 http://127.0.0.1:5000

---

## 问题2：存储入库后显示0

### 症状

点击"存储入库"后弹窗显示：
```
入库成功！
入库数量: 0
```

或点击"查看存储"后显示：
```
暂无存储对象
```

### 根本原因

**DICOM和JSON文件名不匹配**，无法配对入库。

**文件名示例**：
```
❌ 不匹配（旧代码）
protected_dicom/0133cd4a6905be65bd383f99.dcm  (哈希格式)
protected_text/patient00001.json              (patient_id格式)

✅ 匹配（新代码）
protected_dicom/patient00001.dcm  (patient_id格式)
protected_text/patient00001.json  (patient_id格式)
```

### 解决方案

#### 方法1：重启服务（推荐）

**双击运行**：
```
start_server.bat
```

这个脚本会：
1. ✅ 停止Flask服务
2. ✅ 删除Python字节码缓存（.pyc）
3. ✅ 删除旧的输出文件
4. ✅ 删除旧的数据库
5. [OK] 重新启动服务

#### 方法2：手动清理

```powershell
# 1. 停止Flask服务
Ctrl + C（在Flask窗口）

# 2. 删除字节码缓存
Remove-Item services\__pycache__\*.pyc -Force

# 3. 删除旧数据
Remove-Item output -Recurse -Force
Remove-Item storage_repo\db\index.sqlite -Force
Remove-Item storage_repo\cas -Recurse -Force
Remove-Item storage_repo\batches -Recurse -Force

# 4. 重新创建目录
New-Item -ItemType Directory -Path output -Force
New-Item -ItemType Directory -Path storage_repo\db -Force
New-Item -ItemType Directory -Path storage_repo\cas -Force
New-Item -ItemType Directory -Path storage_repo\batches -Force

# 5. 启动服务
python app.py --port 5000
```

### 验证修复

运行数据库检查：
```bash
python debug_database.py
```

**成功示例**：
```
【objects表】
总记录数: 1222  ✅ 不再是0

【保护文件】
protected_dicom: 1222 个文件
  - patient00001.dcm  ✅ patient_id格式
  
protected_text: 1222 个文件
  - patient00001.json  ✅ 匹配
```

### 检查文件命名

```bash
# Windows PowerShell
dir output\batch_*\protected_dicom | Select-Object -First 5
dir output\batch_*\protected_text | Select-Object -First 5
```

**正确命名**：
```
✅ patient00001.dcm
✅ patient00001.json
```

**错误命名**：
```
❌ 0133cd4a6905be65bd383f99.dcm（哈希）
✅ patient00001.json
```

---

## 问题3：置信度固定98%

### 症状

所有实体的置信度都显示为 `0.98`：
```
PATIENT_ID    patient00826    [置信度: 0.98]
PATH          data/...        [置信度: 0.98]
PHONE         13812345678     [置信度: 0.98]
NAME          张三            [置信度: 0.98]
```

### 根本原因

**Python字节码缓存**，服务运行旧代码。

### 解决方案

#### 方法1：重启服务

```bash
# 停止Flask
Ctrl + C

# 删除缓存
Remove-Item services\__pycache__\crossmodal_service.cpython-*.pyc -Force

# Start Server
python app.py --port 5000
```

#### 方法2：一键重启

```
start_server.bat
```

#### 方法3：强制刷新浏览器

```
Ctrl + Shift + R
```

### 验证修复

重新测试后应该看到**不同的置信度**：
```
PATIENT_ID    patient00826    [置信度: 1.00]  ✅ 最高
PATH          data/...        [置信度: 1.00]  ✅ 最高
PHONE         13812345678     [置信度: 0.97]  ✅ 高
NAME          张三            [置信度: 0.95]  ✅ 中高
PATIENT_SEX   Male           [置信度: 0.95]  ✅ 中高
PATIENT_AGE   45             [置信度: 0.95]  ✅ 中高
```

---

## 问题4：速度超过2秒

### 症状

性能测试显示：
```
❌ 速度指标未达标: 2.356s >= 2.0s
```

### 可能原因

1. DICOM文件过大
2. ROI检测耗时
3. CPU性能低
4. 启用了耗时特征提取

### 解决方案

#### 方案1：禁用ROI检测

```python
# services/crossmodal_service.py
processor.process_dicom(Path(dicom_path), try_burnedin=False)
```

#### 方案2：使用GPU加速

```python
# Start Server时使用GPU
service = CrossModalAttentionService(device='cuda')
```

#### 方案3：优化文件大小

- 压缩DICOM文件
- 减少像素数据大小
- 使用缩略图检测

#### 方案4：批量并行

```python
# 使用多进程处理
from multiprocessing import Pool
```

### 验证优化

```bash
python test_performance_metrics.py
```

**预期**：
```
✅ 速度指标达标: 0.856s < 2.0s
```

---

## 问题5：导入错误

### 症状

运行测试时报错：
```python
ImportError: cannot import name 'CrossModalService' from 'services.crossmodal_service'
```

### 根本原因

**类名不匹配**。实际类名是 `CrossModalAttentionService`。

### 解决方案

修改导入语句：
```python
# 错误
from services.crossmodal_service import CrossModalService

# 正确
from services.crossmodal_service import CrossModalAttentionService
```

---

## 问题6：PyDICOM警告

### 症状

终端大量警告：
```
UserWarning: Invalid value for VR DA: '90768852'
```

### 原因

DICOM文件日期字段格式不标准。

### 解决方案

**这只是警告，不影响功能**，可以忽略。

或者修改代码抑制警告：
```python
import warnings
warnings.filterwarnings('ignore', category=UserWarning)
```

---

## 问题7：数据库锁定

### 症状

```
sqlite3.OperationalError: database is locked
```

### 解决方案

```bash
# 停止所有Flask实例
taskkill /F /IM python.exe

# 删除数据库锁文件
Remove-Item storage_repo\db\*.db-journal -Force

# 重启服务
python app.py --port 5000
```

---

## 问题8：端口占用

### 症状

```
OSError: [WinError 10048] 通常每个套接字地址只允许使用一次
```

### 解决方案

```bash
# 查找占用5000端口的进程
netstat -ano | findstr :5000

# 结束进程（替换PID）
taskkill /PID <PID> /F

# 或使用其他端口
python app.py --port 5001
```

---

## 🔍 诊断工具

### 1. 数据库检查

```bash
python debug_database.py
```

**检查项**：
- ✅ 数据库是否存在
- ✅ 表记录数量
- ✅ 文件名格式
- ✅ CAS存储状态

### 2. 日志分析

**Flask终端**：
- 查看错误堆栈
- 检查API调用
- 审计日志

**浏览器Console（F12）**：
- JavaScript错误
- 网络请求
- 调试日志

### 3. 性能测试

```bash
python test_performance_metrics.py
```

**输出分析**：
- 处理时间
- 准确率
- 实体详情
- 详细JSON报告

---

## 📝 调试检查清单

### 环境检查
- [ ] Python版本 ≥ 3.8
- [ ] 依赖包已安装
- [ ] Flask服务正在运行
- [ ] 端口5000可访问

### 缓存检查
- [ ] 浏览器缓存已清除
- [ ] Python .pyc文件已删除
- [ ] 使用无痕模式测试

### 数据检查
- [ ] CSV文件格式正确
- [ ] DICOM文件有效
- [ ] 文件编码正确
- [ ] 文件大小合理

### 存储检查
- [ ] output/目录存在
- [ ] storage_repo/目录存在
- [ ] 数据库文件存在
- [ ] 文件名匹配

---

## 🆘 仍然无法解决？

### 收集信息

1. **Flask日志**（完整输出）
2. **浏览器Console日志**（F12 → Console）
3. **数据库检查结果**（`python debug_database.py`）
4. **性能测试结果**（`performance_test_result.json`）
5. **文件列表**（`dir output\batch_*\protected_*`）

### 重置系统

**完全重置**（清除所有数据）：
```bash
# 运行重置脚本
start_server.bat

# 或手动执行
Remove-Item output -Recurse -Force
Remove-Item storage_repo -Recurse -Force
Remove-Item uploads -Recurse -Force
Remove-Item services\__pycache__ -Recurse -Force

# 重新创建目录
New-Item -ItemType Directory -Path output,storage_repo\db,storage_repo\cas,storage_repo\batches,uploads -Force

# 重启服务
python app.py --port 5000
```

---

## 📚 相关文档

- [测试指南](TESTING_GUIDE.md) - 完整测试流程
- [系统总览](SYSTEM_OVERVIEW.md) - 系统架构说明
- [存储架构](STORAGE_ARCHITECTURE.md) - 存储机制详解

---

**文档版本**: v1.0  
**最后更新**: 2025-10-23  
**问题反馈**: 请提供完整的错误信息和环境描述

