---
title: "小狗的铃铛：用 Hooks 把安全策略从'焊死'变成'挂载'"
date: 2026-07-15
description: "s03 的 Permission 是焊死在 agent_loop 里的——加一个新检查就得改循环。s04 用观察者模式做了一个铃铛系统：四个挂钩（UserPromptSubmit/PreToolUse/PostToolUse/Stop），铃铛随意挂卸。s03 的整个安全检查逻辑完整搬进 permission_hook 作为一颗铃铛挂上 PreToolUse——逻辑一行没少，但 agent_loop 不再有任何安全代码。"
summary: "焊死变挂载：观察者模式 × 责任链模式 → 四个 hook point 挂铃铛 → permission_hook 继承 s03 → Stop 钩子可挽留循环 → agent_loop 彻底对扩展封闭"
tags: ["Claude Code", "Agent", "Harness", "Hooks", "Observer Pattern", "Chain of Responsibility", "LLM"]
categories: ["技术"]
series: ["Claude Code Harness 内部架构"]
ShowToc: true
TocOpen: true
math: false
cover:
  image: "01-collar-hooks.png"
  alt: "小狗项圈上的四个挂钩，挂着四枚铃铛"
  caption: "s04 的核心：项圈上焊了四个挂钩，铃铛想挂什么挂什么——agent_loop 一行不改"
---

上一篇我们给小狗戴上三道锁项圈（Permission）。但三道锁是**焊死**的——`check_permission()` 函数硬编码在 agent_loop 里。想加一个日志记录？改 agent_loop。想加输出大小警告？再改 agent_loop。

s04 把这个焊死拆掉，改成**挂钩+铃铛**——四个挂钩焊在项圈上永远不会动，但铃铛可以随意挂上/取下/换新。

## 这趟要走的路

1. **焊死的痛**：为什么 `check_permission()` 不该留在 agent_loop 里
2. **铃铛系统**：HOOKS 注册表 + register_hook + trigger_hooks 三件套
3. **四颗铃铛逐个拆**：permission_hook / log_hook / large_output_hook / summary_hook
4. **碰撞**：中断机制、优先级、Stop 死循环
5. **升级链路**：s03（焊死）→ s04（挂载）— 逻辑一行没少，耦合全部松开

---

{{< figure src="02-s03-vs-s04.png" alt="s03焊死的锁 vs s04可插拔的铃铛" caption="左边 s03：三道锁焊死在项圈上，火花表示『硬编码』。右边 s04：四个空挂钩，铃铛可以随时装上取下——安全逻辑一行没少，但不再锁死在循环里。" >}}

## 1 · 焊死的痛：为什么 agent_loop 不该管安全

回顾 s03 的 agent_loop：

```python
# s03: 安全检查焊死在循环里
for block in response.content:
    if block.type != "tool_use":
        continue
    if not check_permission(block):    # ← 这一行就是问题
        results.append("Permission denied.")
        continue
    handler = TOOL_HANDLERS.get(block.name)
    output = handler(**block.input)
```

这 3 个问题会随着功能增长越来越痛：

1. **每加一个横切关注点就要改 loop**：想加日志？改。想加统计？改。想加大输出警告？改。agent_loop 变成大杂烩。
2. **违反 SRP（单一职责）**：agent_loop 应该只管"调用 LLM → 分发工具 → 喂回结果"。安全检查、日志、统计——都不是循环的职责。
3. **移除一个检查要改循环**：如果某个环境下不需要权限检查（比如只读模式），你得改 agent_loop 或者在 `check_permission` 里加 if-else——两种都很丑。

**问题的本质**：agent_loop 是一个**流程**（循环/分发/反馈），但安全/日志/统计是**横切关注点**——它们散布在流程的各个节点上。硬编码让流程和关注点**焊死在一起**。

s04 的解：把流程变成发布事件，把关注点变成订阅事件。

---

{{< figure src="01-collar-hooks.png" alt="小狗项圈上的四个挂钩挂着四枚铃铛" caption="四个挂钩焊在项圈上：UserPromptSubmit → PreToolUse → PostToolUse → Stop。铃铛挂在挂钩上，想换就换——agent_loop 只负责在正确的时机摇铃铛。" >}}

## 2 · 铃铛系统三件套

整个 Hook 系统只有 10 行核心代码：

```python
# ① 事件注册表：四个 hook point，每个维护一个回调列表
HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}

# ② 挂铃铛：往事件上注册回调
def register_hook(event: str, callback):
    HOOKS[event].append(callback)

# ③ 摇铃铛：事件发生时依次触发所有回调
def trigger_hooks(event: str, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:   # 非 None = 拦截，中断后续铃铛
            return result
    return None                  # 全部 None = 放行
```

**设计模式**：观察者模式 × 责任链模式的融合。

