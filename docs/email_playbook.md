# Lindsey 的套磁工作流

每封信都要让老师读出三件事：
1. **她真的看了我的网站和论文。**
2. **她真心想跟我读博**，而且有一个具体想做的问题。
3. **她做得到**，有项目经验和真实的发现撑腰。

结构参考 2026-08 的三封范例信（不是 Lindsey 本人写的，只借结构）。

## 信的骨架（230–300 词）：每段负责上面哪一点

| 段 | 内容 | 负责 |
|---|---|---|
| 标题 | `PhD Inquiry (Fall 2027) – Lindsey Ma – <老师自己的研究方向用词>` | 1 |
| ① 我是谁 | Columbia 统计硕士，申请 2027 秋季入学；研究兴趣用**老师网站上的原词** | 1 |
| ② 我读了你的什么 | 一篇 2024–26 年的论文：标题、合作者、年份，再用一句自己的话说出它新在哪里（"rather than …"） | 1 |
| ②’ 呼应 | 我的**一个**项目里的**一个真实发现**，接上这篇论文的论点 | 3 |
| ③ 我想做什么 | 顺着他的工作提一个具体问题，用他的语言；"a direction I would like to develop further under your supervision" | 2 |
| ④ 我能做什么 | 另外 1–2 个项目：方法和结果；问他是否通过 <项目名> 招 2027 年的学生 | 3 |
| ⑤ 附件和收尾 | CV 已附；如方便，希望简短交流 | — |

```
Subject: PhD Inquiry (Fall 2027) – Lindsey Ma – <their topic, their words>

Dear Professor <Last>,

I am Lindsey Ma, finishing an M.S. in Statistics at Columbia and applying to PhD programs for Fall 2027. I am
interested in <their area, their vocabulary>.

I recently read your <year> paper "<exact title>" (with <co-authors>). <Its core idea in one sentence, my words.>
This connected with my own work: <project> — <finding>, which <how it bears on their claim>. I was also interested
in <their second line of work>.

More specifically, I would like to work on <concrete question extending their work>. I see this as a direction I
would like to develop further under your supervision.

<One or two other projects: method and outcome.> Would you be considering PhD students for Fall 2027 through
<program>?

My CV is attached. Thank you for your time; I would appreciate a brief conversation if my interests fit your group.

Best regards,
Lindsey Ma
M.S. in Statistics, Columbia University · lindseyma.com
```

## 你的素材库：可以接住老师论点的发现

全部来自 `config/applicant.yaml`，不加一个字。

| 项目 | 发现 | 接给哪类老师 |
|---|---|---|
| Arborphy（BioCLIP + EfficientNet 融合） | 换成防泄漏、多随机种子的评估后，融合的提升并不稳定，没能可靠地超过只用 BioCLIP 的基线 | 可信 ML、评估、CV、基础模型 |
| Qwen3 幻觉 circuit tracing | 加了 sham 和随机化对照后，效应太不稳定，撑不起因果结论 | 可解释性、LLM、可信 AI |
| 钙成像自监督去噪 | 遮蔽策略结合 PMD，用真实神经元轮廓构造合成基准 | NeuroAI、自监督、成像 |
| EEG 运动想象解码 | 在按 run 分组的验证下，准确率从 67.9% 提到 77.4% | BCI、神经解码 |
| FlyWire 连接组 | 用贝叶斯随机块模型推断潜在神经元类型 | 图模型、贝叶斯、连接组学 |
| 多智能体系统 | 盲审式跨模型验证，加上按实测错误率授予自主权的信任等级 | LLM 智能体、可靠性 |

## 工作流：每位老师走一遍，每个角色只做一件事

| 步 | 谁 | 输入 → 输出 | 怎么保证准 |
|---|---|---|---|
| 1 读老师 | 读者 agent（`agents/38_prof_reader.md`） | 老师主页、实验室网站 → `data/email/cards/<id>.json` | 每一项都附 URL 和原文；代码确认原文在页面上，对不上就删 |
| 2 找呼应 | 匹配 agent（同一 playbook 的第 2 部分） | 卡片 + 素材库 → 选一个发现、一个研究问题 | 接不上就退一级用研究陈述来接；还接不上就**跳过这位老师** |
| 3 写信 | 写信 agent（`agents/40_email_writer.md`） | 卡片 + 匹配结果 → 草稿 | 关于老师的事实只能来自卡片，关于你的只能来自 applicant.yaml |
| 4 审信 | 审信 agent（`agents/50_email_critic.md`），和写信 agent 不是同一个；加代码检查 `outreach/emailcheck.py` | 草稿 → 通过 / 打回 | 换名测试，检查呼应是否牵强，代码查字数、项目重复和套话 |
| 5 发 | 你 | 一批草稿 → Gmail 草稿 → 你点发送 | 每天最多 40 封，同一个系每天最多 2 封 |

两条特殊规则：
- 老师网站写了"不要发邮件，直接申请"，就不写。
- 老师网站要求邮件里写某个关键词，就照写。
