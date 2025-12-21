import requests
import json

url = "http://localhost:8080/chat/api/019b3f8b-470c-7011-bed4-59dc18f4a679/chat/completions"
headers = {
    "Authorization": "Bearer application-0085d1ee1b64d5d8b0c0023608c67979",
    "Content-Type": "application/json"
}

payload = {
    "message": "开始人才画像分析",
    "stream": False,  # 先用 False 观察完整结构
    "messages": [{"role": "user", "content": "111"}],
    "form_data": {
        "six_dimension_payload": "测试数据",
        "tech_hunter_payload": "测试数据",
        "code_auditor_payload": "测试数据"
    }
}

try:
    print("🚀 正在请求 MaxKB...")
    response = requests.post(url, headers=headers, json=payload)
    print(f"HTTP 状态码: {response.status_code}")
    
    result = response.json()
    
    # 打印完整响应，方便观察结构
    print("\n--- 完整响应内容 ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 检查是否有 node_data 字段
    if "node_data" in result:
        print("\n✅ 发现 node_data，可以进行节点提取！")
    else:
        print("\n⚠️ 未发现 node_data，可能需要检查工作流是否已发布或 URL 是否正确。")

except Exception as e:
    print(f"❌ 请求失败: {e}")