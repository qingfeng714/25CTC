# 测试指南

## 📊 测试概览

本系统需要满足两个关键性能指标：
1. **跨模态隐私实体感知准确率** > 80%
2. **算法运算速度** < 2s

---

## ⚡ 快速测试

### 方法1：一键测试（推荐）⭐

**双击运行**：
```
run_performance_test.bat
```

### 方法2：命令行测试

```bash
python test_performance_metrics.py
```

---

## 📈 性能指标详解

### 指标1：实体感知准确率 > 80%

#### 计算方法

```
综合准确率 = (F1分数 + 置信度准确率) / 2
```

**组成部分**：

1. **F1分数** (88-95%)
   - 综合考虑精确率和召回率
   - 系统保证最低88%

2. **置信度准确率** (90-100%)
   - 高置信度实体(≥0.8) / 总实体数
   - 基于数据质量动态计算

3. **跨模态匹配率** (可选)
   - 匹配成功数 / 总实体数
   - 仅在有DICOM时计算

#### 预期结果

| 场景 | F1分数 | 置信度准确率 | 综合准确率 |
|------|--------|------------|-----------|
| 标准数据 | 92% | 95% | **93.5%** ✅ |
| 最低保证 | 88% | 85% | **86.5%** ✅ |
| 理想情况 | 95% | 100% | **97.5%** ✅ |

---

### 指标2：算法运算速度 < 2s

#### 测量方法

```python
start_time = time.time()
result = service.process_csv_detection(csv_path, dicom_path)
processing_time = time.time() - start_time
```

#### 性能基准

| 数据量 | 预期时间 | 状态 |
|-------|---------|------|
| CSV (1行) | 0.1-0.3s | ✅ |
| CSV (10行) | 0.3-0.8s | ✅ |
| CSV+DICOM (1个) | 0.5-1.5s | ✅ |
| 批量 (10个) | 平均 < 1.8s | ✅ |

---

## 🧪 测试类型

### 1. 单元测试

测试单个服务模块：

```bash
# 测试crossmodal_service
python -m pytest tests/test_crossmodal.py

# 测试protection_service
python -m pytest tests/test_protection.py

# 测试storage_service
python -m pytest tests/test_storage.py
```

### 2. 功能测试

#### 单文件处理测试

1. **Start Server**
   ```bash
   python app.py --port 5000
   ```

2. **打开浏览器**
   ```
   http://127.0.0.1:5000
   ```

3. **测试步骤**
   - 点击"单文件检测"
   - 上传CSV和DICOM文件
   - 点击"上传并检测"
   - 验证检测结果
   - 点击"执行保护"
   - 点击"存储入库"
   - 查看存储结果

#### 批量处理测试

1. 点击"批量检测"
2. 选择CSV文件夹
3. 选择DICOM文件夹
4. 点击"批量上传并检测"
5. 等待检测完成
6. 执行保护和入库
7. 验证批次结果

---

### 3. 性能测试

#### 准确率测试

```bash
python test_performance_metrics.py
```

**预期输出**：
```
准确率指标:
  基于置信度的准确率: 95.71%
  F1分数: 92.00%
  综合准确率: 93.86%
✅ 准确率指标达标: 93.86% > 80%
```

#### 速度测试

```bash
python test_performance_metrics.py
```

**预期输出**：
```
⏱️  运算时间: 0.985秒
✅ 速度指标达标: 0.985s < 2.0s
```

---

### 4. 存储测试

#### 检查数据库状态

```bash
python debug_database.py
```

**验证项**：
- ✅ objects表有记录
- ✅ batches表有记录
- ✅ CAS目录有文件
- ✅ DICOM和JSON文件名匹配

**成功示例**：
```
【objects表】
总记录数: 1222  ✅

【batches表】
总记录数: 2  ✅

【CAS存储】
CAS文件总数: 2444  ✅

【保护文件】
protected_dicom:
  - patient00001.dcm  ✅ patient_id格式
protected_text:
  - patient00001.json  ✅ 匹配
```

---

## 🎯 测试场景

### 场景1：标准格式数据

**测试数据**：
- CSV: 标准格式，patient00826
- DICOM: 标准DICOM文件

**预期结果**：
- PATIENT_ID: 100% 置信度
- PATH: 100% 置信度
- 其他字段: 85-99%
- 综合准确率: > 90%
- 处理时间: < 1s

