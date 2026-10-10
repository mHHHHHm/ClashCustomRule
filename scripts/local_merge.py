import os
import requests
import yaml
import base64
import sys
import socket
import concurrent.futures

# ================= 1. 获取订阅与下载解析 =================
urls = os.environ.get('SUBSCRIPTION_URLS', '').split()
all_proxies = []

for url in urls:
    try:
        resp = requests.get(url, timeout=15)
        content = resp.text
        # 尝试直接解析 YAML
        try:
            data = yaml.safe_load(content)
        except:
            # 尝试 Base64 解码后再解析
            try:
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
            all_proxies.append(p)
                
    except Exception as e:
        print(f"❌ 下载或解析失败: {url}, 错误: {e}")

print(f"✅ 原始合并完成！共获取到 {len(all_proxies)} 个节点。")

if not all_proxies:
    print("❌ 没有获取到任何节点，终止。")
    sys.exit(1)

# ================= 2. 终极清洗 + 深度去重 =================
print("开始进行终极清洗、深度去重与瘦身...")

# 2.1 基础协议与字段清洗
step1_proxies = []
for p in all_proxies:
    # 协议白名单，只保留主流且兼容性好的
    if p.get('type') not in ['vless', 'vmess', 'trojan', 'hysteria2', 'ss', 'ssr']:
        continue
    # 剔除带易报错非标字段的节点（防止 Clash 内核崩溃）
    if 'xhttp-opts' in p or 'ech-opts' in p or 'reuse-settings' in p or '_spider-x' in p:
        continue
    # 严格校验 REALITY short-id
    if p.get('type') == 'vless' and 'reality-opts' in p:
        sid = p['reality-opts'].get('short-id')
        if not sid:
            continue
        sid_str = str(sid).strip()
        is_valid_hex = all(c in '0123456789abcdefABCDEF' for c in sid_str)
        # 非法字符、长度大于16、长度等于0，统统踢掉
        if not is_valid_hex or len(sid_str) > 16 or len(sid_str) == 0:
            continue
    # 剔除缺少 server 或 port 的
    if not p.get('server') or not p.get('port'):
        continue
    step1_proxies.append(p)

print(f"  - 基础字段清洗后剩余: {len(step1_proxies)} 个")

# 2.2 深度去重（核心改进：按服务器指纹去重，无视名字不同）
seen_fingerprints = set()
dedup_proxies = []
for p in step1_proxies:
    node_type = p.get('type', '')
    server = p.get('server', '')
    port = str(p.get('port', ''))
    # 获取密码或UUID作为鉴别要素
    auth = str(p.get('password', p.get('uuid', '')))
    
    # 生成唯一指纹
    fingerprint = f"{node_type}:{server}:{port}:{auth}"
    
    if fingerprint not in seen_fingerprints:
        seen_fingerprints.add(fingerprint)
        dedup_proxies.append(p)

print(f"  - 深度去重后剩余: {len(dedup_proxies)} 个")

# ================= 3. TCP 连通性并发测活 =================
def tcp_check(proxy):
    try:
        server = proxy.get('server')
        port = int(proxy.get('port'))
        with socket.create_connection((server, port), timeout=3):
            return proxy
    except Exception:
        return None

print(f"开始 TCP 连通性测试，共计 {len(dedup_proxies)} 个节点...")
valid_proxies = []
with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
    results = executor.map(tcp_check, dedup_proxies)

for p in results:
    if p is not None:
        valid_proxies.append(p)

print(f"  - TCP 测活后剩余: {len(valid_proxies)} 个")

# ================= 4. 按地区限额瘦身 =================
final_proxies = []
region_counts = {}
# 常见地区关键词
region_keywords = ['香港', 'HK', '日本', 'JP', '美国', 'US', '新加坡', 'SG', '台湾', 'TW', '韩国', 'KR', '英国', 'UK', '德国', 'DE', '法国', 'FR', '俄罗斯', 'RU']

for p in valid_proxies:
    name = p.get('name', '')
    region = '其他'
    for kw in region_keywords:
        if kw.lower() in name.lower():
            region = kw
            break
    
    # 每个地区最多保留 30 个节点，防止 UI 卡死
    if region_counts.get(region, 0) >= 30:
        continue
        
    region_counts[region] = region_counts.get(region, 0) + 1
    final_proxies.append(p)

all_proxies = final_proxies
print(f"✅ 经过终极清洗、去重、测活与瘦身，最终保留了 {len(all_proxies)} 个精品节点。")

# ================= 5. 构建最终配置文件 =================
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

# ================= 6. 写入文件 =================
with open('clash-meta.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(config, f, allow_unicode=True, sort_keys=False)

print("✅ 配置文件 clash-meta.yaml 生成完毕。")
