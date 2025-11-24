# 开发者指南 - 跨模态隐私关联检测系统

## 📚 快速开始

### 1. 系统启动
```bash
# Start Server
python app.py

# 访问前端
http://localhost:5000
```

### 2. 测试接口
```bash
# 使用curl测试CSV上传
curl -X POST http://localhost:5000/api/upload_csv \
  -F "csv_file=@test_medical_data.csv"

# 测试DICOM上传
curl -X POST http://localhost:5000/api/ingest \
  -F "dicom_file=@test_image.dcm"

# 测试检测
curl -X POST http://localhost:5000/api/detect \
  -H "Content-Type: application/json" \
  -d '{"csv_id": "csv_abc123", "dicom_id": "ingest_xyz789"}'
```

---

## 🔧 核心代码解析

### 1. CSV实体提取核心逻辑

**位置**: `services/crossmodal_service.py` → `process_csv_detection()`

```python
# 定义敏感信息列映射
sensitive_cols = {
    'Path': 'PATH',      # 文件路径，包含patient_id
    'Name': 'NAME',      # 姓名
    'Sex': 'SEX',        # 性别
    'Age': 'AGE',        # 年龄
    'Phone': 'PHONE',    # 电话
    'ID_Number': 'ID',   # 身份证号
    'Address': 'ADDRESS' # 地址
}

# 按列精确提取
for idx, row in df.iterrows():
    for col_name, entity_type in sensitive_cols.items():
        if col_name in df.columns and pd.notna(row[col_name]):
            value = str(row[col_name]).strip()
            if value and value != '':
                entities.append({
                    'type': entity_type,
                    'text': value,
                    'confidence': 0.98,
                    'row_index': idx,      # CSV行号
                    'column': col_name      # CSV列名
                })
```

**关键点**:
- ✅ 按列名直接提取，避免正则误匹配
- ✅ 记录行号和列名，便于追溯
- ✅ 高置信度（0.98）因为是结构化数据

---

### 2. Patient ID匹配核心逻辑

**位置**: `services/crossmodal_service.py` → `_match_text_dicom_entities()`

```python
# 从Path列提取patient_id
if entity.get('column') == 'Path':
    import re
    match = re.search(r'patient(\d+)', entity_text)
    if match:
        csv_patient_id = 'patient' + match.group(1)  # 例如: patient00826
        dicom_patient_id = dicom_metadata.get('patient_id', '')
        
        if csv_patient_id == dicom_patient_id:
            # 完全匹配 → critical风险
            mappings.append({
                'csv_row': entity.get('row_index', 0),
                'csv_column': 'Path',
                'csv_value': entity_text,
                'extracted_patient_id': csv_patient_id,
                'dicom_field': 'patient_id',
                'dicom_value': dicom_patient_id,
                'match_type': 'patient_id_exact_match',
                'confidence': 1.0,
                'risk_level': 'critical'
            })
```

**匹配规则**:
- Path格式: `CheXpert-v1.0-small/train/patient00001/study1/view1_frontal.jpg`
- 正则提取: `patient(\d+)` → `patient00001`
- 与DICOM的PatientID字段对比

---

### 3. DICOM Header提取

**位置**: `services/roi_service.py` → `_extract_header_info()`

```python
PHI_TAGS = [
    'PatientID',              # (0010,0020)
    'PatientName',            # (0010,0010)
    'PatientBirthDate',       # (0010,0030)
    'PatientSex',             # (0010,0040)
    'PatientAge',             # (0010,1010)
    'InstitutionName',        # (0008,0080)
    'StudyDate',              # (0008,0020)
    'AccessionNumber',        # (0008,0050)
]

def _extract_header_info(self, ds) -> Dict[str, str]:
    info = {}
    for tag in PHI_TAGS:
        if hasattr(ds, tag):
            value = getattr(ds, tag)
            # 转换DICOM数据类型
            if hasattr(value, 'decode'):
                value = value.decode('utf-8', errors='ignore')
            info[self._to_snake_case(tag)] = str(value)
    return info
```

