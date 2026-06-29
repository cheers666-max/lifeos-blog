---
title: "扔掉 critic 的 PPO:GRPO 是怎么靠「组内内卷」省一半的"
date: 2026-06-29
description: "DPO 绕开了强化学习,GRPO 是另一条路——真跑 RL,但把它做便宜了。它扔掉 PPO 那个跟模型一样大的 critic,改用『同一题采样一组、用组内平均当基准』来算 advantage。带数字、配小黑图,从 PPO 痛点一步步推到 GRPO 目标函数,DeepSeek-R1 就是用它训出推理能力的。"
summary: "GRPO = 省掉 critic 的 PPO:组内采样、用组平均当基准算 advantage,DeepSeek-R1 同款"
tags: ["GRPO", "PPO", "强化学习", "RLHF", "大模型", "对齐"]
categories: ["技术"]
series: ["偏好优化家族"]
ShowToc: true
TocOpen: true
math: true
cover:
  image: "01-teacher-vs-peer.png"
  alt: "PPO 老师打分 vs GRPO 同学互评"
  caption: "PPO 靠一个『老师』(critic)打分;GRPO 让一组答案『同学互评』,扔掉了 critic"
---

前两篇([DPO](../dpo-preference-optimization/)、[IPO](../ipo-identity-preference-optimization/))走的是"**绕开强化学习**"那条路——把偏好直接变成一条监督损失。这篇讲**另一条路**:**真的跑强化学习,但把它做便宜了**。这就是 **GRPO**(Group Relative Policy Optimization,组相对策略优化),DeepSeek-R1 就是用它训出推理能力的。

## 这趟要走的路(主线)

1. 对齐有两条路:DPO(绕开 RL)和真·RL(PPO/GRPO)——GRPO 在 RL 这条;
2. PPO 的痛点:要同时养**两个一样大的模型**(策略 + critic),贵又难训;
3. GRPO 的一招:**同一题采样一组答案,用"组内平均"当基准**,把 critic 整个扔掉("内卷");
4. 怎么把"组内相对"变成可优化的数(advantage 归一化);
5. 拼成 GRPO 的目标函数(还是 PPO 那套 clip + 一根 KL 拴绳);
6. 它用在哪、奖励函数为什么是灵魂。

一句话:**GRPO = 省掉 critic 的 PPO——不学一个价值模型来当基准,而是让同一题的一组答案互相比、用组内平均当基准。**

## 1 · 大局:对齐的两条路,GRPO 在 RL 这边

模型 SFT 完只会接龙,要"对齐"得有奖励 + 拴绳(防 reward hacking,这些前两篇讲过)。**对齐有两条路**:

```
                 ┌─ DPO/IPO:不跑 RL,把偏好直接变监督损失(前两篇)
对齐(SFT 之后)─┤
                 └─ 真·RL:PPO → GRPO,真的边采样边奖励边更新
                         GRPO 是 DeepSeek 训 R1 推理用的省钱版
```

DPO 是"想方设法**绕开** RL";GRPO 是"**正经跑** RL,只是做便宜了"。

> **小结**:GRPO 站在 RL 这条路上。**下一步先看它要省的钱花在哪——PPO 的痛点。**

## 2 · PPO 的痛点:要养两个一样大的模型

经典的 RL 对齐用 PPO,它要同时跑**两个大模型**:

- **策略模型(actor)**:就是你在训的语言模型,负责生成回答;
- **价值模型(critic)**:专门估"当前这步大概值多少分",用来算 **advantage**——这个回答比"平均水平"好多少。

问题是:**critic 和策略模型一样大**,显存、算力直接翻倍,而且它自己也难训、估不准还会拖累整个训练。

为什么非要 critic?因为 PPO 的 advantage 是 `这次的奖励 − critic 估的基准`:

$$
A \approx r - V(s) \qquad (V \text{ 就是 critic 估的「平均水平」})
$$

{{< figure src="02-drop-critic.png" alt="小黑扔掉 critic 模型" caption="PPO 要养策略 + critic 两个大模型;GRPO 把 critic 扔进垃圾桶,省一半" >}}

> **小结**:PPO 贵在那个"估基准"的 critic。**GRPO 的全部聪明,就是用别的办法估这个基准、把 critic 干掉。**

## 3 · GRPO 的一招:同一题采样一组,用「组内平均」当基准