- `register_hook` = 订阅（Observer Pattern 的 subscribe）
- `trigger_hooks` = 发布 + 链式中断（Chain of Responsibility 的短路机制）
- 返回值 `None` = "没事，下一个"
- 返回值非 `None` = "出事了，中断链"

**为什么用 `append` 而不是 `=`？** 同一事件可以有多个订阅者。比如 `PreToolUse` 上挂了两个铃铛：`permission_hook`（安全检查）+ `log_hook`（记录日志）。注册顺序 = 执行顺序——最简单的优先级机制。

四个 hook point 覆盖 Agent Loop 的四个关键节点：

| 挂钩 | 在哪触发 | 回调拿到什么 | 能干什么 |
|------|---------|-------------|---------|
| `UserPromptSubmit` | 用户输入后、LLM 调用前 | `query: str` | 上下文注入、输入预处理 |
| `PreToolUse` | 工具执行前 | `block: ToolUseBlock` | 权限拦截、日志记录 |
| `PostToolUse` | 工具执行后 | `block, output` | 输出校验、大小警告 |
| `Stop` | 循环即将退出 | `messages: list` | 统计摘要、**挽留循环** |

> **小结**：10 行代码，四个事件。agent_loop 只负责在正确的时机喊 `trigger_hooks(...)`，铃铛响什么、响几个——循环完全不关心。

---

## 3 · 四颗铃铛逐个拆

### 铃铛 A：permission_hook（PreToolUse）

这是 s03 的 `check_permission()` 整个搬过来，**函数体一行没少**：

```python
def permission_hook(block):
    if block.name == "bash":
        for pattern in DENY_LIST:            # Gate 1: 黑名单
            if pattern in block.input.get("command", ""):
                return "Permission denied by deny list"
        for kw in DESTRUCTIVE:               # Gate 2: 规则库 → Gate 3: 人工审批
            if kw in block.input.get("command", ""):
                choice = input("Allow? [y/N] ").strip().lower()
                if choice not in ("y", "yes"):
                    return "Permission denied by user"
    if block.name in ("write_file", "edit_file"):
        if not safe_path_check(block.input.get("path", "")):
            choice = input("Allow? [y/N] ").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"
    return None  # 全通过
```

和 s03 的区别只有两点：
1. **不再叫 `check_permission`，叫 `permission_hook`**——语义从"必须调用的检查函数"变成"可插拔的回调"
2. **通过 `register_hook("PreToolUse", permission_hook)` 挂上去**，而不是硬编码在 agent_loop 里

如果哪天想**去掉权限检查**（比如只读模式），s03 要改 agent_loop，s04 只需要不注册这个钩子。

### 铃铛 B：log_hook（PreToolUse）

```python
def log_hook(block):
    args_preview = str(list(block.input.values())[:2])[:60]
    print(f"[HOOK] {block.name}({args_preview})")
    return None  # ← 永远返回 None，只记录不拦截
```

这枚铃铛也挂在 `PreToolUse` 上，但在 `permission_hook` **之后**注册——所以它只在安全检查通过后才执行。如果 `permission_hook` 返回了非 None（被拦截），链中断，`log_hook` 根本不会被触发——这是正确的，因为工具没被执行，没东西可记。

### 铃铛 C：large_output_hook（PostToolUse）

```python
def large_output_hook(block, output):
    if len(str(output)) > 100000:
        print(f"[HOOK] ⚠ Large output from {block.name}: {len(str(output))} chars")
    return None
```

挂在 `PostToolUse` 上——工具执行**之后**触发。和 PreToolUse 的区别：它拿到的不只是 `block`，还有 `output`（工具执行结果）。只警告不拦截——大输出本身不是安全问题。

### 铃铛 D：summary_hook（Stop）

```python
def summary_hook(messages: list):
    tool_count = sum(1 for m in messages
                     for b in (m.get("content") if isinstance(m.get("content"), list) else [])
                     if isinstance(b, dict) and b.get("type") == "tool_result")
    print(f"[HOOK] Stop: session used {tool_count} tool calls")
    return None
```

挂在 `Stop` 上——循环结束前触发。**但这颗铃铛有一个隐藏的超能力**：

```python
# agent_loop 的 Stop 处理
if response.stop_reason != "tool_use":
    force = trigger_hooks("Stop", messages)
    if force:                         # ← Stop 钩子返回了非 None
        messages.append({"role": "user", "content": force})
        continue                      # ← 循环不退出！回到 while True
    return
```

这意味着一个 Stop 钩子可以**挽留循环**——返回一段提示词，追加进 messages，agent_loop 继续跑。s17 Autonomous Agents 的"空闲自驱动"就是靠这个机制：模型说"我做完了"，Stop 钩子说"你还有 3 个 TODO 没完成，继续"，循环被挽留。

{{< figure src="03-stop-hook.png" alt="Stop钩子挽留小狗继续跑" caption="小狗刚要停步，Stop 铃铛摇晃闪烁：『还有3件事没做完，继续！』——这就是 s17 自主代理的前身。" >}}

