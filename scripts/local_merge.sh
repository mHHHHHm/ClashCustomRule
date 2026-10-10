#!/bin/bash
set -e

echo "开始检测订阅源可用性..."
VALID_URLS=""
for url in $(echo -e "$SUBSCRIPTION_URLS"); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -k -L "$url" 2>/dev/null)
  if [ -z "$HTTP_CODE" ]; then HTTP_CODE="000"; fi
  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ 源可用: $url"
    VALID_URLS="$VALID_URLS$url\n"
  else
    echo "❌ 源失效或超时 (HTTP $HTTP_CODE)，已跳过: $url"
  fi
done

export SUBSCRIPTION_URLS=$(echo -e "$VALID_URLS" | sed '/^\s*$/d')

if [ -z "$SUBSCRIPTION_URLS" ]; then
  echo "❌ 所有订阅源均失效，脚本终止。"
  exit 1
fi

echo "检测完毕，开始本地合并构建..."
python3 scripts/local_merge.py

echo "开始上传至 Gist..."
GIST_FILENAME="${GIST_FILENAME:-clash-meta.yaml}"
GIST_DESCRIPTION="Clash Meta config generated at $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# 使用临时文件构造 JSON payload，避免参数过长
PAYLOAD_FILE=$(mktemp)
jq -n \
  --arg desc "$GIST_DESCRIPTION" \
  --arg filename "$GIST_FILENAME" \
  --rawfile content clash-meta.yaml \
  '{description: $desc, files: {($filename): {content: $content}}}' > "$PAYLOAD_FILE"

# 调用 GitHub API 更新 Gist，从文件读取 payload
RESPONSE=$(curl -s -X PATCH \
  -H "Authorization: token $GIST_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  -d @"$PAYLOAD_FILE" \
  "https://api.github.com/gists/$GIST_ID")

rm -f "$PAYLOAD_FILE"