GRPO 的想法朴素到拍大腿——**别花钱养老师了,让同学互评**:

> 对**同一个问题**,一次采样**一组** G 个回答(比如 8 个)→ 全用奖励模型/规则打分 → **拿这组的平均分当基准**。

某个回答好不好,**不看绝对分,看它在这组里高于还是低于平均**。就像考试看的不是你考多少分,而是你超没超过这次的班级平均线。基准从"critic 估出来的"变成"组内同学现算出来的"——**critic 就不需要了**。

{{< figure src="01-teacher-vs-peer.png" alt="PPO 老师打分 vs GRPO 同学互评" caption="PPO:一个老师(critic)给每个答案打分;GRPO:一组答案互相比、按平均线评" >}}

> **小结**:用"组内平均"顶替"critic 估的基准"。**下一步:把"高于/低于平均"变成一个能塞进损失的数——advantage 归一化。**

## 4 · 把「组内相对」变成数:advantage 归一化

一组 G 个回答,奖励是 $r_1,\dots,r_G$。GRPO 给第 $i$ 个回答的 advantage 是**对这组做标准化**:

$$
\hat{A}_i = \frac{r_i - \mathrm{mean}(r_1,\dots,r_G)}{\mathrm{std}(r_1,\dots,r_G)}
$$

(同一个回答里的**每个 token 共用这个 $\hat{A}_i$**。)

**算给你看**:一题采样 4 个回答,奖励 `[1, 0, 1, 0]`(2 对 2 错),平均 = 0.5、标准差 = 0.5:

$$
\hat{A} = \left[\tfrac{1-0.5}{0.5},\ \tfrac{0-0.5}{0.5},\ \tfrac{1-0.5}{0.5},\ \tfrac{0-0.5}{0.5}\right] = [+1,\ -1,\ +1,\ -1]
$$

**高于平均 → 正 advantage → 强化;低于平均 → 负 → 压制。** 这就是"内卷"的数学版。还有个隐藏好处:**全队一起进步时,平均线自己会涨**,所以单纯"刷分"压不出优势——这是 GRPO 对 reward hacking 天然有点抵抗力的原因(注意只是"有点",奖励设计烂照样翻车)。

> **小结**:advantage = 在组内标准化后的相对好坏。**下一步:把它塞进 PPO 那套 clip 目标里。**

## 5 · 拼成 GRPO 的目标函数

好消息:**外壳还是 PPO 那套**(你若读过 PPO 的 clip 目标,这里零负担)。GRPO 的目标:

$$
\mathcal{J}_{GRPO}(\theta) = \mathbb{E}\Big[ \tfrac{1}{G}\sum_{i=1}^{G} \tfrac{1}{|o_i|}\sum_{t} \min\big( \rho_{i,t}\,\hat{A}_i,\ \mathrm{clip}(\rho_{i,t},1-\varepsilon,1+\varepsilon)\,\hat{A}_i \big) \Big] - \beta\, D_{KL}(\pi_\theta \,\|\, \pi_{ref})
$$

逐块拆(大白话):

- $\rho_{i,t} = \dfrac{\pi_\theta(o_{i,t}\mid q,o_{i,<t})}{\pi_{\theta_{old}}(o_{i,t}\mid q,o_{i,<t})}$:策略比率,**和 PPO 一模一样**——新策略比旧策略更想/更不想吐这个 token;
- $\min(\rho\hat{A},\ \mathrm{clip}(\cdot)\hat{A})$:**和 PPO 一模一样的"限速器"**——advantage 为正鼓励、为负压制,但步子不许迈太大;
- $\tfrac{1}{G}\sum_i \tfrac{1}{|o_i|}\sum_t$:对**一组 G 个回答**求平均、对每个回答的**每个 token** 求平均;
- $-\beta\,D_{KL}$:**拴绳**——别离参考模型太远(和 DPO 的 β/KL 同一个味道)。

**所以 GRPO 和 PPO 的实质差别只有两点**:① advantage 用第 4 节的"组内归一化"(不用 critic);② KL 的放法(下一节)。其余照搬 PPO。

> ⚠️ **纠个常见误解**:GRPO **仍然用 advantage、仍然是 clip 的策略梯度**(PPO 家族);它**不是**"拟合某个分布的交叉熵监督学习"。别被某些对比表带偏。

