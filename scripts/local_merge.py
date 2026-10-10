import os
import requests
import yaml
import base64
import sys

# 1. 获取环境变量中的订阅链接
urls = os.environ.get('SUBSCRIPTION_URLS', '').split()
all_proxies = []
seen_names = set()

# 2. 逐个下载并解析
for url in urls:
    try:
        resp = requests.get(url, timeout=15)
        content = resp.text
        # 尝试直接解析 YAML，如果失败说明可能是 Base64 编码的文本
        try:
            data = yaml.safe_load(content)
        except:
            try:
            # 尝试 Base64 解码后再解析
                content = base64.b64decode(content).decode('utf-8')
                data = yaml.safe_load(content)
            except Exception:
                print(f"❌ 无法解析 YAML 或 Base64: {url}")
                continue
        
        if not isinstance(data, dict):
            print(f"❌ 格式不是字典，跳过: {url}")
            continue
            
        proxies = data.get('proxies', [])
        for p in proxies:
            # 简单去重逻辑：如果节点名字已经存在，就跳过
            name = p.get('name')
            if name and name not in seen_names:
                seen_names.add(name)
                all_proxies.append(p)
            else:
                # 名字重复时，给个后缀或者直接跳过（这里选跳过）
                pass
                
    except Exception as e:
        print(f"❌ 下载或解析失败: {url}, 错误: {e}")

print(f"✅ 本地合并完成！共获取到 {len(all_proxies)} 个节点。")

if not all_proxies:
    print("❌ 没有获取到任何节点，终止。")
    sys.exit(1)

# 3. 构建最终配置文件
# 如果没有代理组，Clash 是跑不起来的，这里我们生成基本的策略组
proxy_names = [p['name'] for p in all_proxies]
config = {
    'mixed-port': 7890,
    'allow-lan': False,
    'mode': 'rule',
    'log-level': 'info',
    'external-controller': '127.0.0.1:9090',
    'proxies': all_proxies,
    'proxy-groups': [
        {
            'name': '🚀 节点选择',
            'type': 'select',
            'proxies': ['♻️ 自动选择', 'DIRECT'] + proxy_names
        },
        {
            'name': '♻️ 自动选择',
            'type': 'url-test',
            'url': 'http://www.gstatic.com/generate_204',
            'interval': 300,
            'proxies': proxy_names
        }
    ],
    'rules': [
        'DOMAIN-SUFFIX,openai.com,🚀 节点选择',
        'DOMAIN-SUFFIX,anthropic.com,🚀 节点选择',
        'MATCH,🚀 节点选择'
    ]
}

# 4. 写入文件
with open('clash-meta.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(config, f, allow_unicode=True, sort_keys=False)

print("✅ 配置文件 clash-meta.yaml 生成完毕。")
