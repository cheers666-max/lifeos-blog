# LifeOS Blog

个人博客 — 记录技术、思考、阅读和生活的数字花园。

🌐 **访问**: [http://35.208.201.12/](http://35.208.201.12/)（域名绑定中）

## 技术栈

- **生成器**: [Hugo](https://gohugo.io/) (v0.163+)
- **主题**: [PaperMod](https://github.com/adityatelange/hugo-PaperMod)
- **部署**: GCP e2-micro + Caddy
- **部署方式**: `git push` 自动部署（post-receive hook）

## 写作流程

```bash
# 1. 新建文章
hugo new content posts/my-post.md

# 2. 编辑 + 本地预览
hugo server -D

# 3. 发布（推送即部署）
git add -A && git commit -m "post: xxx"
git push origin main       # 归档到 GitHub
git push blog-server main  # 部署到服务器
```

或直接对 Claude 说：**"帮我写一篇关于 XX 的博客"**

## 目录结构

```
lifeos_blog/
├── hugo.yaml              # 站点配置
├── content/
│   ├── posts/             # 📝 博客文章
│   ├── about/             # 🙋 关于我
│   ├── reference/         # 📚 参考与资源
│   ├── search/            # 🔍 搜索页
│   └── archives.md        # 📦 归档
├── themes/PaperMod/       # 主题 (submodule)
├── deploy/                # 部署脚本
└── .claude/skills/        # Claude Code 技能
```

## 栏目

| 分类 | 内容 |
|------|------|
| 技术 | 软件架构、工程实践、工具链 |
| 思考 | 产品理念、认知升级、决策框架 |
| 阅读 | 读书笔记、思维模型提炼 |
| 生活 | 日常观察、周报、实验记录 |

## 参考灵感

见 [/reference/inspiring-blogs/](http://35.208.201.12/reference/inspiring-blogs/) — 整理了一批值得学习的优秀个人博客。
