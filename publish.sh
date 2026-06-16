#!/bin/bash
# LifeOS Blog — 发布脚本
# 用法: ./publish.sh
# 先构建 Hugo，然后推送到 GitHub (归档) 和服务器 (部署)

set -e

echo "📦 Building Hugo site..."
cd "$(dirname "$0")"
hugo --minify

echo ""
echo "📤 Pushing to GitHub..."
git push origin main

echo ""
echo "🚀 Deploying to server..."
git push blog-server main

echo ""
echo "✅ Published! Verify:"
echo "   http://35.208.201.12/"
echo "   https://github.com/cheers666-max/lifeos-blog"
