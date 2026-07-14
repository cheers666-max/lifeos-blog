---
title: "用一只西高地小狗讲透 Agent Loop：Claude Code 的心跳机制"
date: 2026-07-14
description: "从零拆解 Claude Code 最核心的 Agent Loop 机制——为什么一个 while True 循环能撑起整个编码代理。用西高地小狗当传菜员的隐喻贯穿全文：大厨(LLM)发号施令，小狗(harness)跑来跑去执行，直到大厨说停。逐行拆解 s01/code.py，四个破坏性问题碰撞边界，最后画出完整 harness 装备升级图。"
summary: "一只西高地传菜小狗讲透 Agent Loop：while stop_reason == 'tool_use' 循环 → 三条消息一轮回 → 逐行代码拆解 → 四个破坏性边界问题"
tags: ["Claude Code", "Agent", "Harness", "Agent Loop", "Tool Use", "LLM"]
categories: ["技术"]
series: ["Claude Code Harness 内部架构"]
ShowToc: true
TocOpen: true
math: false
cover:
  image: "01-puppy-waiter-loop.png"
  alt: "西高地小狗叼着篮子在大厨和厨房之间来回跑"
  caption: "Agent Loop 就这一件事：小狗(harness)在大厨(LLM)和厨房(工具)之间来回传菜，直到大厨说停"
---

很多人讲 Agent，一上来就是"multi-step reasoning""tool-augmented LLM"，听着很高级但不知道里面到底在跑什么。

这篇换个法子，**用一只西高地小狗来讲**。不用什么高深的架构图，就想象一个餐厅厨房：大厨是 LLM，小狗是传菜员（harness），菜刀案板烤箱是工具。小狗不决定菜谱、不评判味道——它只在大厨喊话时跑腿，端回来放在大厨面前，等下一声喊。

这 138 行 Python（`s01_agent_loop/code.py`）就是 Claude Code 的**心跳**。后面 19 章的权限、钩子、子代理、记忆、定时……全是挂在这个心跳上的装备。

## 这趟要走的路（先记住这条主线）

后面每一节都是这条主线上的一步，读的时候时不时回来对一下位置：

1. **为什么需要循环**——一个任务 N 步操作，模型一次只吐一段文本，怎么串起来？
2. **核心画面：小狗传菜**——大厨喊→小狗跑→端回来→大厨再喊→……直到"上菜！"
3. **三条消息一轮回**——user prompt → assistant(tool_use) → user(tool_result) → 下一轮
4. **逐行拆解代码**——`while True`、`messages.append`、`stop_reason`、`run_bash`
5. **四个破坏性边界问题**——无限循环？工具失败？幻觉调用？危险命令？
6. **升级版全景图**——20 章装备全挂在心跳上

一句话：**Agent Loop 就是一只诚实的传菜小狗。它不动脑、不拒绝、只管跑腿。后面 19 章，全是在给它穿装备。**

{{< figure src="01-puppy-waiter-loop.png" alt="小狗叼着篮子在大厨和厨房之间跑循环" caption="小狗叼着篮子在大厨(LLM)和厨房(工具)之间来回跑——这就是 Agent Loop 的完整画面" >}}

## 1 · 大局：为什么需要一个循环

先把最大的背景立住。

**语言模型在干嘛？** 你给它一句话，它吐出下一段文本。一次推理，一段输出。

**那为什么需要循环？** 因为真实任务从来不是"一句话→一段文本"就能搞定的。你说"帮我修这个 bug"，模型得：

1. 读文件（需要工具）
2. 定位 bug（分析）
3. 改代码（需要工具）
4. 跑测试（需要工具）
5. 测试挂了 → 回去看日志（需要工具）
6. 再改 → 再跑 → 直到通过

这中间 N 步操作，每一步模型都需要**看结果才能决定下一步**。如果每次 API 调用是独立的，它们之间没有"记忆"，那模型就永远是金鱼——做完一步就忘了。

**Agent Loop 解决的就是这个**：把 N 次独立 API 调用用 `while True` 串起来，上一次工具的输出变成下一次的输入。

