#!/bin/bash
# Post-receive hook for blog auto-deployment
# This runs on the server when you `git push` to deploy

set -e

REPO_DIR="/opt/blog-repo.git"
WORK_TREE="/opt/blog-worktree"
WWW_DIR="/var/www/blog"
CADDY_SERVICE="caddy"

echo "🚀 Blog deployment started at $(date)"

# Clean up old worktree if exists
rm -rf "$WORK_TREE"

# Clone the repo to a working directory
git --git-dir="$REPO_DIR" --work-tree="$WORK_TREE" checkout -f main

# Navigate to worktree
cd "$WORK_TREE"

# Build with Hugo
echo "📦 Building with Hugo..."
hugo --minify --destination="$WWW_DIR"

# Reload Caddy
echo "🔄 Reloading Caddy..."
sudo systemctl reload caddy

echo "✅ Deployment completed at $(date)"
echo "📂 Files served from: $WWW_DIR"