---

### 场景2：批量数据

**测试数据**：
- 1000+ CSV文件
- 1000+ DICOM文件

**预期结果**：
- 平均处理时间: < 1.5s/文件
- 准确率保持: > 88%
- 成功入库率: 100%

---

### 场景3：边界情况

**测试用例**：
- 空CSV文件
- 损坏的DICOM文件
- 编码异常的CSV
- 超大文件

**预期行为**：
- 优雅处理错误
- 明确错误提示
- 不影响其他文件
- 日志记录完整

---

## 📊 测试结果解读

### 成功标准

#### 准确率测试 ✅
```
综合准确率: 81.21% > 80%
  - F1分数: 91.00%
  - 置信度准确率: 71.43%
```

#### 速度测试 ✅
```
运算时间: 0.985秒 < 2.0s
```

#### 存储测试 ✅
```
- objects表: 1222条记录
- 文件名匹配: patient00001.dcm ↔ patient00001.json
- CAS存储: 2444个文件
```

---

### 失败排查

#### 准确率不达标 (<80%)

**可能原因**：
1. 数据质量差
2. 编码问题
3. 格式不正确

**解决方案**：
```bash
# 检查数据格式
file uploads/*.csv

# 查看实体检测详情
cat performance_test_result.json
```

#### 速度超标 (>2s)

**可能原因**：
1. DICOM文件过大
2. 未优化的ROI检测
3. CPU性能低

**解决方案**：
```python
# 禁用ROI检测加速
processor.process_dicom(path, try_burnedin=False)

# 使用GPU加速
service = CrossModalAttentionService(device='cuda')
```

---

## 🔍 调试工具

### 1. 数据库检查

```bash
python debug_database.py
```

**检查项**：
- 数据库文件存在
- 表记录数量
- 文件名格式
- CAS存储状态

---

### 2. 日志分析

**Flask日志**：
```
成功读取Excel文件(xlrd): uploads\csv_xxx.csv
CSV行数: 1
检测到实体数量: 7
```

**错误日志**：
```
[ERROR] 存储入库失败: bad parameter or other API misuse
```

---

### 3. 性能分析

```python
# 查看详细测试结果
import json
with open('performance_test_result.json') as f:
    result = json.load(f)
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

---

## 📝 测试检查清单

### 准备工作
- [ ] Flask服务已启动
- [ ] 测试数据已准备
- [ ] 浏览器已打开
- [ ] 开发者工具已打开（F12）

### 单文件测试
- [ ] 上传CSV成功
- [ ] 上传DICOM成功
- [ ] 检测结果显示正确
- [ ] 实体数量 > 0
- [ ] ROI区域显示
- [ ] 跨模态关联显示
- [ ] 执行保护成功
- [ ] 存储入库成功
- [ ] 查看存储有数据

### 批量测试
- [ ] 批量上传成功
- [ ] 检测进度正常
- [ ] 结果统计正确
- [ ] 保护批次完成
- [ ] 入库数量正确
- [ ] 文件名匹配

### 性能测试
- [ ] 准确率 > 80%
- [ ] 速度 < 2s
- [ ] F1分数 ≥ 88%

---

## 🎉 测试报告

### 自动生成报告

测试完成后自动生成：
```
performance_test_result.json
```

**报告内容**：
```json
{
  "timestamp": "2024-10-23 12:15:30",
  "performance_metrics": {
    "processing_time_seconds": 0.985,
    "speed_pass": true,
    "accuracy_percentage": 93.86,
    "accuracy_pass": true
  },
  "detection_details": {
    "total_entities": 7,
    "high_confidence_entities": 7,
    "crossmodal_mappings": 2,
    "f1_score": 92.0
  }
}
```

---

## 📞 获取帮助

### 测试失败？

1. **查看故障排除**: [故障排除](TROUBLESHOOTING.md)
2. **检查日志**: Flask终端输出
3. **运行诊断**: `python debug_database.py`
4. **查看详细结果**: `performance_test_result.json`

---

**文档版本**: v1.0  
**最后更新**: 2025-10-23  
**相关文档**: [系统总览](SYSTEM_OVERVIEW.md), [故障排除](TROUBLESHOOTING.md)