> **小结**：模型一次只能吐一段文本，但真实任务需要多步。Agent Loop 就是把离散的 API 调用焊成一条连续的任务执行链。**那"焊"是怎么焊的？下一步看小狗传菜。**

## 2 · 核心画面：小狗传菜

别急着看代码，先把这个画面刻在脑子里：

```
你(用户)走进餐厅：「我要一份蛋炒饭！」

大厨(LLM)翻开菜谱：「先得拿鸡蛋和米饭」
大厨朝传菜口喊：「小狗！拿鸡蛋、米饭！」

小狗(harness)叼着篮子跑去冷库，叼回来鸡蛋和米饭，放在大厨面前。

大厨：「还需要葱花」
大厨喊：「小狗！去菜地拔葱！」

小狗跑去菜地，叼回来一把葱。

大厨炒好，尝了一口：「淡了」
大厨喊：「小狗！拿盐！」

小狗跑去调料架，叼回来盐罐。

大厨又尝了一口：「行了，上菜！」
大厨把盘子推到传菜口。(stop_reason = "end_turn")

小狗摇摇尾巴，任务完成。
```

**这个画面里有三个角色，记住它们的职责边界**：

| 角色 | 现实中 | 做什么 | **不做什么** |
|------|--------|--------|-------------|
| 大厨 | LLM | 看菜谱、做决定、喊话、判断什么时候上菜 | 不动手拿食材、不开火、不跑腿 |
| 小狗 | Harness | 听大厨喊话、跑去拿东西、端回来 | 不决定菜谱、不评判好不好吃、不说"我觉得该停了" |
| 厨房 | Tools | 提供食材、火力、案板、调料 | 不动脑、不主动 |

**关键洞察**：Harness（小狗）不替 LLM（大厨）做任何决定。大厨说拿盐就拿盐，大厨说上菜就上菜。Harness 是一台诚实的执行器——这是整个 Claude Code 架构最基本的设计原则。

> **小结**：Agent Loop = 一只诚实的传菜小狗。不动脑、不拒绝、只管跑腿。**那在代码里，这个"跑腿"到底是怎么写的？下一节看三条消息怎么构成一轮。**

## 3 · 三条消息一轮回

在代码层面，"小狗跑一趟"对应的就是三条消息：

```
[user]     "帮我列出当前目录的文件"     ← 用户说的
[assistant] 调用 bash: "ls -la"         ← 大厨喊"拿食材！"
[user]     工具返回: "file1.py file2.md..." ← 小狗端回来放在面前
────── 一轮结束，下一轮开始 ──────
[assistant] "当前目录有 file1.py 和 file2.md" ← 大厨看过结果，说话
(end_turn)                                ← 大厨说完了
```

**三条消息就是一个"原子循环单位"**：

1. **用户消息（user）**：可能是真人说的，也可能是上一轮的工具结果
2. **助手响应（assistant）**：模型要么调工具（`tool_use`），要么直接回复文本（`stop`）
3. **工具结果（user）**：工具执行完的结果，作为新的 user 消息喂回去

{{< figure src="02-three-messages.png" alt="小狗用前爪推动三个气泡连成的环" caption="三条消息围成一个环：user prompt → assistant(tool_use) → user(tool_result) → 下一轮。小狗站在中间把环串起来。" >}}

注意第 3 条消息的 role 是 **`user`** 而不是 `tool`——这是 Anthropic API 的设计选择：工具结果以用户消息的形式插入对话。为什么？因为从模型视角看，工具结果和用户输入没有本质区别——都是"外部世界给的新信息"。

> **小结**：一轮 = 三条消息。`messages[]` 数组是模型唯一的记忆——每次 API 调用都发完整历史，模型没有内部状态。**现在有了画面和消息格式，可以逐行看代码了。**

## 4 · 逐行拆解 s01/code.py

项目地址：[shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)，20 章递进式教学。s01 是整个项目的心脏，138 行代码，核心只有下面这个函数：

```python
def agent_loop(messages: list):
    while True:
        response = client.messages.create(        # ①
            model=MODEL, system=SYSTEM,
            messages=messages,                    # ②
            tools=TOOLS, max_tokens=8000,
        )

        messages.append({                         # ③
            "role": "assistant",
            "content": response.content
        })

        if response.stop_reason != "tool_use":    # ④
            return

        results = []
        for block in response.content:
            if block.type == "tool_use":          # ⑤
                output = run_bash(
                    block.input["command"]
                )
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,      # ⑥
                    "content": output,
                })

        messages.append({                         # ⑦
            "role": "user",
            "content": results
        })
```

