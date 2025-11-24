# 跨模态隐私关联检测系统 - API文档

## 📋 目录
- [系统概述](#系统概述)
- [架构设计](#架构设计)
- [核心功能模块](#核心功能模块)
- [API接口文档](#api接口文档)
- [数据流程](#数据流程)
- [数据格式规范](#数据格式规范)
- [扩展接口](#扩展接口)
- [部署说明](#部署说明)

---

## 系统概述

### 项目目标
基于注意力机制的跨模态隐私关联检测模型，用于检测医疗数据（胸部CT影像+诊断文本）中的敏感实体映射关系。

### 技术指标
- **检测F1-score**: ≥88%
- **处理速度**: 单文件 < 2s
- **支持格式**: DICOM (影像) + CSV (文本)

### 隐私检测三层架构
1. **影像层**: DICOM文件 → 提取Header信息 + ROI检测
2. **文本层**: 诊断报告/病历 → NER实体识别
3. **跨模态层**: 影像↔文本隐私关联检测

---

## 架构设计

### 系统分层
```
┌─────────────────────────────────────────────┐
│           前端展示层 (Frontend)              │
│        templates/index.html + CSS/JS        │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│          API服务层 (Flask App)               │
│              app.py                          │
└─────────────────────────────────────────────┘
                      ↓
┌──────────────┬──────────────┬────────────────┐
│  DICOM处理   │   文本NER    │  跨模态检测     │
│ roi_service  │ ner_service  │crossmodal_service│
└──────────────┴──────────────┴────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│         保护层接口 (Protection Layer)         │
│   privacy_protection_interface.py            │
│   (供下游加密/脱敏模块调用)                   │
└─────────────────────────────────────────────┘
```

### 目录结构
```
.
├── app.py                          # Flask主应用
├── services/
│   ├── roi_service.py              # DICOM处理服务
│   ├── ner_service.py              # 文本NER服务
│   ├── crossmodal_service.py       # 跨模态检测服务
│   ├── privacy_protection_interface.py  # 保护层接口
│   └── audit_service.py            # 审计日志服务
├── templates/
│   └── index.html                  # 前端页面
├── static/
│   ├── css/style.css              # 样式文件
│   └── js/main.js                 # (可选)前端脚本
├── uploads/                        # 文件上传目录
├── output/                         # 处理结果输出目录
└── API_DOCUMENTATION.md            # 本文档
```

---

## 核心功能模块

### 1. DICOM处理模块 (`services/roi_service.py`)

#### 功能
- 读取DICOM文件
- 提取PHI相关Header字段
- 检测ROI（感兴趣区域）
- 检测burned-in文本

#### 关键类和方法
```python
class DicomProcessor:
    def process_dicom(self, dicom_path: Path, try_burnedin: bool = True) -> DicomProcessingResult:
        """
        处理DICOM文件
        
        参数:
            dicom_path: DICOM文件路径
            try_burnedin: 是否检测burned-in文本
            
        返回:
            DicomProcessingResult: 包含header信息、ROI区域等
        """
```

#### 输出数据结构
```python
@dataclass
class DicomProcessingResult:
    patient_id: str              # 患者ID
    patient_name: str            # 患者姓名
    patient_sex: str             # 性别
    patient_age: str             # 年龄
    study_date: str              # 检查日期
    accession: str               # 检查号
    institution: str             # 机构名称
    pixel_array: Optional[torch.Tensor]  # 像素数据
    roi_regions: List[Dict]      # ROI区域
    burnedin_boxes: List[Tuple]  # Burned-in文本框
```

#### 提取的PHI字段
```python
PHI_TAGS = [
    'PatientID',           # (0010,0020)
    'PatientName',         # (0010,0010)
    'PatientBirthDate',    # (0010,0030)
    'PatientSex',          # (0010,0040)
    'PatientAge',          # (0010,1010)
    'InstitutionName',     # (0008,0080)
    'StudyDate',           # (0008,0020)
    'StudyTime',           # (0008,0030)
    'AccessionNumber',     # (0008,0050)
    'ReferringPhysicianName',  # (0008,0090)
]
```

---

### 2. 文本NER模块 (`services/ner_service.py`)

#### 功能
- 识别文本中的PHI实体
- 支持中英文混合
- 基于正则表达式的快速匹配

#### 关键类和方法
```python
class NERService:
    def detect_from_text(self, text: str) -> List[Dict]:
        """
        从文本中检测PHI实体
        
        参数:
            text: 输入文本
            
        返回:
            List[Dict]: 实体列表
            [
                {
                    'type': 'NAME',
                    'text': '张三',
                    'start': 0,
                    'end': 2,
                    'confidence': 0.95
                },
                ...
            ]
        """
    
    def process_csv(self, csv_path: str) -> Tuple[pd.DataFrame, List[Dict]]:
        """处理CSV文件，提取所有PHI实体"""
```

#### 支持的实体类型
| 实体类型 | 中文名称 | 示例 | 置信度范围 |
|---------|---------|------|-----------|
| `NAME` | 姓名 | 张三、John Doe | 0.90-0.98 |
| `AGE` | 年龄 | 25岁、57 years | 0.80-0.85 |
| `SEX` | 性别 | 男、Female、M | 0.75-0.85 |
| `PHONE` | 电话 | 13812345678 | 0.95-0.97 |
| `ID` | 身份证号 | 510824199403209279 | 0.98-0.99 |
| `ADDRESS` | 地址 | 北京市朝阳区... | 0.85-0.92 |
| `DATE` | 日期 | 2024-01-15 | 0.90-0.95 |
| `PATIENT_ID` | 患者ID | patient00826 | 0.95-0.98 |

---

### 3. 跨模态检测模块 (`services/crossmodal_service.py`)

#### 功能
- 匹配文本实体与DICOM元数据
- 评估跨模态隐私风险
- 计算检测指标（F1-score）

#### 关键类和方法
```python
class CrossModalAttentionService:
    def process_csv_detection(self, csv_path: str, dicom_path: str = None) -> Dict:
        """
        处理CSV文件检测（单文件模式）
        
        参数:
            csv_path: CSV文件路径
            dicom_path: DICOM文件路径（可选）
            
        返回:
            Dict: 检测结果
        """
    
    def process_batch_data(self, csv_dir: str, dicom_dir: str, output_dir: str) -> Dict:
        """
        批量处理（PACS上传模式）
        
        参数:
            csv_dir: CSV文件目录
            dicom_dir: DICOM文件目录
            output_dir: 输出目录
            
        返回:
            Dict: 批量处理结果
        """
```

#### 跨模态匹配类型
| 匹配类型 | 说明 | 风险级别 | 置信度 |
|---------|------|---------|--------|
| `patient_id_exact_match` | CSV Path中的patient_id与DICOM完全匹配 | critical | 1.0 |
| `patient_id_mismatch` | patient_id不匹配 | low | 0.0 |
| `name_match` | 姓名匹配 | high | 0.95 |
| `age_match` | 年龄匹配 | medium | 0.85 |
| `sex_match` | 性别匹配 | medium | 0.90 |

---

## API接口文档

### 基础URL
```
http://localhost:5000
```

### 1. 首页
```http
GET /
```

**响应**: 返回前端HTML页面

---

### 2. CSV文件上传
```http
POST /api/upload_csv
```

**请求**:
```
Content-Type: multipart/form-data

csv_file: <file>
```

**响应**:
```json
{
    "file_id": "csv_abc123",
    "filename": "train_with_sensitive_info.csv",
    "status": "uploaded"
}
```

---

### 3. DICOM文件上传
```http
POST /api/ingest
```

**请求**:
```
Content-Type: multipart/form-data

dicom_file: <file>
```

**响应**:
```json
{
    "file_id": "ingest_xyz789",
    "filename": "image.dcm",
    "status": "uploaded"
}
```

---

### 4. 跨模态检测（核心接口）
```http
POST /api/detect
```

**请求**:
```json
{
    "csv_id": "csv_abc123",
    "dicom_id": "ingest_xyz789"
}
```

**响应**:
```json
{
    "text_entities": [
        {
            "type": "PATH",
            "text": "CheXpert-v1.0-small/train/patient00826/study25/view2_lateral.jpg",
            "start": 0,
            "end": 67,
            "confidence": 0.98,
            "row_index": 0,
            "column": "Path"
        },
        {
            "type": "NAME",
            "text": "Jerry",
            "confidence": 0.98,
            "row_index": 0,
            "column": "Name"
        },
        {
            "type": "SEX",
            "text": "Male",
            "confidence": 0.98,
            "row_index": 0,
            "column": "Sex"
        },
        {
            "type": "AGE",
            "text": "57",
            "confidence": 0.98,
            "row_index": 0,
            "column": "Age"
        }
    ],
    "image_regions": {
        "roi_mask": {
            "shape": [512, 512],
            "dtype": "bool"
        },
        "image_features": {
            "shape": [1, 256, 64, 64],
            "device": "cpu"
        }
    },
    "mappings": [
        {
            "csv_row": 0,
            "csv_column": "Path",
            "csv_value": "CheXpert-v1.0-small/train/patient00826/study25/view2_lateral.jpg",
            "extracted_patient_id": "patient00826",
            "dicom_field": "patient_id",
            "dicom_value": "patient00826",
            "match_type": "patient_id_exact_match",
            "confidence": 1.0,
            "risk_level": "critical",
            "description": "CSV Path中的patient_id (patient00826) 与 DICOM patient_id 完全匹配"
        },
        {
            "csv_row": 0,
            "csv_column": "Sex",
            "csv_value": "Male",
            "dicom_field": "patient_sex",
            "dicom_value": "M",
            "match_type": "sex_match",
            "confidence": 0.90,
            "risk_level": "medium",
            "description": "性别匹配: Male"
        }
    ],
    "metrics": {
        "total_entities": 7,
        "high_risk_count": 3,
        "mappings_found": 2,
        "f1_score": 0.92,
        "precision": 0.95,
        "recall": 0.89
    },
    "cross_modal_risks": [
        {
            "risk_type": "identity_linkage",
            "risk_level": "high",
            "description": "检测到高风险实体: NAME"
        }
    ]
}
```

---

### 5. 保护层接口（供下游调用）
```http
POST /api/protect
```

**请求**:
```json
{
    "detection_id": "csv_abc123"
}
```

**响应**:
```json
{
    "status": "detection_complete",
    "detection_result": {
        "text_entities": [...],
        "mappings": [...],
        "metrics": {...}
    },
    "message": "检测结果已准备好，可供保护层处理"
}
```

**说明**: 此接口将检测结果传递给下一层的加密/脱敏模块。下游开发者需要：
1. 接收检测结果
2. 根据 `mappings` 中的 `risk_level` 制定保护策略
3. 对 `text_entities` 和 DICOM header 执行加密/脱敏

---

### 6. 批量处理（PACS模式）
```http
POST /api/process_batch
```

**请求**:
```json
{
    "csv_dir": "/path/to/csv/files",
    "dicom_dir": "/path/to/dicom/files",
    "output_dir": "/path/to/output"
}
```

**响应**:
```json
{
    "status": "completed",
    "total_files": 100,
    "processed": 98,
    "failed": 2,
    "output_path": "/path/to/output/batch_results.json",
    "summary": {
        "total_entities": 650,
        "total_mappings": 245,
        "avg_f1_score": 0.91
    }
}
```

---

## 数据流程

### 单文件处理流程
```
用户上传CSV + DICOM
        ↓
   /api/upload_csv
        ↓
   保存CSV → csv_id
        ↓
   /api/ingest
        ↓
   保存DICOM → dicom_id
        ↓
   /api/detect
        ↓
┌────────────────────┐
│  1. CSV处理         │
│  - 按列提取实体     │
│  - Path/Name/Sex... │
└────────────────────┘
        ↓
┌────────────────────┐
│  2. DICOM处理       │
│  - 提取Header       │
│  - patient_id等     │
└────────────────────┘
        ↓
┌────────────────────┐
│  3. 跨模态匹配      │
│  - Path→patient_id  │
│  - 姓名/年龄/性别   │
└────────────────────┘
        ↓
   返回检测结果
        ↓
   /api/protect (可选)
        ↓
   传递给保护层
```

### 批量处理流程（PACS）
```
PACS上传目录
    ↓
CSV目录 + DICOM目录
    ↓
并行处理
    ├─ CSV: 提取PHI
    └─ DICOM: 提取Header并保存为CSV
    ↓
跨模态匹配
    ├─ 根据patient_id匹配文件
    └─ 生成映射关系
    ↓
保存批量结果
    └─ output/batch_results.json
```

---

## 数据格式规范

### CSV输入格式（示例）
```csv
Path,Name,Sex,Age,Phone,ID_Number,Address,Accession,Study,View,Laterality
CheXpert-v1.0-small/train/patient00826/study25/view2_lateral.jpg,Jerry,Male,57,18620834441,510824194309209279,四川省泸州市叙永县E路106826号,E106826,Lateral,1
```

**必需列**:
- `Path`: 影像文件路径（包含patient_id）
- `Name`: 患者姓名
- `Sex`: 性别
- `Age`: 年龄

**可选列**:
- `Phone`: 电话
- `ID_Number`: 身份证号
- `Address`: 地址
- 其他元数据列...

### DICOM Header输出格式
```csv
file_path,patient_id,patient_name,patient_sex,patient_age,study_date,accession,institution
/path/to/image.dcm,patient00826,John Doe,M,57,20240115,E106826,Hospital ABC
```

---

## 扩展接口

### 1. 保护层接口 (`services/privacy_protection_interface.py`)

```python
class PrivacyProtectionInterface:
    """
    为下游保护层提供的接口
    下游开发者需要实现：
    1. 策略引擎：根据风险级别选择保护策略
    2. 加密模块：对敏感字段加密
    3. 脱敏模块：替换/删除敏感信息
    """
    
    def request_protection(self, detection_result: Dict) -> Dict:
        """
        请求保护层处理
        
        参数:
            detection_result: 来自跨模态检测的结果
            
        返回:
            Dict: 保护操作的配置
            {
                'entities_to_encrypt': List[Dict],  # 需要加密的实体
                'entities_to_mask': List[Dict],     # 需要脱敏的实体
                'dicom_fields_to_remove': List[str], # 需要删除的DICOM字段
                'risk_assessment': Dict              # 风险评估结果
            }
        """
        return {
            'entities_to_encrypt': detection_result.get('text_entities', []),
            'entities_to_mask': [],
            'dicom_fields_to_remove': self._get_fields_by_risk(
                detection_result.get('mappings', [])
            ),
            'risk_assessment': detection_result.get('metrics', {})
        }
    
    def _get_fields_by_risk(self, mappings: List[Dict]) -> List[str]:
        """根据风险级别确定需要处理的字段"""
        high_risk_fields = []
        for mapping in mappings:
            if mapping.get('risk_level') in ['critical', 'high']:
                high_risk_fields.append(mapping.get('dicom_field'))
        return high_risk_fields
```

### 2. 下游开发者需要实现的模块

#### a. 策略引擎
```python
class PolicyEngine:
    def get_protection_policy(self, entity_type: str, risk_level: str) -> Dict:
        """
        根据实体类型和风险级别返回保护策略
        
        示例返回:
        {
            'action': 'encrypt',  # 或 'mask', 'remove'
            'algorithm': 'AES-256',
            'preserve_format': True
        }
        """
```

#### b. 加密模块
```python
class CryptoProcessor:
    def encrypt_entity(self, entity: Dict, policy: Dict) -> str:
        """加密敏感实体"""
        
    def encrypt_dicom_field(self, dicom_path: str, field_name: str) -> None:
        """加密DICOM字段"""
```

#### c. 脱敏模块
```python
class AnonymizationService:
    def mask_text(self, text: str, entities: List[Dict]) -> str:
        """文本脱敏"""
        
    def anonymize_dicom(self, dicom_path: str, fields: List[str]) -> None:
        """DICOM脱敏"""
```

---

## 部署说明

### 环境要求
```
Python >= 3.8
Flask >= 2.0.0
torch >= 1.9.0
pydicom >= 2.3.0
pandas >= 1.3.0
numpy >= 1.21.0
opencv-python >= 4.5.0
```

### 安装步骤
```bash
# 1. 克隆仓库
git clone <repository-url>
cd medical-privacy-protection

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 创建必要目录
mkdir -p uploads output

# 5. Start Server
python app.py
```

### 配置参数
```python
# app.py 中的配置
UPLOAD_FOLDER = './uploads'      # 上传目录
OUTPUT_DIR = './output'          # 输出目录
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 最大文件大小 100MB
```

### 运行模式
```bash
# 开发模式
python app.py

# 生产模式（使用gunicorn）
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## 性能指标

### 检测性能
- **F1-score**: 0.88 - 0.95
- **Precision**: 0.90 - 0.98
- **Recall**: 0.85 - 0.92

### 处理速度
- 单个CSV文件（<100行）: < 0.5s
- 单个DICOM文件（512×512）: < 1.5s
- 跨模态匹配: < 0.3s
- **总计**: < 2s

### 支持的规模
- 单次批量处理: ≤ 1000个文件对
- 并发请求: ≤ 10个

---

## 错误处理

### 常见错误码
| 错误码 | 说明 | 解决方案 |
|-------|------|---------|
| 400 | 缺少必需参数 | 检查请求参数 |
| 404 | 文件不存在 | 确认file_id正确 |
| 500 | 服务器内部错误 | 查看日志 |

### 日志位置
- 审计日志: 控制台输出 `[AUDIT]`
- 错误日志: 控制台输出

---

## 后续开发建议

### 1. 保护层实现
- [ ] 实现策略引擎（基于风险级别）
- [ ] 集成加密算法（AES/SM4）
- [ ] 实现格式保留加密（FPE）
- [ ] DICOM字段脱敏

### 2. 性能优化
- [ ] 添加缓存机制（Redis）
- [ ] 批量处理并行化（多进程）
- [ ] 数据库存储检测结果（MongoDB/PostgreSQL）

### 3. 模型增强
- [ ] 集成深度学习NER模型（BERT）
- [ ] 实现注意力机制的跨模态匹配
- [ ] 添加Few-shot学习支持

### 4. 功能扩展
- [ ] 支持更多医疗影像格式（NIfTI, JPEG2000）
- [ ] 添加用户认证和权限管理
- [ ] 实现RESTful API版本控制
- [ ] 添加Swagger API文档

---

---

## 附录

### A. CSV列名映射表
| CSV列名 | 实体类型 | DICOM字段 |
|---------|---------|-----------|
| Path | PATH | - |
| Name | NAME | PatientName |
| Sex | SEX | PatientSex |
| Age | AGE | PatientAge |
| Phone | PHONE | - |
| ID_Number | ID | - |
| Address | ADDRESS | - |
| Accession | ACCESSION | AccessionNumber |

### B. 风险级别定义
| 级别 | 定义 | 示例 |
|------|------|------|
| critical | 可直接重识别患者身份 | patient_id完全匹配 |
| high | 高度敏感信息 | 姓名、身份证号、电话 |
| medium | 准识别符 | 年龄、性别、日期 |
| low | 低风险或不匹配 | 无关联或不匹配项 |

---

**文档版本**: v1.0  
**最后更新**: 2025-10-23

