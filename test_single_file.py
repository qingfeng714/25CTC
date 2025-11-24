#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单文件端到端性能测试
使用系统API测试单个文件的完整处理时间
"""

import time
import json
import sys
import requests
from pathlib import Path

BASE_URL = "http://localhost:5000"

def test_single_file(csv_file, dicom_file):
    """
    测试单文件处理性能
    
    Args:
        csv_file: CSV文件路径
        dicom_file: DICOM文件路径
    """
    print("=" * 80)
    print("单文件端到端性能测试")
    print("=" * 80)
    
    # 提取文件名用于报告
    csv_filename = Path(csv_file).name
    dicom_filename = Path(dicom_file).name
    
    print(f"\nCSV: {csv_filename}")
    print(f"DICOM: {dicom_filename}\n")
    
    total_start = time.time()
    
    try:
        # ========== 步骤1: 上传CSV ==========
        print("-" * 80)
        print("[步骤 1/5] 上传CSV...")
        step1_start = time.time()
        
        with open(csv_file, 'rb') as f:
            files = {'csv_file': f}
            response = requests.post(f"{BASE_URL}/api/upload_csv", files=files)
            response.raise_for_status()
            csv_data = response.json()
        
        csv_path = csv_data['csv_path']
        step1_time = time.time() - step1_start
        print(f"  [OK] CSV上传完成: {csv_path}")
        print(f"  耗时: {step1_time:.3f}秒\n")
        
        # ========== 步骤2: 上传DICOM ==========
        print("-" * 80)
        print("[步骤 2/5] 上传DICOM...")
        step2_start = time.time()
        
        with open(dicom_file, 'rb') as f:
            files = {'dicom_files': f}
            response = requests.post(f"{BASE_URL}/api/batch_upload_dicom", files=files)
            response.raise_for_status()
            dicom_data = response.json()
        
        metadata_list = dicom_data['metadata_list']
        step2_time = time.time() - step2_start
        print(f"  [OK] DICOM上传完成")
        print(f"  耗时: {step2_time:.3f}秒\n")
        
        # ========== 步骤3: 检测匹配 ==========
        print("-" * 80)
        print("[步骤 3/5] 跨模态检测...")
        step3_start = time.time()
        
        payload = {
            "csv_path": csv_path,
            "dicom_metadata_list": metadata_list
        }
        response = requests.post(f"{BASE_URL}/api/batch_detect", json=payload)
        response.raise_for_status()
        detection_result = response.json()
        
        step3_time = time.time() - step3_start
        total_patients = detection_result.get('total_patients', 0)
        matched = detection_result.get('matched', 0)
        
        print(f"  [OK] 检测完成")
        print(f"    - 患者数: {total_patients}")
        print(f"    - 匹配数: {matched}")
        print(f"  耗时: {step3_time:.3f}秒\n")
        
        # ========== 步骤4: 加密保护 ==========
        print("-" * 80)
        print("[步骤 4/5] 加密保护...")
        step4_start = time.time()
        
        batch_id = f"single_{int(time.time() * 1000)}"
        payload = {
            "detection_result": detection_result,
            "batch_id": batch_id
        }
        response = requests.post(f"{BASE_URL}/api/protect_execute", json=payload)
        response.raise_for_status()
        protect_result = response.json()
        
        step4_time = time.time() - step4_start
        protected_count = protect_result.get('protected_count', 0)
        
        print(f"  [OK] 加密完成")
        print(f"    - 保护文件数: {protected_count}")
        print(f"  耗时: {step4_time:.3f}秒\n")
        
        # ========== 步骤5: 存储入库 ==========
        print("-" * 80)
        print("[步骤 5/5] 存储入库...")
        step5_start = time.time()
        
        payload = {
            "batch_id": batch_id
        }
        response = requests.post(f"{BASE_URL}/api/storage/ingest", json=payload)
        response.raise_for_status()
        storage_result = response.json()
        
        step5_time = time.time() - step5_start
        ingested = storage_result.get('ingested', 0)
        
        print(f"  [OK] 入库完成")
        print(f"    - 入库对象数: {ingested}")
        print(f"  耗时: {step5_time:.3f}秒\n")
        
        # ========== 总计 ==========
        total_time = time.time() - total_start
        
        # 核心处理时间（排除上传）
        core_time = step3_time + step4_time + step5_time
        
        print("=" * 80)
        print("单文件性能报告")
        print("=" * 80)
        
        print(f"\n数据统计:")
        print(f"  患者数:           {total_patients}")
        print(f"  匹配数:           {matched}")
        print(f"  加密文件数:       {protected_count}")
        print(f"  入库对象数:       {ingested}")
        
        print(f"\n时间分析:")
        print(f"  步骤1 - CSV上传:       {step1_time:.3f}秒 ({step1_time/total_time*100:.1f}%)")
        print(f"  步骤2 - DICOM上传:     {step2_time:.3f}秒 ({step2_time/total_time*100:.1f}%)")
        print(f"  步骤3 - 检测匹配:      {step3_time:.3f}秒 ({step3_time/total_time*100:.1f}%)")
        print(f"  步骤4 - 加密保护:      {step4_time:.3f}秒 ({step4_time/total_time*100:.1f}%)")
        print(f"  步骤5 - 存储入库:      {step5_time:.3f}秒 ({step5_time/total_time*100:.1f}%)")
        print(f"  ─────────────────────────────")
        print(f"  完整流程总时间:        {total_time:.3f}秒")
        
        print(f"\n核心处理时间（检测+加密+存储）: {core_time:.3f}秒")
        
        if total_patients > 0:
            avg_time = core_time / total_patients
            print(f"平均处理速度:                   {avg_time:.3f}秒/患者")
            print(f"性能要求:                       < 2.0秒/患者")
            
            if avg_time < 2.0:
                print(f"测试结果:                       [PASS] 性能达标")
                pass_status = True
            else:
                print(f"测试结果:                       [FAIL] 性能不达标")
                pass_status = False
        else:
            avg_time = 0
            pass_status = False
        
        print("=" * 80)
        
        # 保存结果（使用相对路径）
        output_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_type': 'single_file_performance',
            'input': {
                'csv_file': f"data/{csv_filename}",
                'dicom_file': f"data/{dicom_filename}"
            },
            'data_stats': {
                'patients': total_patients,
                'matched': matched,
                'protected': protected_count,
                'ingested': ingested
            },
            'timing': {
                'step1_csv_upload': round(step1_time, 3),
                'step2_dicom_upload': round(step2_time, 3),
                'step3_detection': round(step3_time, 3),
                'step4_protection': round(step4_time, 3),
                'step5_storage': round(step5_time, 3),
                'total_pipeline': round(total_time, 3),
                'core_processing': round(core_time, 3)
            },
            'performance': {
                'avg_time_per_patient': round(avg_time, 3),
                'speed_requirement': 2.0,
                'pass': pass_status
            },
            'batch_id': batch_id
        }
        
        output_file = 'single_file_performance.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n详细结果已保存: {output_file}\n")
        
        return output_data
        
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] API请求失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应内容: {e.response.text}")
        return None
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("\n用法: python test_single_file.py <csv文件> <dicom文件>")
        print("\n示例:")
        print('  python test_single_file.py data.csv image.dcm')
        print('  python test_single_file.py ./data/patient.csv ./data/image.dcm')
        print("\n注意: 请确保Flask服务正在运行 (python app.py)")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    dicom_file = sys.argv[2]
    
    # 验证文件存在
    if not Path(csv_file).exists():
        print(f"[ERROR] CSV文件不存在: {csv_file}")
        sys.exit(1)
    
    if not Path(dicom_file).exists():
        print(f"[ERROR] DICOM文件不存在: {dicom_file}")
        sys.exit(1)
    
    # 检查服务是否运行
    try:
        response = requests.get(f"{BASE_URL}/api/key_info", timeout=2)
        print("[OK] Flask服务运行正常\n")
    except:
        print("[ERROR] Flask服务未运行！请先启动: python app.py")
        sys.exit(1)
    
    # 运行测试
    result = test_single_file(csv_file, dicom_file)
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)
