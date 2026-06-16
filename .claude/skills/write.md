---
name: write
description: Write and publish a new blog post to LifeOS blog. Creates Hugo markdown, helps draft/refine content, previews locally, then commits and deploys to both GitHub and the live server with a single git push. Use when the user wants to write a new article, draft a post, or publish to their blog.
---

# LifeOS Blog Writing

Write blog posts with a structured workflow: draft → preview → publish.

## Quick Start

Ask the user for the topic or title. If they just say "write a blog post" without specifics, ask:
- What's the main idea?
- Is this technical, reflective, or a book note?
- Any specific angle or story to tell?

## Workflow

### 1. Create the Post

```bash
cd /Users/ajing/Projects/lifeos_blog && hugo new content posts/<slug>.md
```

The slug should be short, English, kebab-case (e.g., `my-first-post`, `why-i-start-writing`).

### 2. Edit Frontmatter

Open the created file and update the frontmatter:

```yaml
---
title: "<Chinese or English title>"
date: "<YYYY-MM-DD>"
description: "<one-line summary for SEO and previews>"
summary: "<slightly longer summary for listing pages>"
tags: ["tag1", "tag2"]
categories: ["<技术|思考|阅读|生活|产品>"]
series: []
ShowToc: true
TocOpen: false
draft: false  # set to true to hide from production
---
```

Remove `draft: true` when ready to publish. Keep it `true` for work-in-progress.

### 3. Write the Content

Follow these writing rules adapted from the article-writing skill:

**Opening**: Lead with something concrete — a story, a problem, an observation, a number. Never start with "In today's world..." or similar filler.

**Structure**: 
- One idea per section with a clear heading
- Use short paragraphs (2-4 sentences max)
- Code blocks for technical content
- Blockquotes for key takeaways or references

**Voice**: Direct, personal, conversational. Write like you're explaining to a friend over coffee. In Chinese when the idea flows better in Chinese, in English for technical terms.

**Ending**: Close with a takeaway, a question, or a call to action — not a soft summary.

**Banned**: 
- 众所周知 / 随着XX的发展 / 在当今时代
- 毋庸置疑 / 显而易见 
- game-changer, revolutionary, cutting-edge
- Vague claims without personal experience backing

### 4. Preview Locally

```bash
cd /Users/ajing/Projects/lifeos_blog && hugo server -D --noHTTPCache
```

Open http://localhost:1313/ to preview. Check:
- Titles and headings read well
- Code blocks render correctly
- Links work
- Mobile view looks good
- No broken images

### 5. Build and Publish

Once the user approves:

```bash
cd /Users/ajing/Projects/lifeos_blog

# Build to verify no errors
hugo --minify

# Commit
git add -A
git commit -m "post: <title>"

# Push to GitHub (origin) — this archives the post and shows activity
git push origin main

# Push to server (blog-server) — this triggers auto-deployment via post-receive hook
# The server runs Hugo build and reloads Caddy automatically
git push blog-server main
```

After push, verify:
```bash
curl -s http://35.208.201.12/posts/<slug>/ | grep '<title>'
```

### 6. Share

Remind the user they can now:
- Share the link on social media
- Post to their Twitter/LinkedIn
- Add a link to the post in other relevant articles (cross-linking)

## Post Types Guide

### Technical Article (技术)
- Start with the problem you faced
- Show the solution with code/commands
- Explain why it works
- Close with alternatives considered or lessons learned

### Thinking / Opinion (思考)
- Start with a tension, contradiction, or surprising observation
- Build one argument per section
- Use personal experience as evidence
- End with an open question or implication

### Reading Notes (阅读)
- Don't just summarize the book — extract mental models
- For each insight: what the book says → what it means → how you'll apply it
- One actionable takeaway per book minimum
- Link to related posts if you've written on the topic before

### Life / Reflection (生活)
- Specific anecdotes > general reflections
- Write the small moment that illustrates the big idea
- Honest and vulnerable beats polished and safe

## Quick Reference

| What | Command |
|------|---------|
| New post | `hugo new content posts/<slug>.md` |
| Preview | `hugo server -D` |
| Build check | `hugo --minify` |
| Deploy | `git push origin main && git push blog-server main` |
| Verify | `curl -s http://35.208.201.12/posts/<slug>/` |

## Git Remotes

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | `https://github.com/cheers666-max/lifeos-blog` | Code hosting, activity tracking |
| `blog-server` | `ssh://blog-server-iap/opt/blog-repo.git` | Auto-deploy to live server |

`blog-server` uses IAP tunnel via `~/.ssh/config` → always routes through Google's Identity-Aware Proxy for security.