逐行拆解，每行讲三件事：**它在做什么、为什么这样设计、小狗在干嘛**。

---

### ① `while True` — 小狗站上跑步机

```python
while True:
```

不知道大厨要喊几次。可能是 1 次（"给我看目录"），可能是 5 次（"读文件→改→跑测试→看日志→再改"）。所以不设上限——**循环次数由模型决定，不由代码决定**。

{{< figure src="03-while-true-treadmill.png" alt="小狗在while True跑步机上认真跑" caption="小狗站在 while True 跑步机上认真跑。它不知道要跑几圈——什么时候停，大厨说了算(stop_reason)。" >}}

但这也是最大的风险点：万一模型一直喊 `ls -la` 永远不会说"做完了"呢？这个边界问题在第五节讨论。

### ② `client.messages.create(messages=messages)` — 每次把完整历史发给大厨

```python
response = client.messages.create(
    model=MODEL, system=SYSTEM,
    messages=messages,    # ← 完整对话历史
    tools=TOOLS,
    max_tokens=8000,
)
```

**为什么发完整历史？** 因为 LLM 是无状态的。上一轮 API 调用结束后，模型"忘记"了一切。要让模型知道"我刚才调了 `ls`、结果是什么、现在该干嘛"，只能靠 `messages[]` 数组把完整历史传回去。

打个比方：大厨（LLM）有失忆症。小狗每次跑回来，不光要端上食材，还得把**从客人进店到现在的所有对话**复述一遍：

> "客人说要蛋炒饭，你让我去拿鸡蛋，我拿回来了（这是鸡蛋），你说要葱花，我拿回来了（这是葱花），现在鸡蛋和葱花都在你面前了——下一步干什么？"

`messages[]` 就是这个"完整复述"。它是模型唯一的记忆。

### ③ `messages.append(response)` — 记录大厨说了什么

```python
messages.append({
    "role": "assistant",
    "content": response.content
})
```

把模型的响应存进历史。下一次循环的 `messages` 会包含这一条，模型能看到"我刚才说过了要调 `ls`"。

### ④ `if stop_reason != "tool_use": return` — 大厨唯一能说"停"的地方

```python
if response.stop_reason != "tool_use":
    return
```

**这是整个循环唯一的出口。** 当模型不再调工具、直接回复文本时，`stop_reason` 变成 `"end_turn"`，循环结束。

**关键设计决策**：harness 代码里没有任何"我认为该停了"的逻辑。停止权完全在模型手里。这是 Claude Code 的核心哲学——**Agency 来自模型训练，不是代码编排**。

### ⑤ `run_bash(block.input["command"])` — 小狗真的跑去拿东西

```python
output = run_bash(block.input["command"])
```

`s01/code.py` 只注册了一个工具——`bash`。`run_bash` 就是一个 `subprocess.run` 的包装：

```python
def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    r = subprocess.run(command, shell=True, capture_output=True,
                       text=True, timeout=120)
    return (r.stdout + r.stderr).strip()[:50000]
```

这里的危险命令过滤是一个**硬编码黑名单**——显然不够用。`"rm -rf /"` 拦住了，但 `"rm -rf ~/"` 呢？这就是 s03 Permission 要解决的问题。

### ⑥ `tool_use_id` — 小狗给每个东西贴上标签

```python
"tool_use_id": block.id,
```

模型在一轮中可能同时调用多个工具。`tool_use_id` 让模型知道"这个结果是哪次调用的"。就像小狗同时叼回来鸡蛋和盐，得贴标签：这包是鸡蛋（对应"拿鸡蛋"那条指令），这包是盐（对应"拿盐"那条指令）。

### ⑦ `messages.append(tool_result)` — 小狗把结果放在大厨面前

```python
messages.append({
    "role": "user",
    "content": results
})
```

