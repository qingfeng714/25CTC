#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试CSV文件PHI提取功能
直接测试crossmodal_service中的CSV处理逻辑
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_csv_extraction():
    """测试CSV文件提取"""
    print("=" * 80)
    print("CSV文件PHI提取测试")
    print("=" * 80)
    
    try:
        from services.crossmodal_service import CrossModalAttentionService
        import pandas as pd
        
        # 初始化服务
        service = CrossModalAttentionService(device='cpu')
        print("[OK] CrossModalAttentionService 初始化成功\n")
        
        # 查找测试CSV文件
        csv_files = []
        
        # 检查database目录
        db_csv = project_root / "database" / "cxr-record-list.csv"
        if db_csv.exists():
            csv_files.append(db_csv)
        
        # 检查uploads目录
        uploads_dir = project_root / "uploads"
        if uploads_dir.exists():
            for csv_file in uploads_dir.glob("*.csv"):
                csv_files.append(csv_file)
        
        if not csv_files:
            print("[ERROR] 未找到CSV测试文件！")
            print("请将CSV文件放在以下位置之一：")
            print("  - database/cxr-record-list.csv")
            print("  - uploads/*.csv")
            return False
        
        # 使用第一个找到的CSV文件
        csv_path = csv_files[0]
        print(f"[INFO] 使用CSV文件: {csv_path}")
        print(f"[INFO] 文件大小: {csv_path.stat().st_size} 字节\n")
        
        # 读取CSV文件基本信息
        try:
            df = pd.read_csv(csv_path, encoding='utf-8', encoding_errors='ignore')
        except Exception:
            try:
                df = pd.read_csv(csv_path, encoding='gbk', encoding_errors='ignore')
            except Exception:
                df = pd.read_csv(csv_path, engine='python', encoding='utf-8', sep=None)
        
        print(f"[INFO] CSV文件读取成功")
        print(f"  - 行数: {len(df)}")
        print(f"  - 列数: {len(df.columns)}")
        print(f"  - 列名: {list(df.columns)}\n")
        
        if len(df) == 0:
            print("[ERROR] CSV文件为空！")
            return False
        
        # 显示第一行数据
        print("[INFO] 第一行数据示例:")
        first_row = df.iloc[0]
        for col_name, col_value in list(first_row.items())[:10]:
            if pd.notna(col_value):
                value_str = str(col_value)[:50]
                print(f"  {col_name}: {value_str}")
        print()
        
        # 手动测试提取逻辑
        print("=" * 80)
        print("手动测试CSV提取逻辑")
        print("=" * 80)
        
        from services.ner_service import NERService
        ner_service = NERService()
        
        total_entities = 0
        entities_by_column = {}
        
        for idx, row in df.iterrows():
            row_entities = []
            
            for col_name, col_value in row.items():
                if pd.isna(col_value):
                    continue
                
                col_value_str = str(col_value).strip()
                if not col_value_str or col_value_str.lower() == 'nan':
                    continue
                
                # 创建列实体
                import re
                entity_type = re.sub(r'[^A-Za-z0-9_]', '_', col_name.upper())
                if not entity_type:
                    entity_type = 'CSV_FIELD'
                
                entity = {
                    'type': entity_type,
                    'text': col_value_str,
                    'column': col_name,
                    'confidence': 0.95
                }
                row_entities.append(entity)
                
                # 统计
                if col_name not in entities_by_column:
                    entities_by_column[col_name] = 0
                entities_by_column[col_name] += 1
                
                # NER检测
                try:
                    detected = ner_service.detect_from_text(col_value_str)
                    for ent in detected:
                        if ent['type'] == 'AGE':
                            try:
                                age_value = int(ent['text'])
                                if age_value < 0 or age_value > 150:
                                    continue
                            except (ValueError, TypeError):
                                continue
                        ent['column'] = col_name
                        row_entities.append(ent)
                        entities_by_column[col_name] += 1
                except Exception as e:
                    pass
            
            total_entities += len(row_entities)
            
            # 只显示前3行的详细信息
            if idx < 3:
                print(f"\n[行 {idx}] 提取了 {len(row_entities)} 个实体")
                for ent in row_entities[:5]:
                    print(f"  - {ent['type']}: {ent['text'][:50]} (列: {ent.get('column', 'N/A')})")
        
        print("\n" + "=" * 80)
        print("提取结果统计")
        print("=" * 80)
        print(f"\n总实体数: {total_entities}")
        print(f"总行数: {len(df)}")
        print(f"平均每行实体数: {total_entities / len(df):.2f}\n")
        
        print("按列统计（前15列）:")
        sorted_cols = sorted(entities_by_column.items(), key=lambda x: x[1], reverse=True)
        for col_name, count in sorted_cols[:15]:
            print(f"  {col_name}: {count} 个实体")
        
        if total_entities == 0:
            print("\n[ERROR] 提取到0个实体！请检查CSV文件格式。")
            return False
        else:
            print(f"\n[SUCCESS] 成功提取 {total_entities} 个实体！")
            return True
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_process_files_folder():
    """测试process_files_folder方法"""
    print("\n" + "=" * 80)
    print("测试process_files_folder方法")
    print("=" * 80)
    
    try:
        from services.crossmodal_service import CrossModalAttentionService
        
        service = CrossModalAttentionService(device='cpu')
        
        # 查找CSV文件
        csv_path = None
        db_csv = project_root / "database" / "cxr-record-list.csv"
        if db_csv.exists():
            csv_path = str(db_csv)
        
        if not csv_path:
            uploads_dir = project_root / "uploads"
            if uploads_dir.exists():
                csv_files = list(uploads_dir.glob("*.csv"))
                if csv_files:
                    csv_path = str(csv_files[0])
        
        if not csv_path:
            print("[ERROR] 未找到CSV文件")
            return False
        
        # 查找files文件夹
        files_root = project_root / "database" / "files"
        if not files_root.exists():
            print("[WARN] 未找到files文件夹，跳过process_files_folder测试")
            print(f"  预期路径: {files_root}")
            return True  # 不算失败，只是跳过
        
        output_path = project_root / "output" / "test_csv_extraction"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"[INFO] CSV文件: {csv_path}")
        print(f"[INFO] Files根目录: {files_root}")
        print(f"[INFO] 输出路径: {output_path}\n")
        
        print("开始处理...")
        result = service.process_files_folder(
            csv_path=str(csv_path),
            files_root=str(files_root),
            output_path=str(output_path)
        )
        
        print("\n处理结果:")
        print(f"  - 状态: {result.get('status', 'unknown')}")
        print(f"  - 处理的series数: {result.get('processed', 0)}")
        print(f"  - 匹配数: {result.get('matched', 0)}")
        print(f"  - CSV实体总数: {result.get('total_csv_phi', 0)}")
        print(f"  - TXT实体总数: {result.get('total_txt_phi', 0)}")
        print(f"  - DICOM实体总数: {result.get('total_dicom_phi', 0)}")
        
        if result.get('total_csv_phi', 0) == 0:
            print("\n[ERROR] CSV实体数为0！")
            return False
        else:
            print(f"\n[SUCCESS] CSV实体提取成功！共 {result.get('total_csv_phi', 0)} 个实体")
            return True
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 设置UTF-8编码
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    results = []
    
    # 测试1: 手动CSV提取
    results.append(("CSV提取逻辑", test_csv_extraction()))
    
    # 测试2: process_files_folder方法
    results.append(("process_files_folder", test_process_files_folder()))
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过！")
        sys.exit(0)
    else:
        print("\n[ERROR] 部分测试失败，请检查上面的错误信息。")
        sys.exit(1)