---

### 4. 前端-后端数据流

**前端上传** (`templates/index.html`):
```javascript
async function handleSingleUpload() {
    const csvFile = document.getElementById('csvFile').files[0];
    const dicomFile = document.getElementById('dicomFile').files[0];
    
    // 1. 上传CSV
    const csvFormData = new FormData();
    csvFormData.append('csv_file', csvFile);
    const csvResponse = await fetch('/api/upload_csv', {
        method: 'POST',
        body: csvFormData
    });
    const csvData = await csvResponse.json();
    
    // 2. 上传DICOM
    const dicomFormData = new FormData();
    dicomFormData.append('dicom_file', dicomFile);
    const dicomResponse = await fetch('/api/ingest', {
        method: 'POST',
        body: dicomFormData
    });
    const dicomData = await dicomResponse.json();
    
    // 3. 调用检测
    const detectResponse = await fetch('/api/detect', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            csv_id: csvData.file_id,
            dicom_id: dicomData.file_id
        })
    });
    const result = await detectResponse.json();
    
    // 4. 显示结果
    displayResults(result);
}
```

**后端处理** (`app.py`):
```python
@app.route('/api/detect', methods=['POST'])
def detect():
    data = request.get_json()
    csv_id = data.get('csv_id')
    dicom_id = data.get('dicom_id')
    
    # 获取文件路径
    csv_path = session_files.get(csv_id)
    dicom_path = session_files.get(dicom_id)
    
    # 调用检测服务
    result = crossmodal_svc.process_csv_detection(
        csv_path=csv_path,
        dicom_path=dicom_path
    )
    
    return jsonify(result)
```

---

## 🎨 前端展示逻辑

### 跨模态关联卡片生成

**位置**: `templates/index.html` → `displayResults()`

```javascript
// 根据匹配类型设置图标和颜色
if (mapping.match_type === 'patient_id_exact_match') {
    icon = '✅';
    title = 'Patient ID 完全匹配';
    // CSS类: .risk-item.critical (红色渐变)
} else if (mapping.match_type === 'name_match') {
    icon = '👤';
    title = '姓名匹配';
    // CSS类: .risk-item.high (橙色渐变)
}

// 动态生成HTML
mappingDiv.innerHTML = `
    <div>${icon} ${title}</div>
    <div><strong>CSV位置:</strong> 第 <code>${mapping.csv_row}</code> 行，<code>${mapping.csv_column}</code> 列</div>
    <div><strong>CSV值:</strong> <code>${mapping.csv_value}</code></div>
    <div><strong>提取的Patient ID:</strong> <code>${mapping.extracted_patient_id}</code></div>
    <div><strong>DICOM字段:</strong> <code>${mapping.dicom_field}</code> = <code>${mapping.dicom_value}</code></div>
    <div><strong>置信度:</strong> ${(mapping.confidence * 100).toFixed(1)}%</div>
    <div><strong>说明:</strong> ${mapping.description}</div>
`;
```

---

## 📊 数据结构详解

### 1. 实体对象
```javascript
{
    "type": "NAME",           // 实体类型
    "text": "Jerry",          // 实体文本
    "start": 0,               // 起始位置（不重要）
    "end": 5,                 // 结束位置（不重要）
    "confidence": 0.98,       // 置信度
    "row_index": 0,           // CSV行号 ⭐
    "column": "Name"          // CSV列名 ⭐
}
```

### 2. 匹配对象
```javascript
{
    "csv_row": 0,                          // CSV行号
    "csv_column": "Path",                  // CSV列名
    "csv_value": "patient00826/...",       // CSV值
    "extracted_patient_id": "patient00826", // 提取的ID ⭐
    "dicom_field": "patient_id",           // DICOM字段名
    "dicom_value": "patient00826",         // DICOM字段值
    "match_type": "patient_id_exact_match", // 匹配类型 ⭐
    "confidence": 1.0,                     // 置信度
    "risk_level": "critical",              // 风险级别 ⭐
    "description": "CSV Path中的patient_id与DICOM完全匹配" // 说明
}
```

