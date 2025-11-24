import pydicom
import numpy as np
import torch
try:
    import cv2
    _HAS_CV2 = True
except Exception:
    cv2 = None
    _HAS_CV2 = False
from typing import Optional, Tuple, Dict, List
from pathlib import Path
from dataclasses import dataclass
from pydicom.errors import InvalidDicomError
from PIL import Image

# PHI标签定义
PHI_TAGS = [
    ("PatientName",        (0x0010,0x0010)),
    ("PatientID",          (0x0010,0x0020)),
    ("PatientBirthDate",   (0x0010,0x0030)),
    ("PatientSex",         (0x0010,0x0040)),
    ("PatientAge",         (0x0010,0x1010)),
    ("AccessionNumber",    (0x0008,0x0050)),  # 检查号（由RIS系统生成）
    ("StudyID",            (0x0020,0x0010)),  # 检查ID（短标识符）
    ("StudyInstanceUID",   (0x0020,0x000D)),  # 检查实例UID（唯一标识符）
    ("SeriesInstanceUID",  (0x0020,0x000E)),
    ("SOPInstanceUID",     (0x0008,0x0018)),
    ("StudyDate",          (0x0008,0x0020)),
    ("StudyTime",          (0x0008,0x0030)),
    ("InstitutionName",    (0x0008,0x0080)),
]

@dataclass
class DicomProcessingResult:
    dicom_path: str
    pixel_array: np.ndarray
    normalized_tensor: torch.Tensor
    metadata: Dict[str, str]
    roi_mask: Optional[np.ndarray] = None
    roi_boxes: Optional[List[Tuple[int,int,int,int]]] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    accession: Optional[str] = None
    study_date: Optional[str] = None
    study_id: Optional[str] = None  # 检查ID (0020,0010)
    study_instance_uid: Optional[str] = None  # Study Instance UID (0020,000D)
    institution: Optional[str] = None
    patient_sex: Optional[str] = None
    patient_age: Optional[str] = None
    burned_in_annotation: Optional[str] = None
    roi_type: str = "header_only"
    image_size: Optional[Tuple[int,int]] = None
    # 新增：ROI文本内容和敏感信息
    roi_texts: Optional[List[Dict]] = None  # 每个ROI区域的文本内容 [{"box": (x,y,w,h), "text": "...", "source": "ocr|annotation"}]
    roi_names: Optional[List[str]] = None  # ROI名称列表（从RTSS等提取）
    roi_descriptions: Optional[List[str]] = None  # ROI描述列表
    roi_phi_entities: Optional[List[Dict]] = None  # 从ROI文本中提取的敏感信息

