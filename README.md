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


## 数字生活：频道归档精选

`/explore/digital/` 展示 `share.cokelink.com` 中的编辑精选；原入门手册仍位于 `/guides/digital-life/`。

- 内容入口：`data/digital.json` 的 `archive.items`，保留归档 ID、原始标题、收录日期、详情地址和 Telegram 原帖地址。展示标题与摘要经过精简。
- 本页为人工选编的静态快照，不会自动跟随频道更新，也不改动归档站的精选标记。当前选编日期见 `archive.selected_at`。
- 新增内容时先核对公开接口 `/api/messages/:id`，再补充条目；列表首项是主推荐。
- 封面为本站文字设计。2026-09-27 检查时，归档返回的 TeamAI 图片地址为 404，因此页面不依赖归档媒体。
- 归档仍是完整内容的来源；网站仅提供摘要和跳转入口。无需读取 D1、R2 或 Telegram 凭据。