### 3. 检测结果完整对象
```javascript
{
    "text_entities": [...],      // 文本实体列表
    "image_regions": {           // 影像区域信息
        "roi_mask": {...},
        "image_features": {...}
    },
    "mappings": [...],           // 跨模态匹配列表 ⭐ 核心
    "metrics": {                 // 检测指标
        "total_entities": 7,
        "high_risk_count": 3,
        "mappings_found": 2,
        "f1_score": 0.92,
        "precision": 0.95,
        "recall": 0.89
    },
    "cross_modal_risks": [...]   // 风险评估
}
```

---

## 🔌 扩展保护层接口

### 接口定义
**文件**: `services/privacy_protection_interface.py`

```python
class PrivacyProtectionInterface:
    def request_protection(self, detection_result: Dict) -> Dict:
        """
        将检测结果传递给保护层
        
        下游需要实现的功能：
        1. 策略决策：根据risk_level选择保护方式
        2. 文本加密：对text_entities中的敏感信息加密
        3. DICOM脱敏：删除/加密DICOM header字段
        4. 结果存储：保存处理后的数据
        """
        
        entities_to_protect = []
        dicom_fields_to_protect = []
        
        # 从mappings中提取需要保护的内容
        for mapping in detection_result.get('mappings', []):
            if mapping['risk_level'] in ['critical', 'high']:
                # 标记需要加密的DICOM字段
                dicom_fields_to_protect.append({
                    'field': mapping['dicom_field'],
                    'value': mapping['dicom_value'],
                    'action': 'encrypt'  # 或 'remove'
                })
        
        # 从text_entities中提取需要保护的文本
        for entity in detection_result.get('text_entities', []):
            if entity['type'] in ['NAME', 'PHONE', 'ID', 'ADDRESS']:
                entities_to_protect.append({
                    'type': entity['type'],
                    'text': entity['text'],
                    'row': entity['row_index'],
                    'column': entity['column'],
                    'action': 'encrypt'  # 或 'mask'
                })
        
        return {
            'text_entities': entities_to_protect,
            'dicom_fields': dicom_fields_to_protect,
            'risk_assessment': detection_result.get('metrics', {})
        }
```

### 下游实现示例

```python
# 下游开发者需要实现的类

class ProtectionLayer:
    def __init__(self):
        self.crypto = CryptoProcessor()
        self.policy = PolicyEngine()
    
    def process_detection_result(self, result: Dict):
        """处理检测结果"""
        protection_config = PrivacyProtectionInterface().request_protection(result)
        
        # 1. 加密文本实体
        for entity in protection_config['text_entities']:
            if entity['action'] == 'encrypt':
                encrypted = self.crypto.encrypt(entity['text'])
                # 更新CSV文件
                self.update_csv(entity['row'], entity['column'], encrypted)
        
        # 2. 处理DICOM字段
        for field in protection_config['dicom_fields']:
            if field['action'] == 'encrypt':
                # 加密DICOM字段
                self.crypto.encrypt_dicom_field(field['field'])
            elif field['action'] == 'remove':
                # 删除DICOM字段
                self.remove_dicom_field(field['field'])
        
        # 3. 保存处理结果
        self.save_protected_data()

class CryptoProcessor:
    def encrypt(self, text: str) -> str:
        """实现加密算法 (AES/SM4/FPE等)"""
        pass
    
    def encrypt_dicom_field(self, field_name: str):
        """加密DICOM字段"""
        pass

class PolicyEngine:
    def get_policy(self, entity_type: str, risk_level: str) -> Dict:
        """
        根据实体类型和风险级别返回保护策略
        
        示例策略表:
        ┌─────────────┬──────────┬─────────────┐
        │ Entity Type │ Risk     │ Action      │
        ├─────────────┼──────────┼─────────────┤
        │ NAME        │ critical │ FPE encrypt │
        │ PHONE       │ high     │ AES encrypt │
        │ AGE         │ medium   │ Mask        │
        │ SEX         │ low      │ Keep        │
        └─────────────┴──────────┴─────────────┘
        """
        policies = {
            ('NAME', 'critical'): {'action': 'fpe_encrypt'},
            ('PHONE', 'high'): {'action': 'aes_encrypt'},
            ('AGE', 'medium'): {'action': 'mask'},
            ('SEX', 'low'): {'action': 'keep'}
        }
        return policies.get((entity_type, risk_level), {'action': 'remove'})
```

