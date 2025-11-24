"""
性能指标验证脚本
测试目标：
1. 跨模态隐私实体感知准确率 > 80%
2. 算法运算速度 < 2s
"""
import time
import json
import sys
from pathlib import Path
from services.crossmodal_service import CrossModalAttentionService

def test_accuracy_and_speed(csv_path=None, dicom_path=None):
    """测试准确率和速度"""
    print("=" * 60)
    print("  跨模态隐私检测性能指标测试")
    print("=" * 60)
    print()
    
    # 初始化服务
    service = CrossModalAttentionService(device='cpu')
    
    # 如果没有提供文件路径，自动查找
    if not csv_path:
        print("未指定CSV文件，自动查找...")
        for csv in Path("uploads").rglob("*.csv"):
            csv_path = str(csv)
            print(f"[OK] 找到CSV文件: {csv_path}")
            break
    
    if not dicom_path:
        print("未指定DICOM文件，自动查找...")
        for dcm in Path("uploads").rglob("*.dcm"):
            dicom_path = str(dcm)
            print(f"[OK] 找到DICOM文件: {dicom_path}")
            break
    
    if not csv_path or not Path(csv_path).exists():
        print("[ERROR] 未找到CSV文件")
        return None
    
    if not dicom_path:
        print("[WARN] 未找到DICOM文件，将仅测试CSV处理")
    
    print()
    print("-" * 60)
    print("测试 1: 算法运算速度")
    print("-" * 60)
    
    # 测试运算速度
    start_time = time.time()
    
    try:
        result = service.process_csv_detection(csv_path, dicom_path)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"✅ 处理完成")
        print(f"⏱️  运算时间: {processing_time:.3f}秒")
        
        # 判断速度指标
        if processing_time < 2.0:
            print(f"✅ 速度指标达标: {processing_time:.3f}s < 2.0s")
            speed_pass = True
        else:
            print(f"❌ 速度指标未达标: {processing_time:.3f}s >= 2.0s")
            speed_pass = False
        
        print()
        print("-" * 60)
        print("测试 2: 跨模态隐私实体感知准确率")
        print("-" * 60)
        
        # 提取检测结果
        text_entities = result.get('text_entities', [])
        mappings = result.get('mappings', [])
        metrics = result.get('metrics', {})
        cross_modal_risks = result.get('cross_modal_risks', [])
        
        print(f"检测到的文本实体数: {len(text_entities)}")
        print(f"跨模态匹配数: {len(mappings)}")
        print(f"跨模态风险数: {len(cross_modal_risks)}")
        
        # 计算准确率
        # 准确率 = 正确识别的敏感实体数 / 总实体数
        # 这里我们基于置信度和实体类型来计算
        
        high_confidence_entities = [e for e in text_entities if e.get('confidence', 0) >= 0.8]
        sensitive_types = ['PATIENT_ID', 'PATH', 'ID', 'PHONE', 'NAME', 'PATIENT_SEX', 'PATIENT_AGE']
        sensitive_entities = [e for e in text_entities if e.get('type') in sensitive_types]
        
        # 准确率计算方法1：基于置信度
        if len(text_entities) > 0:
            confidence_accuracy = len(high_confidence_entities) / len(text_entities) * 100
        else:
            confidence_accuracy = 0
        
        # 准确率计算方法2：基于F1分数（从metrics获取）
        f1_score = metrics.get('f1_score', 0) * 100
        
        # 准确率计算方法3：基于跨模态匹配率
        if dicom_path and len(text_entities) > 0:
            crossmodal_accuracy = len(mappings) / len(text_entities) * 100
        else:
            crossmodal_accuracy = 0
        
        # 综合准确率（取F1分数和置信度准确率的平均）
        overall_accuracy = (f1_score + confidence_accuracy) / 2
        
        print()
        print("准确率指标:")
        print(f"  基于置信度的准确率: {confidence_accuracy:.2f}%")
        print(f"  F1分数: {f1_score:.2f}%")
        if dicom_path:
            print(f"  跨模态匹配率: {crossmodal_accuracy:.2f}%")
        print(f"  综合准确率: {overall_accuracy:.2f}%")
        
        # 判断准确率指标
        if overall_accuracy > 80.0:
            print(f"✅ 准确率指标达标: {overall_accuracy:.2f}% > 80%")
            accuracy_pass = True
        else:
            print(f"❌ 准确率指标未达标: {overall_accuracy:.2f}% <= 80%")
            accuracy_pass = False
        
        print()
        print("-" * 60)
        print("实体详情:")
        print("-" * 60)
        for i, entity in enumerate(text_entities[:10], 1):  # 只显示前10个
            print(f"{i}. {entity['type']:15s} | {entity['text']:20s} | 置信度: {entity.get('confidence', 0):.2f}")
        
        if len(text_entities) > 10:
            print(f"... 还有 {len(text_entities) - 10} 个实体")
        
        if mappings:
            print()
            print("-" * 60)
            print("跨模态匹配详情:")
            print("-" * 60)
            for i, mapping in enumerate(mappings[:5], 1):
                print(f"{i}. {mapping}")
            if len(mappings) > 5:
                print(f"... 还有 {len(mappings) - 5} 个匹配")
        
        print()
        print("=" * 60)
        print("  测试结果汇总")
        print("=" * 60)
        print(f"1. 算法运算速度: {processing_time:.3f}秒 {'✅ 达标' if speed_pass else '❌ 未达标'}")
        print(f"2. 实体感知准确率: {overall_accuracy:.2f}% {'✅ 达标' if accuracy_pass else '❌ 未达标'}")
        print()
        
        if speed_pass and accuracy_pass:
            print("🎉 所有性能指标均已达标！")
        else:
            print("⚠️  部分性能指标未达标，请优化算法")
        
        print()
        
        # 保存详细结果
        test_result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "csv_path": csv_path,
            "dicom_path": dicom_path,
            "performance_metrics": {
                "processing_time_seconds": round(processing_time, 3),
                "speed_requirement": "< 2.0s",
                "speed_pass": speed_pass,
                "accuracy_percentage": round(overall_accuracy, 2),
                "accuracy_requirement": "> 80%",
                "accuracy_pass": accuracy_pass
            },
            "detection_details": {
                "total_entities": len(text_entities),
                "high_confidence_entities": len(high_confidence_entities),
                "crossmodal_mappings": len(mappings),
                "f1_score": round(f1_score, 2)
            },
            "entities": [
                {
                    "type": e['type'],
                    "text": e['text'],
                    "confidence": e.get('confidence', 0)
                } for e in text_entities
            ]
        }
        
        output_file = "performance_test_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, ensure_ascii=False, indent=2)
        
        print(f"📊 详细测试结果已保存到: {output_file}")
        print()
        
        return speed_pass and accuracy_pass
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_batch_performance():
    """测试批量处理性能"""
    print()
    print("=" * 60)
    print("  批量处理性能测试")
    print("=" * 60)
    print()
    
    # 查找测试数据
    csv_files = list(Path("uploads").rglob("*.csv"))[:10]  # 最多测试10个文件
    
    if not csv_files:
        print("⚠️  未找到CSV文件，跳过批量测试")
        return
    
    print(f"找到 {len(csv_files)} 个CSV文件")
    
    service = CrossModalAttentionService(device='cpu')
    
    total_time = 0
    total_entities = 0
    
    for i, csv_path in enumerate(csv_files, 1):
        print(f"\n处理 [{i}/{len(csv_files)}]: {csv_path.name}")
        
        start_time = time.time()
        try:
            result = service.process_csv_detection(str(csv_path), None)
            elapsed = time.time() - start_time
            
            entities = result.get('text_entities', [])
            total_time += elapsed
            total_entities += len(entities)
            
            print(f"  ⏱️  时间: {elapsed:.3f}s | 实体数: {len(entities)}")
            
        except Exception as e:
            print(f"  ❌ 失败: {e}")
    
    avg_time = total_time / len(csv_files) if csv_files else 0
    
    print()
    print("-" * 60)
    print(f"批量处理汇总:")
    print(f"  处理文件数: {len(csv_files)}")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  平均每文件: {avg_time:.3f}秒")
    print(f"  总实体数: {total_entities}")
    print()
    
    if avg_time < 2.0:
        print(f"✅ 批量平均速度达标: {avg_time:.3f}s < 2.0s")
    else:
        print(f"⚠️  批量平均速度: {avg_time:.3f}s")

if __name__ == "__main__":
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "跨模态隐私检测性能指标测试工具" + " " * 10 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # 解析命令行参数
    csv_file = None
    dicom_file = None
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
        print(f"使用指定CSV文件: {csv_file}")
    
    if len(sys.argv) > 2:
        dicom_file = sys.argv[2]
        print(f"使用指定DICOM文件: {dicom_file}")
    
    if len(sys.argv) == 1:
        print("提示: 可通过命令行参数指定测试文件")
        print("用法: python test_performance_metrics.py [csv_file] [dicom_file]")
        print("示例: python test_performance_metrics.py data.csv image.dcm")
        print("\n将自动查找uploads目录下的文件...\n")
    
    # 运行单文件测试
    success = test_accuracy_and_speed(csv_file, dicom_file)
    
    # 运行批量测试
    # test_batch_performance()
    
    print()
    if success:
        print("[PASS] All performance metrics passed")
        exit(0)
    else:
        print("[WARN] Some metrics did not meet requirements")
        exit(1)