---

## 4 · 碰撞：铃铛系统的边界

### 问题 1：一个铃铛意外返回非 None，后面的全被跳过

```python
for callback in HOOKS[event]:
    result = callback(*args)
    if result is not None:
        return result   # ← 链中断，后面的 callback 永远不执行
```

如果 `log_hook` 因为 bug 返回了 `True` 而不是 `None`——它后面的铃铛全部被静默跳过。这个契约是刻意的：**返回值就是控制权**。编写钩子的人必须遵守"只想拦截时才返回非 None，否则必须显式 `return None`"。

### 问题 2：注册顺序 = 优先级，但没有显式保证

```python
register_hook("PreToolUse", permission_hook)  # 先注册 → 先执行
register_hook("PreToolUse", log_hook)         # 后注册 → 后执行
```

在当前文件里一目了然——所有 `register_hook` 调用都在一个地方。但当 s07 Skill Loading 引入"不同 skill 各自注册钩子"时，跨文件的注册顺序可能出乎意料。s07 的 `SkillManifest` 会引入显式的优先级字段。

### 问题 3：Stop 钩子被滥用 → 无限循环

```python
if force:
    messages.append(...)
    continue  # 如果 Stop 钩子每次返回同样的提示词 → 死循环
```

当前代码没有防护。`summary_hook` 永远返回 `None` 所以没事，但如果有人写了一个"总觉得没做完"的钩子——每轮 Stop 都挽留，永动机。s17 会加 `idle_turns_max` 上限。

> **小结**：三个问题都不是 bug——它们是**刻意的简化**。在 5-10 个钩子的规模下，显式优先级是过度设计；`idle_turns_max` 在还没遇到自主代理的上下文里是 YAGNI。每个问题的解法都精确地出现在后续章节里。

---

## 5 · s01 → s04 升级链路

四代进化，agent_loop 核心逻辑变动量：

| 版本 | 核心机制 | agent_loop 改动行数 | 设计模式 |
|------|---------|-------------------|---------|
| s01 | 只有 bash | — | — |
| s02 | 5 个工具，查表分发 | 改 2 行 | 策略模式（dispatch map） |
| s03 | 三关审批管道 | 加 1 行 | 责任链模式 |
| s04 | 铃铛系统 | 改 1 行 + 加 2 行 | 观察者模式 |

**四次升级，agent_loop 的 while + stop_reason + messages 循环骨架从头到尾没变过。** 每次升级都是"在循环外面加东西"——从不在循环里面改逻辑。

```python
# s01: output = run_bash(cmd)
# s02: handler = TOOL_HANDLERS.get(name); output = handler(**input)
# s03: if not check_permission(block): continue
# s04: if trigger_hooks("PreToolUse", block): continue
#      ...
#      trigger_hooks("PostToolUse", block, output)
#      ...
#      if trigger_hooks("Stop", messages): continue  # 可挽留
```

---

## 6 · 白月光调查档案：Hoops

| 七问 | 回答 |
|------|------|
| **它是谁** | 一个观察者模式回调系统：4 个事件 + register_hook（订阅） + trigger_hooks（发布），链式中断（返回值非 None = 拦截） |
| **它从哪来** | s03 的 `check_permission()` 焊死在 loop 里——每加一个横切关注点就要改循环 |
| **为什么存在** | 把流程（agent_loop）和横切关注点（权限/日志/统计）解耦——循环只发事件，铃铛各管各的 |
| **如果它消失** | 所有安全/日志/统计/上下文注入逻辑堆回 agent_loop → 一个几百行的大杂烩函数 |
| **关系网** | 上游 ← s03 Permission 逻辑搬入 / 同级 → s02 Tool Use / 下游 → s07 Skill Loading、s10 System Prompt、s17 Autonomous Agents |
| **谁依赖它** | s07 技能加载（批量注册钩子）、s10 上下文注入（UserPromptSubmit 的升级）、s17 自主代理（Stop 挽留循环） |
| **下一条线索** | 四个 hook point 在循环的关键节点上，但循环**中间**怎么办？→ s05 TodoWrite（计划系统，在循环中插入结构化任务管理） |

## 下一篇预告

s05 TodoWrite：**小狗的记事本**——怎么把一个非结构化的用户需求拆解成可追踪的 TODO 列表？怎么防止模型"做了三件事忘了第四件"？

---

> **系列文章：《Claude Code Harness 内部架构》**
>
> 每篇文章一个核心机制，一只西高地小狗贯穿始终。
> - 第一篇：[s01 Agent Loop — 小狗传菜](https://cheers666-max.github.io/lifeos-blog/posts/agent-loop-harness/)
> - 第二篇：[s02+s03 — 五个房间与三道锁项圈](https://cheers666-max.github.io/lifeos-blog/posts/tool-use-permission/)
>
> 项目源码：[shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（MIT 开源，20 章递进式教学）