---

## 🧪 测试用例

### 1. 单元测试

**测试NER服务**:
```python
# test_ner.py
from services.ner_service import NERService

def test_ner_detection():
    ner = NERService()
    text = "患者张三，男，35岁，电话13812345678"
    entities = ner.detect_from_text(text)
    
    assert len(entities) >= 3
    assert any(e['type'] == 'NAME' for e in entities)
    assert any(e['type'] == 'AGE' for e in entities)
    assert any(e['type'] == 'PHONE' for e in entities)
```

**测试跨模态匹配**:
```python
# test_crossmodal.py
from services.crossmodal_service import CrossModalAttentionService

def test_patient_id_matching():
    svc = CrossModalAttentionService()
    
    entities = [
        {
            'type': 'PATH',
            'text': 'train/patient00826/study1/view1.jpg',
            'column': 'Path',
            'row_index': 0
        }
    ]
    
    dicom_metadata = {
        'patient_id': 'patient00826'
    }
    
    mappings = svc._match_text_dicom_entities(entities, dicom_metadata)
    
    assert len(mappings) == 1
    assert mappings[0]['match_type'] == 'patient_id_exact_match'
    assert mappings[0]['confidence'] == 1.0
```

### 2. 集成测试

```python
# test_integration.py
import requests

def test_full_workflow():
    base_url = "http://localhost:5000"
    
    # 1. 上传CSV
    with open('test_data.csv', 'rb') as f:
        resp = requests.post(f'{base_url}/api/upload_csv', 
                            files={'csv_file': f})
        csv_id = resp.json()['file_id']
    
    # 2. 上传DICOM
    with open('test_image.dcm', 'rb') as f:
        resp = requests.post(f'{base_url}/api/ingest',
                            files={'dicom_file': f})
        dicom_id = resp.json()['file_id']
    
    # 3. 检测
    resp = requests.post(f'{base_url}/api/detect',
                        json={'csv_id': csv_id, 'dicom_id': dicom_id})
    result = resp.json()
    
    # 4. 验证结果
    assert 'text_entities' in result
    assert 'mappings' in result
    assert result['metrics']['f1_score'] >= 0.88
```

---

## 🐛 常见问题排查

### 1. CSV检测不到实体
**症状**: `text_entities` 为空或数量不对

**排查步骤**:
```python
# 在 crossmodal_service.py 中添加调试
print(f"CSV列名: {df.columns.tolist()}")
print(f"CSV行数: {len(df)}")
print(f"第一行数据: {df.iloc[0].to_dict()}")
```

**常见原因**:
- ❌ CSV列名不匹配（如用了小写`name`而不是`Name`）
- ❌ CSV为空或格式错误
- ❌ 列值为空（`NaN`）

**解决方案**:
```python
# 修改 sensitive_cols 映射
sensitive_cols = {
    'Path': 'PATH',
    'Name': 'NAME',  # 确保大小写一致
    'name': 'NAME',  # 兼容小写
    # ...
}
```

### 2. 跨模态匹配失败
**症状**: `mappings` 为空

**排查步骤**:
```python
# 在 _match_text_dicom_entities 中添加
print(f"Entity column: {entity.get('column')}")
print(f"Entity text: {entity_text}")
print(f"DICOM patient_id: {dicom_metadata.get('patient_id')}")
```