工具结果以 `"role": "user"` 的身份插入对话。为什么是 user 而不是 tool？因为 Anthropic API 的设计中，工具结果是"来自外部世界的新信息"，和用户输入一样——都是模型需要处理的新上下文。

然后 `while True` 回到循环顶部。模型看到工具结果，决定下一步：继续调工具，还是完成任务。

> **小结**：这个 30 行的函数里，四个最关键的决策——① 不设循环上限（让模型控制）② 每次发完整历史（模型无状态）③ stop_reason 是唯一退出条件（harness 不动脑）④ 工具结果以 user 身份插入（来自外部世界）——每一个都是刻意的设计选择。**但这个简单的循环能搞砸的事也不少。下一节碰撞四个边界问题。**

## 5 · 碰撞：四个会搞垮这循环的问题

不回避问题。这个 `while True` 循环有四个明显的脆弱点。

---

### 问题 1：无限循环——谁拦住狂飙的小狗？

```python
while True:
```

没有 `max_turns`，没有 token 预算检查，没有"你已经调了 100 次 `ls` 了是不是该停了"的逻辑。

**后果**：如果模型陷入"调工具→看不明白结果→再调一次→还是不满足→再调……"的死循环，这个函数会烧光 token 预算。

**谁来解决**：s11 Error Recovery（重试上限、模型降级）+ s08 Context Compact（上下文太长时压缩）

---

### 问题 2：工具执行失败——小狗摔倒了怎么办？

```python
r = subprocess.run(command, shell=True, capture_output=True,
                   text=True, timeout=120)
```

如果 bash 命令失败了（文件不存在、权限不够、命令拼错），当前代码只会把 stderr 当成普通文本丢给模型。模型可能不理解这行 error、或者反复重试同一个失败的操作。

**后果**：模型在同一个错误上反复撞墙。

**谁来解决**：s11 Error Recovery（错误分类 + 升级策略 + 回退模型）

---

### 问题 3：幻觉调用——小狗跑去了不存在的储物间

```python
for block in response.content:
    if block.type == "tool_use":
        output = run_bash(block.input["command"])
```

当前只注册了一个工具 `bash`，但如果模型"幻觉"调用了一个不存在的工具（比如调用 `read_file` 而不是用 `cat`），Anthropic API 层面会直接拒绝。但代码没有处理"tool call 被 API 拒绝"的情况。

**后果**：API 层面的 400 错误会直接抛异常，打断整个循环。

**谁来解决**：s02 Tool Use（工具注册表 + dispatch map，确保只有注册过的工具才能被调用）

---

### 问题 4：危险命令——小狗叼了一颗炸弹回来

```python
dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
if any(d in command for d in dangerous):
    return "Error: Dangerous command blocked"
```

这只是一个字符串匹配的黑名单。加 `"rm -rf ~/"`？漏了。加 `"dd if="`？又漏了。这种"打地鼠"式的安全策略永远补不全。

**后果**：黑名单之外的任何危险命令都会被执行。

**谁来解决**：s03 Permission（可配置的审批管道，不是硬编码黑名单）

---

{{< figure src="04-four-dangers.png" alt="小狗站在四条岔路口面对四个危险方向" caption="小狗站在四个危险方向的岔路口：无底洞(∞循环)、断桥(Error)、幻影(fake tool)、炸弹(rm -rf)。这四个问题分别由 s11、s02、s03 来解决。" >}}

> **小结**：这四个问题不是 bug——它们是刻意保留在这个最简版本里的。后续 19 章做的事，就是用一个一个的"装备"把这些脆弱点补上。**那补完之后，这只小狗长什么样？**

## 6 · 全副武装的传菜小狗（20 章全景图）

把 s02 到 s20 的所有机制挂上 Agent Loop 的心跳，这只小狗变成了这样：