class DicomProcessor:
    def __init__(self, device: str = 'cpu'):
        self.device = device
        
    def process_dicom(self, dicom_path: Path, try_burnedin: bool = False) -> Optional[DicomProcessingResult]:
        """
        处理单个DICOM文件，提取像素数据、元数据和ROI信息
        ROI信息可能来自：
        1. DICOM标注部分（如RT Structure Set, Segmentation等）
        2. 烧录文本区域（burned-in annotations）
        3. Header中的ROI标识符
        """
        try:
            ds = pydicom.dcmread(str(dicom_path), force=True)
            pixel_array = self._get_pixel_array(ds)
            
            # 提取header信息
            header = self._extract_header_info(ds)
            
            # 尝试从DICOM标注部分提取ROI信息
            roi_from_annotations = self._extract_roi_from_annotations(ds, pixel_array)
            
            # 检测烧录文本区域（如果启用）
            roi_mask, roi_boxes = self._detect_roi_regions(pixel_array, try_burnedin)
            
            # 如果从标注中提取到了ROI，优先使用标注ROI
            roi_names = []
            roi_descriptions = []
            if roi_from_annotations['roi_mask'] is not None:
                roi_mask = roi_from_annotations['roi_mask']
                roi_boxes = roi_from_annotations['roi_boxes']
                roi_type = roi_from_annotations['roi_type']
                # 提取ROI名称和描述
                if 'roi_names' in roi_from_annotations:
                    roi_names = roi_from_annotations['roi_names']
                if 'roi_descriptions' in roi_from_annotations:
                    roi_descriptions = roi_from_annotations['roi_descriptions']
                print(f"[INFO] 从DICOM标注中提取到ROI: {roi_type}, 区域数: {len(roi_boxes)}")
            elif roi_mask is not None and roi_mask.any():
                roi_type = "burned_in"
                print(f"[INFO] 检测到烧录文本ROI区域: {len(roi_boxes)} 个区域")
            else:
                roi_type = "header_only"
                print(f"[INFO] 未检测到ROI区域（仅提取header信息）。可能原因：1) DICOM文件不包含ROI标注；2) 未检测到烧录文本；3) OpenCV未安装")
            
            # 提取ROI区域中的文本内容（OCR）
            roi_texts = []
            if roi_boxes and len(roi_boxes) > 0:
                roi_texts = self._extract_text_from_roi_regions(pixel_array, roi_boxes)
                print(f"[INFO] 从ROI区域中提取了 {len(roi_texts)} 个文本区域")
            
            # 对ROI文本进行敏感信息检测
            roi_phi_entities = []
            if roi_texts:
                from services.ner_service import NERService
                ner_service = NERService()
                for roi_text_info in roi_texts:
                    text = roi_text_info.get('text', '')
                    if text:
                        entities = ner_service.detect_from_text(text)
                        for entity in entities:
                            entity['source'] = 'dicom_roi'
                            entity['roi_box'] = roi_text_info.get('box')
                            entity['roi_text_source'] = roi_text_info.get('source', 'ocr')
                        roi_phi_entities.extend(entities)
                print(f"[INFO] 从ROI文本中检测到 {len(roi_phi_entities)} 个敏感实体")
            
            return DicomProcessingResult(
                dicom_path=str(dicom_path),
                pixel_array=pixel_array,
                normalized_tensor=self._normalize_to_tensor(pixel_array),
                metadata=header,
                roi_mask=roi_mask,
                roi_boxes=roi_boxes,
                patient_id=header.get("PatientID"),
                patient_name=header.get("PatientName"),
                accession=header.get("AccessionNumber"),
                study_date=header.get("StudyDate"),
                study_id=header.get("StudyID"),  # 检查ID (0020,0010)
                study_instance_uid=header.get("StudyInstanceUID"),  # Study Instance UID (0020,000D)
                institution=header.get("InstitutionName"),
                patient_sex=header.get("PatientSex"),
                patient_age=header.get("PatientAge"),
                burned_in_annotation=header.get("BurnedInAnnotation"),
                roi_type=roi_type,
                image_size=pixel_array.shape[:2] if len(pixel_array.shape) >= 2 else None,
                roi_texts=roi_texts,
                roi_names=roi_names if roi_names else None,
                roi_descriptions=roi_descriptions if roi_descriptions else None,
                roi_phi_entities=roi_phi_entities if roi_phi_entities else None
            )
        except Exception as e:
            print(f"Error processing {dicom_path}: {str(e)}")
            return None
    
    def _get_pixel_array(self, ds: pydicom.Dataset) -> np.ndarray:
        """提取并标准化像素数据"""
        array = ds.pixel_array.astype(np.float32)
        return (array - array.min()) / (array.max() - array.min() + 1e-6)
    
    def _extract_header_info(self, ds: pydicom.Dataset) -> Dict[str, str]:
        """提取DICOM header中的PHI信息"""
        header = {}
        for name, tag in PHI_TAGS:
            try:
                value = ds.get(tag, None)
                if value is not None:
                    if hasattr(value, 'value'):
                        header[name] = str(value.value)
                    else:
                        header[name] = str(value)
                else:
                    header[name] = None
            except Exception:
                header[name] = None
        return header
    
    def _extract_roi_from_annotations(self, ds: pydicom.Dataset, pixel_array: np.ndarray) -> Dict:
        """
        从DICOM标注部分提取ROI信息
        支持多种标注格式：
        1. RT Structure Set (RTSS) - 放射治疗结构集
        2. Segmentation - DICOM分割对象
        3. Presentation State - 显示状态中的ROI
        4. Key Object Selection - 关键对象选择
        """
        result = {
            'roi_mask': None,
            'roi_boxes': [],
            'roi_type': 'none'
        }
        
        try:
            # 方法1: 检查RT Structure Set (RTSS)
            # RT Structure Set通常包含ROI轮廓信息
            if hasattr(ds, 'SOPClassUID'):
                sop_class = str(ds.SOPClassUID)
                if '1.2.840.10008.5.1.4.1.1.481.3' in sop_class:  # RT Structure Set Storage
                    roi_mask, roi_boxes, roi_names, roi_descriptions = self._extract_roi_from_rtss(ds, pixel_array)
                    if roi_mask is not None:
                        result['roi_mask'] = roi_mask
                        result['roi_boxes'] = roi_boxes
                        result['roi_type'] = 'rt_structure_set'
                        result['roi_names'] = roi_names
                        result['roi_descriptions'] = roi_descriptions
                        return result
            
            # 方法2: 检查Segmentation对象
            if hasattr(ds, 'SegmentationType'):
                roi_mask, roi_boxes = self._extract_roi_from_segmentation(ds, pixel_array)
                if roi_mask is not None:
                    result['roi_mask'] = roi_mask
                    result['roi_boxes'] = roi_boxes
                    result['roi_type'] = 'segmentation'
                    return result
            
            # 方法3: 检查Presentation State中的ROI
            if hasattr(ds, 'GraphicAnnotationSequence'):
                roi_mask, roi_boxes = self._extract_roi_from_presentation_state(ds, pixel_array)
                if roi_mask is not None:
                    result['roi_mask'] = roi_mask
                    result['roi_boxes'] = roi_boxes
                    result['roi_type'] = 'presentation_state'
                    return result
            
            # 方法4: 检查Key Object Selection
            if hasattr(ds, 'KeyObjectSelectionSequence'):
                # Key Object Selection通常只是标记，不包含实际ROI数据
                result['roi_type'] = 'key_object_selection'
                return result
            
        except Exception as e:
            print(f"Warning: Failed to extract ROI from annotations: {e}")
        
        return result
    
    def _extract_roi_from_rtss(self, ds: pydicom.Dataset, pixel_array: np.ndarray) -> Tuple[Optional[np.ndarray], List, List[str], List[str]]:
        """从RT Structure Set提取ROI，返回(roi_mask, roi_boxes, roi_names, roi_descriptions)"""
        try:
            if not hasattr(ds, 'StructureSetROISequence'):
                return None, [], [], []
            
            # RTSS包含ROI序列，每个ROI有轮廓点
            roi_mask = np.zeros(pixel_array.shape[:2], dtype=np.uint8)
            roi_boxes = []
            roi_names = []
            roi_descriptions = []
            
            for roi_sequence in ds.StructureSetROISequence:
                roi_number = getattr(roi_sequence, 'ROINumber', None)
                roi_name = getattr(roi_sequence, 'ROIName', 'Unknown')
                roi_names.append(roi_name)
                
                # 提取ROI描述（如果有）
                roi_description = getattr(roi_sequence, 'ROIDescription', '')
                if roi_description:
                    roi_descriptions.append(str(roi_description))
                
                # 查找对应的ROI轮廓
                if hasattr(ds, 'ROIContourSequence'):
                    for contour_seq in ds.ROIContourSequence:
                        if getattr(contour_seq, 'ReferencedROINumber', None) == roi_number:
                            if hasattr(contour_seq, 'ContourSequence'):
                                # 提取轮廓点并生成掩码
                                for contour in contour_seq.ContourSequence:
                                    if hasattr(contour, 'ContourData'):
                                        # ContourData包含(x,y,z)坐标对
                                        contour_data = contour.ContourData
                                        if len(contour_data) >= 6:  # 至少需要2个点
                                            # 简化处理：提取2D轮廓（忽略Z坐标）
                                            points = []
                                            for i in range(0, len(contour_data), 3):
                                                if i + 1 < len(contour_data):
                                                    points.append((int(contour_data[i]), int(contour_data[i+1])))
                                            
                                            if len(points) >= 3:
                                                # 使用OpenCV填充多边形
                                                if _HAS_CV2:
                                                    import cv2
                                                    pts = np.array(points, dtype=np.int32)
                                                    cv2.fillPoly(roi_mask, [pts], 255)
                                                    
                                                    # 计算边界框
                                                    x_coords = [p[0] for p in points]
                                                    y_coords = [p[1] for p in points]
                                                    x_min, x_max = min(x_coords), max(x_coords)
                                                    y_min, y_max = min(y_coords), max(y_coords)
                                                    roi_boxes.append((x_min, y_min, x_max - x_min, y_max - y_min))
            
            if roi_mask.any():
                return roi_mask, roi_boxes
        except Exception as e:
            print(f"Warning: Failed to extract ROI from RTSS: {e}")
        
        return None, []
    
    def _extract_roi_from_segmentation(self, ds: pydicom.Dataset, pixel_array: np.ndarray) -> Tuple[Optional[np.ndarray], List]:
        """从Segmentation对象提取ROI"""
        try:
            if not hasattr(ds, 'SegmentSequence'):
                return None, []
            
            roi_mask = np.zeros(pixel_array.shape[:2], dtype=np.uint8)
            roi_boxes = []
            
            for segment in ds.SegmentSequence:
                segment_number = getattr(segment, 'SegmentNumber', None)
                segment_label = getattr(segment, 'SegmentLabel', 'Unknown')
                
                # 查找对应的像素数据
                if hasattr(ds, 'PixelData'):
                    # Segmentation的像素数据通常是掩码
                    # 这里简化处理，实际需要根据SegmentationType解析
                    pass
            
            if roi_mask.any():
                return roi_mask, roi_boxes
        except Exception as e:
            print(f"Warning: Failed to extract ROI from Segmentation: {e}")
        
        return None, []
    
    def _extract_roi_from_presentation_state(self, ds: pydicom.Dataset, pixel_array: np.ndarray) -> Tuple[Optional[np.ndarray], List]:
        """从Presentation State提取ROI"""
        try:
            if not hasattr(ds, 'GraphicAnnotationSequence'):
                return None, []
            
            roi_mask = np.zeros(pixel_array.shape[:2], dtype=np.uint8)
            roi_boxes = []
            
            for annotation in ds.GraphicAnnotationSequence:
                if hasattr(annotation, 'GraphicObjectSequence'):
                    for graphic_obj in annotation.GraphicObjectSequence:
                        graphic_type = getattr(graphic_obj, 'GraphicType', '')
                        if graphic_type in ['POLYLINE', 'POLYGON', 'ELLIPSE', 'RECTANGLE']:
                            # 提取图形对象的坐标
                            if hasattr(graphic_obj, 'GraphicData'):
                                graphic_data = graphic_obj.GraphicData
                                if len(graphic_data) >= 4:
                                    # 简化处理：提取边界框
                                    x_coords = [graphic_data[i] for i in range(0, len(graphic_data), 2)]
                                    y_coords = [graphic_data[i+1] for i in range(0, len(graphic_data), 2)]
                                    if x_coords and y_coords:
                                        x_min, x_max = int(min(x_coords)), int(max(x_coords))
                                        y_min, y_max = int(min(y_coords)), int(max(y_coords))
                                        roi_boxes.append((x_min, y_min, x_max - x_min, y_max - y_min))
                                        if _HAS_CV2:
                                            import cv2
                                            cv2.rectangle(roi_mask, (x_min, y_min), (x_max, y_max), 255, -1)
            
            if roi_mask.any():
                return roi_mask, roi_boxes
        except Exception as e:
            print(f"Warning: Failed to extract ROI from Presentation State: {e}")
        
        return None, []
    
    def _normalize_to_tensor(self, pixel_array: np.ndarray) -> torch.Tensor:
        """将像素数组转换为标准化的tensor"""
        # 归一化到0-1范围
        normalized = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min() + 1e-6)
        # 转换为tensor并添加batch和channel维度
        tensor = torch.FloatTensor(normalized).unsqueeze(0).unsqueeze(0)
        return tensor.to(self.device)
    
    def _detect_roi_regions(self, pixel_array: np.ndarray, try_burnedin: bool = False) -> Tuple[Optional[np.ndarray], Optional[List[Tuple[int,int,int,int]]]]:
        """检测ROI区域"""
        if not try_burnedin:
            return None, []

        if not _HAS_CV2:
            # OpenCV not available: skip burned-in text detection
            return None, []

        try:
            # 转换为8位灰度图
            gray_u8 = self._normalize_to_u8(pixel_array)
            roi_boxes = self._detect_burnedin_text(gray_u8)

            # 生成ROI掩码
            roi_mask = np.zeros_like(gray_u8, dtype=np.uint8)
            for (x, y, w, h) in roi_boxes:
                roi_mask[y:y+h, x:x+w] = 255

            return roi_mask, roi_boxes
        except Exception as e:
            print(f"ROI detection failed: {e}")
            return None, []
    
    def _normalize_to_u8(self, arr: np.ndarray) -> np.ndarray:
        """归一化到8位图像"""
        arr = arr.astype(np.float32)
        a, b = np.percentile(arr, [0.5, 99.5])
        if b <= a:
            b = arr.max()
            a = arr.min()
        arr = np.clip((arr - a) / (b - a + 1e-6), 0, 1)
        return (arr * 255).astype(np.uint8)
    
    def _detect_burnedin_text(self, gray_u8: np.ndarray) -> List[Tuple[int,int,int,int]]:
        """检测烧录文本区域"""
        h, w = gray_u8.shape
        
        # 使用CLAHE增强对比度
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        eq = clahe.apply(gray_u8)
        
        # Otsu阈值化
        _, otsu = cv2.threshold(eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bin_img = 255 - otsu
        
        # 形态学操作
        kx = max(3, w // 300)
        ky = max(1, h // 400)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky))
        mor = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=1)
        mor = cv2.medianBlur(mor, 3)
        
        # 连通组件分析
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mor, connectivity=8)
        boxes = []
        
        for i in range(1, n):
            x, y, w0, h0, area = stats[i,0], stats[i,1], stats[i,2], stats[i,3], stats[i,4]
            if area < 40 or w0 < 10 or h0 < 8:
                continue
            aspect = w0 / max(h0, 1)
            if aspect < 1.5 or aspect > 40:
                continue
            boxes.append((int(x), int(y), int(w0), int(h0)))
        
        # 非极大值抑制
        return self._nms(boxes)
    
    def _nms(self, boxes: List[Tuple[int,int,int,int]]) -> List[Tuple[int,int,int,int]]:
        """非极大值抑制"""
        def area(b):
            return b[2] * b[3]
        
        def iou(a, b):
            ax, ay, aw, ah = a
            bx, by, bw, bh = b
            xa1, ya1, xa2, ya2 = ax, ay, ax + aw, ay + ah
            xb1, yb1, xb2, yb2 = bx, by, bx + bw, by + bh
            ix1, iy1 = max(xa1, xb1), max(ya1, yb1)
            ix2, iy2 = min(xa2, xb2), min(ya2, yb2)
            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
            inter = iw * ih
            uni = aw * ah + bw * bh - inter
            return inter / uni if uni > 0 else 0
        
        keep = []
        for b in sorted(boxes, key=area, reverse=True):
            if all(iou(b, k) < 0.3 for k in keep):
                keep.append(b)
        
        return keep[:20]  # 最多保留20个区域
    
    def _extract_text_from_roi_regions(self, pixel_array: np.ndarray, roi_boxes: List[Tuple[int,int,int,int]]) -> List[Dict]:
        """
        从ROI区域中提取文本内容（使用OCR）
        :param pixel_array: 像素数组
        :param roi_boxes: ROI边界框列表 [(x, y, w, h), ...]
        :return: [{"box": (x,y,w,h), "text": "...", "source": "ocr|annotation"}, ...]
        """
        roi_texts = []
        
        if not roi_boxes or len(roi_boxes) == 0:
            return roi_texts
        
        # 转换为8位灰度图
        gray_u8 = self._normalize_to_u8(pixel_array)
        
        # 尝试使用OCR提取文本
        for box in roi_boxes:
            x, y, w, h = box
            # 确保坐标在图像范围内
            x = max(0, min(x, gray_u8.shape[1] - 1))
            y = max(0, min(y, gray_u8.shape[0] - 1))
            w = min(w, gray_u8.shape[1] - x)
            h = min(h, gray_u8.shape[0] - y)
            
            if w <= 0 or h <= 0:
                continue
            
            # 提取ROI区域
            roi_region = gray_u8[y:y+h, x:x+w]
            
            # 尝试使用Tesseract OCR
            text = None
            if _HAS_TESSERACT:
                try:
                    # 使用PIL Image进行OCR
                    roi_image = Image.fromarray(roi_region)
                    text = pytesseract.image_to_string(roi_image, lang='chi_sim+eng', config='--psm 6')
                    text = text.strip()
                except Exception as e:
                    print(f"[WARN] Tesseract OCR失败: {e}")
            
            # 如果Tesseract失败，尝试使用EasyOCR
            if (not text or len(text.strip()) == 0) and _HAS_EASYOCR:
                try:
                    if not hasattr(self, '_easyocr_reader'):
                        self._easyocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                    results = self._easyocr_reader.readtext(roi_region)
                    if results:
                        text = ' '.join([result[1] for result in results])
                except Exception as e:
                    print(f"[WARN] EasyOCR失败: {e}")
            
            if text and len(text.strip()) > 0:
                roi_texts.append({
                    'box': box,
                    'text': text.strip(),
                    'source': 'ocr'
                })
        
        return roi_texts

class ROISegmenter:
    """ROI分割服务"""
    def __init__(self):
        self.processor = DicomProcessor()
    
    def segment(self, pixel_array: np.ndarray) -> np.ndarray:
        """分割ROI区域"""
        try:
            _, roi_boxes = self.processor._detect_roi_regions(pixel_array, try_burnedin=True)
            if not roi_boxes:
                return np.zeros_like(pixel_array, dtype=np.uint8)
            
            roi_mask = np.zeros_like(pixel_array, dtype=np.uint8)
            for (x, y, w, h) in roi_boxes:
                roi_mask[y:y+h, x:x+w] = 255
            
            return roi_mask
        except Exception:
            return np.zeros_like(pixel_array, dtype=np.uint8)