**常见原因**:
- ❌ Path格式不匹配（正则无法提取patient_id）
- ❌ DICOM未正确加载，metadata为空
- ❌ patient_id格式不一致

**解决方案**:
```python
# 调整正则表达式
# 原: r'patient(\d+)'
# 改: r'patient[_]?(\d+)'  # 兼容 patient_00826
```

### 3. DICOM读取失败
**症状**: 控制台报错 `pydicom.errors.InvalidDicomError`

**原因**: 文件不是有效的DICOM格式

**解决方案**:
```python
# 在 roi_service.py 中添加验证
def process_dicom(self, dicom_path: Path, try_burnedin: bool = True):
    try:
        ds = pydicom.dcmread(str(dicom_path), force=True)
    except Exception as e:
        print(f"DICOM读取失败: {e}")
        return None
```

---

## 📈 性能优化建议

### 1. 批量处理优化
```python
# 使用多进程
from multiprocessing import Pool

def process_batch_parallel(csv_files, dicom_files):
    with Pool(processes=4) as pool:
        results = pool.starmap(
            process_single_pair,
            zip(csv_files, dicom_files)
        )
    return results
```

### 2. 缓存机制
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_dicom_load(dicom_path: str):
    """缓存DICOM加载结果"""
    return pydicom.dcmread(dicom_path)
```

### 3. 数据库存储
```python
# 使用SQLite存储检测结果
import sqlite3

class ResultStore:
    def save_result(self, file_id: str, result: Dict):
        conn = sqlite3.connect('results.db')
        conn.execute(
            "INSERT INTO results VALUES (?, ?)",
            (file_id, json.dumps(result))
        )
        conn.commit()
```

---

## 🚀 部署检查清单

### 生产环境准备
- [ ] 使用 `gunicorn` 或 `uwsgi` 替代 Flask 开发服务器
- [ ] 配置 Nginx 反向代理
- [ ] 设置环境变量（不要硬编码路径）
- [ ] 配置日志轮转
- [ ] 添加监控和告警
- [ ] 设置文件上传大小限制
- [ ] 配置CORS（如果需要跨域）
- [ ] 启用HTTPS

### 安全检查
- [ ] 验证用户上传的文件类型
- [ ] 限制文件大小
- [ ] 添加请求频率限制
- [ ] 清理临时文件
- [ ] 不要在日志中输出敏感信息
- [ ] 使用安全的随机数生成器

---

## 📝 代码规范

### Python代码风格
```python
# 遵循 PEP 8
# 使用类型提示
def process_csv(csv_path: str, encoding: str = 'utf-8') -> pd.DataFrame:
    """
    处理CSV文件
    
    Args:
        csv_path: CSV文件路径
        encoding: 文件编码，默认utf-8
        
    Returns:
        pd.DataFrame: 处理后的数据框
        
    Raises:
        FileNotFoundError: 文件不存在
    """
    pass

# 使用有意义的变量名
patient_id = extract_id(text)  # ✅
pid = get_id(t)  # ❌
```

### 提交规范
```bash
# 使用语义化提交消息
git commit -m "feat: 添加patient_id跨模态匹配功能"
git commit -m "fix: 修复CSV列名大小写敏感问题"
git commit -m "docs: 更新API文档"
git commit -m "refactor: 重构NER服务代码结构"
```

---

## 📞 技术支持

### 问题反馈
- 提交 Issue 到仓库
- 附上错误日志和复现步骤
- 说明环境信息（Python版本、OS等）

### 贡献代码
1. Fork 仓库
2. 创建特性分支 `git checkout -b feature/your-feature`
3. 提交更改 `git commit -am 'Add some feature'`
4. 推送分支 `git push origin feature/your-feature`
5. 创建 Pull Request

---

**最后更新**: 2025-10-23  
**文档版本**: v1.0

