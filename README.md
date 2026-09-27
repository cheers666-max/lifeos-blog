# LifeOS · 学习、工作与数字生活

公开站点：https://cheers666-max.github.io/lifeos-blog/

Hugo + PaperMod。推送 main 后由 GitHub Actions 构建并发布到 GitHub Pages。

## 本地预览与检查

```sh
git submodule update --init --recursive
hugo server
hugo --destination /tmp/lifeos-build
python3 scripts/check-portal.py /tmp/lifeos-build
```

首页由 layouts/index.html 构建，领域入口定义在 data/lifeos.json。文章继续存放在 content/posts，保持原 URL。新内容入口为 content/start、content/explore、content/guides、content/projects。

公开内容只收录经过编辑的文章与方法，不自动镜像私人 Notion 数据。项目页区分规划、试用与验证状态。

## 2026-09-27 改版

新增门户首页、三条入门路线、六个主题领域、数字生活手册、三个项目说明。保留现有文章、系列、搜索、归档、推荐及 RSS。桌面与手机布局已编写；本轮浏览器控制超时，尚未完成视觉验收。

历史 publish.sh 和 deploy/ 为旧服务器部署方式，当前 GitHub Pages 发布不调用它们。


## 数字生活：嵌入已有资源分享社

`/explore/digital/` 通过 iframe 直接嵌入 `https://share.cokelink.com/`，复用原项目的界面、搜索、归档与内容维护。LifeOS 不再存储、选编或复制归档条目；`data/digital.json` 仅保留原站、频道地址和站内实践文章入口。

原入门手册仍位于 `/guides/digital-life/`。嵌入区提供新窗口打开入口，方便独立浏览或在嵌入加载失败时使用。

2026-09-27 检查：原站返回 HTTP 200，无 X-Frame-Options 或 CSP frame-ancestors 限制。若原站后续添加嵌入限制，应在原项目中明确允许 LifeOS 的来源。原站主题和内部导航由原项目管理。
