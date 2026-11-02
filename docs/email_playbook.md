# 套磁邮件：从三封范例里提炼的模板和工作流

范例：Zeya Zhou 写给 Spiess、Udell、Barak 的三封信（2026-08）。

## 1. 三封信的共同骨架

| 段落 | 作用 | 范例里的写法 |
|---|---|---|
| 标题 | 让老师在收件箱里认出是写给他的 | `PhD Inquiry – 姓名 – <老师自己的研究方向用词>`。Spiess 那封直接用了论文标题里的词 |
| ① 我是谁 | 一句话说身份，研究兴趣**照搬老师的用词** | "interested in human-AI decision-making and the design of algorithmic systems that support human judgment" |
| ② 我读了你的什么 | 证明真看过 | 最强的是 Spiess：论文全名、合作者、发表月份，再用自己的话概括核心思想："the algorithm highlights key features … rather than simply providing a recommendation" |
| ②’ 共鸣 | 把我的一个真实经历接到他的核心思想上 | "users' decision quality depended less on the AI's final output and more on whether the system helped them surface the most relevant information"。这是一个**发现**，正好呼应论文论点 |
| ③ 我想研究什么 | 用老师的语言说一个具体问题，表明有方向但愿意被指导 | "More specifically, I am interested in how … I see this as a direction I would like to develop further under supervision." |
| ④ 我能做什么 | 2–3 个项目当证据，具体到方法和产出 | 再加一句 "I would be interested in learning how your research group approaches X. Would you be considering PhD students for 2027 entry?" |
| ⑤ 附件 | 降低老师回复成本 | CV + portfolio 已附；transcript 和 research concept note 可以按需提供 |
| ⑥ 收尾 | 请求一次简短交流 | "a brief discussion if my research interests might be relevant" |

## 2. 为什么 Spiess 那封最像"真心看过"，另外两封弱

- **具体程度分三级：**
  1. 某篇论文，有标题、合作者、时间，加上一句核心思想（Spiess）
  2. 老师网站上的研究陈述，用他的原话改写（Udell："scalable, accessible, and responsible data-driven decision-making in high-stakes domains"）
  3. 泛泛的方向或头衔（Barak："your work on the theoretical foundations of machine learning … Kempner Institute"）

  第 3 级换个老师名字照样能用，老师一眼就看得出来。
- **共鸣要接在"发现"上，而不是"技能"上。** Spiess 那封接的是一个观察到的现象，很有说服力。Barak 那封拿"量化选股的假设检验"去接"泛化理论"，比较牵强。
- **同一个项目不要出现两次。** Udell 和 Barak 两封里，WorldQuant 在 ② 和 ④ 各出现一次，显得经历不够用。
- **篇幅：** 三封都在 330–380 词，偏长。② 和 ③ 是核心，① ④ ⑤ 可以压缩。

## 3. 换成你的版本

你的优势是有几个**能接住老师论点的真实发现**，这正是 Spiess 那封最有力的地方。下面这些都只来自 applicant.yaml，一个字都不加：

| 你的项目 | 可以当作"发现"的点 | 适合的老师类型 |
|---|---|---|
| Arborphy（BioCLIP + EfficientNet 融合） | 用防泄漏、多随机种子的评估协议后，融合模型的提升并不稳定，没能可靠地超过只用 BioCLIP 的基线 | 可信 ML、评估、CV、基础模型 |
| 幻觉的 circuit tracing（Qwen3） | 加入 sham 和随机化对照后，效应太不稳定，撑不起因果结论 | 可解释性、LLM、可信 AI |
| 钙成像自监督去噪 | 遮蔽策略结合 PMD，用真实神经元轮廓构造合成基准 | NeuroAI、自监督、成像 |
| EEG 运动想象解码 | 在按 run 分组的验证下，准确率从 67.9% 提到 77.4% | BCI、神经解码、时间序列 |
| FlyWire 连接组 SBM | 用贝叶斯模型推断潜在神经元类型 | 图模型、贝叶斯、连接组学 |
| 多智能体系统 | 盲审式跨模型验证，加上按实测错误率授予自主权的信任等级 | LLM 智能体、可靠性、人机协作 |

## 4. 模板（每封 230–300 词）

```
Subject: PhD Inquiry (Fall 2027) – Lindsey Ma – <their topic, in their words>

Dear Professor <Last>,

I am Lindsey Ma, finishing an M.S. in Statistics at Columbia, and I am applying to PhD programs for Fall 2027.
I am interested in <their area, their vocabulary>.

I recently read your <year> paper "<exact title>" (with <co-authors>). <One sentence: its core idea in my own words,
ideally with the "rather than …" contrast that shows I understood what is new.> This connected with my own
experience: <one project> — <the finding>, which <how it relates to their claim>. I was also interested in
<their second line of work, one clause>.

More specifically, I would like to work on <a concrete question extending their work, their vocabulary>. I see
this as a direction I would like to develop further under your supervision.

<Evidence: one or two other projects, methods and outcomes, no repeat of the project above.> Would you be
considering PhD students for Fall 2027 through <program name>?

My CV is attached. I would be glad to share my transcript or a short research note.

Thank you for your time. I would appreciate a brief conversation if my interests fit your group's work.

Best regards,
Lindsey Ma
M.S. in Statistics, Columbia University · lindseyma.com
```

如果老师网站写了"想读博请直接申请，不用发邮件"或"邮件请写某个关键词"，按他说的做：要么不发，要么加上那个关键词。

## 5. 工作流：每位老师一封，四个角色分开做

1. **读者（agent，代码核对引用）。** 只读老师本人网站和最近 2–3 年的论文，产出一张小卡片：
   - 研究陈述原句 2 句
   - 一篇 2024–26 年的论文：标题、合作者、年份、摘要里的核心句
   - 第二条研究线
   - 招生或联系说明的原话
   - 通过哪个博士项目招人

   每一项都要附 URL 和原文引用，代码确认引用在页面上，确认不了就删掉这一项。
2. **匹配员（agent）。** 从上面的项目表里选**一个**发现接到这篇论文的核心思想，再写一个具体的研究问题。如果接不上：退一级，用他的研究陈述来接；还是接不上就标记"跳过"，不硬写。
3. **写信员（agent）。** 按第 4 节的模板写，只能用卡片和 applicant.yaml 里的事实。
4. **审信员（agent，与写信员不是同一个，加代码检查）。**
   - **换名测试：** 把老师名字换成名单上另一位，这封信还能用吗？能用就打回重写。
   - **共鸣检查：** 接得是否牵强。
   - **代码检查：** 字数，同一项目不出现两次，没有禁用套话，关于老师的每一个事实都能在卡片上找到出处。
5. **你：** 每批看一遍，批准后存成 Gmail 草稿，由你点发送。