> **小结**:GRPO 目标 = PPO 的 clip 外壳 + 组内归一化 advantage + KL 拴绳。**下一步:KL 这次放哪、怎么算。**

## 6 · KL 放在损失里(还用了个特殊估计式)

经典 PPO 一般把 KL **揉进奖励**;GRPO 直接把 KL **加在损失项上**(就是上面那个 $-\beta D_{KL}$),而且用一个**无偏、恒非负**的估计式(常称 k3):

$$
D_{KL}(\pi_\theta\|\pi_{ref}) \approx \frac{\pi_{ref}(o_{i,t})}{\pi_\theta(o_{i,t})} - \log\frac{\pi_{ref}(o_{i,t})}{\pi_\theta(o_{i,t})} - 1
$$

逐 token 算,永远 ≥ 0,越偏离参考模型越大。作用和前两篇的拴绳一样:**防止模型为冲奖励跑飞**。

> **小结**:KL 进损失、用 k3 估计。到这儿 GRPO 的全部零件齐了。**下一步:它实际怎么用。**

## 7 · 用在哪:奖励函数是灵魂

GRPO 特别适合**有明确对错的任务**(数学、代码)——因为奖励可以直接用**规则**给,根本不用训奖励模型。DeepSeek-R1 的推理能力,很大程度就是这么"卷"出来的:

- **数学题**:答案对不对(能对上标准答案就 +1);
- **代码**:能不能跑、过不过测试用例;
- **格式**:有没有按 `<think>…</think>` 先思考再回答。

```python
# TRL 里就这么几行(奖励函数是关键)
def reward_func(completions, **kwargs):
    return [1.0 if check_answer(c) else 0.0 for c in completions]  # 对=1 错=0

GRPOTrainer(model="Qwen/Qwen2-0.5B-Instruct",
            train_dataset=dataset, reward_funcs=reward_func).train()
```

> **奖励函数设计 = GRPO 的命门**:它定义了"什么算好答案"。设得好,模型"卷"向真本事;设得烂,照样 reward hacking(模型卷向钻空子)。采样数(常 5~8 个)、温度(1.0 起调)也都影响"卷"的质量。

## 8 · 白月光调查档案:把 GRPO 当成你要查的「人」

{{< figure src="03-curve-advantage.png" alt="一组小黑按组内平均线评高低" caption="组内平均线:高于线的强化↑、低于的压制↓——advantage = 在这组里的相对位置" >}}

- **它是谁**:PPO 的变体,用"组内相对"算 advantage,扔掉 critic。
- **它从哪来**:PPO 养 critic 太贵;DeepSeek(DeepSeekMath / R1)提出用组内平均当基准,省一半还更稳。
- **如果它消失**:你就得回 PPO,多养一个跟模型一样大的 critic,贵且难调。
- **它和谁有关**:父亲是 **PPO**(clip 外壳照搬);共用 **KL 拴绳**;奖励常来自**规则**而非奖励模型。
- **谁依赖它**:DeepSeek-R1 等推理模型;TRL 的 `GRPOTrainer`、VERL 框架。
- **下一条线索**:嫌"组内归一化"还有偏 → 查 **Dr.GRPO / GRPO 的各种改进**;想对比"不跑 RL"的路 → 回看 **DPO**。

## 收尾:把主线再串一遍

> **对齐有两条路:DPO 绕开 RL,GRPO 真跑 RL 但做便宜了。PPO 贵在要养一个和模型一样大的 critic 来估基准;GRPO 的一招是"同一题采样一组、用组内平均当基准",advantage = 组内标准化的相对好坏(高于平均强化、低于压制),于是 critic 被扔掉。外壳还是 PPO 的 clip 目标 + 一根 KL 拴绳。奖励函数是灵魂——这也是 DeepSeek-R1 靠规则奖励"卷"出推理能力的办法。**

到这儿,「偏好优化家族」就凑齐了两条路:**DPO/IPO(不跑 RL)** 和 **GRPO(跑 RL、省 critic)**。下一站可以看 GRPO 的改进(Dr.GRPO),或回头把整条对齐地图连成一张总图。

*(手绘图由「小黑」IP 生成;公式用 KaTeX 渲染。部分对照了我自己的 Notion 学习笔记,并补齐了目标函数、归一化 advantage、KL 估计三处。)*