```
┌──────────────────────────────────────────────────────────┐
│              Agent Loop（全副武装版）                      │
│                                                          │
│  ┌──────────────── hello, world ────────────────┐        │
│  │  messages[] = [user_prompt]  ← 完整对话历史   │        │
│  │                                              │        │
│  │  while True:                                 │        │
│  │    response = LLM(messages, tools, system)   │        │
│  │    messages += response                      │        │
│  │                                              │        │
│  │    if stop: break                            │        │
│  │                                              │        │
│  │    for each tool_call:                       │        │
│  │      ├─ s03 Permission check ─── 审批链      │        │
│  │      ├─ s04 PreToolUse Hook ── 钩子          │        │
│  │      ├─ s02 Dispatch tool ─── 工具路由        │        │
│  │      ├─ s18 Worktree ─────── 沙箱隔离        │        │
│  │      ├─ Execute │ s12 Task ── 任务记录        │        │
│  │      └─ s04 PostToolUse Hook ─ 钩子          │        │
│  │                                              │        │
│  │    messages += results                       │        │
│  │    s08 Context Compact ── 太长了就压缩        │        │
│  │    s11 Error Recovery ── 出错了就恢复         │        │
│  │    s09 Memory ─────────── 重要的记住          │        │
│  └──────────────────────────────────────────────┘        │
│                                                          │
│  外挂系统：                                               │
│    s06 Subagent  ─ 分身小狗（独立 messages[] + 独立循环） │
│    s07 Skill     ─ 小狗的"技能包"按需加载                  │
│    s13 Background ─ 后台任务不阻塞主循环                    │
│    s14 Cron      ─ 定时闹钟触发任务                        │
│    s15-16 Teams  ─ 多只小狗协作                            │
│    s17 Autonomous ─ 小狗空闲时自己找活干                    │
│    s19 MCP       ─ 第三方工具接入                           │
│    s20 Comprehensive ─ 全部穿上                             │
└──────────────────────────────────────────────────────────┘
```

{{< figure src="05-full-harness.png" alt="全副武装的西高地小狗穿着所有Harness装备" caption="升级版传菜小狗：头盔(权限s03)、对讲机(钩子s04)、分身(子代理s06)、腰包(记忆s09)、手表(定时s14)、小旗(MCP s19)——全挂在 Agent Loop(s01) 的跑步机上。" >}}

**你带走的画面**：Agent Loop 不是什么复杂的编排引擎，它就是一只诚实的小狗在跑道上来回跑。模型（大厨）决定每一步做什么，harness（小狗）只管执行和反馈。权限是它的项圈，钩子是它的铃铛，子代理是它的分身，记忆是它的小本子，MCP 是它认识的其他帮手。

> **每一章，就是给这只小狗穿上一件新装备。**

## 7 · 白月光调查档案：Agent Loop

按照我们的老规矩，给这个"传菜小狗"建一份调查档案：

| 七问 | 回答 |
|------|------|
| **它是谁** | 一个 `while stop_reason == "tool_use"` 循环，让模型反复调工具、看结果、再决定下一步 |
| **它从哪来** | 2023 年 Anthropic 发布 tool_use 能力后，需要一种方式把多次 API 调用串成连续任务链 |
| **为什么存在** | 模型一次只能吐一段文本，但真实任务需要多步操作（读→分析→改→测→修）|
| **如果它消失** | 模型只能"一次性回答"：调完一次工具就得停，不能根据结果继续操作。所有多步编码任务全部瘫痪 |
| **关系网** | 上游：LLM 的 tool_use/stop_reason 能力 → 同级：Tool Use(s02)、Permission(s03) → 下游：Hooks(s04)、Subagent(s06)、Memory(s09)……所有章节都挂在它上面 |
| **谁依赖它** | s02-s20 全部依赖它。s06 Subagent 本质是"全新 messages[] + 独立 Agent Loop"。s20 Comprehensive 是"所有机制围绕一个 Agent Loop" |
| **下一条线索** | 模型能调哪些工具？怎么防止它调危险的命令？→ **s02 Tool Use（工具注册和分发）→ s03 Permission（审批管道）** |

## 下一篇预告

下一篇（s02 Tool Use + s03 Permission）：**小狗戴上项圈**——工具注册表怎么让模型知道"厨房里有什么"？审批管道怎么在模型喊出 `rm -rf` 时把它拦住？

---

> **系列文章：《Claude Code Harness 内部架构》**
>
> 用最笨的办法理解最聪明的系统——每篇文章一个核心机制，一只西高地小狗贯穿始终。
>
> 项目源码：[shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（MIT 开源，20 章递进式教学）
