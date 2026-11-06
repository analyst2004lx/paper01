# extract_com_AnswerAndModify —— 逐条回答审阅意见 / 给出 tex 修改方案，并写回清单

## 功能

在已经得到以下两个文件之后使用：

1. `xxx_comments.md`：`extract_comments.py` 从带批注 PDF 中提取的批注清单（编号 C001…）
2. `xxx_comments.json`：`extract_com_mapping.py` 把每条批注映射到 tex 源码后的结果（含 `tex_file`、`tex_line`、`tex_col`、`tex_text`、`match`）

本提示词让模型按编号逐条读取 tex 中对应位置的上下文，判断审阅意见的性质，给出：

- **Answer**：对审阅人的回答。用于：评语是提问；或评语给了建议但我们认为不合理（说明不采纳的理由）。
- **Modify**：具体的 tex 修改方案。用于：评语指出了表述/逻辑/结构问题；或采纳了建议；或不完全采纳但有更好的改法。

两者可以同时出现（例如：先回答问题，再给出为避免误解而做的修改）。结果以字段形式**追加**到 `.md` 中对应编号的条目里，再同步到 `.json`。

默认只写方案，**不改 tex**；用户明确说「应用修改」时才改 tex（见第 6 节）。

## 怎么让模型使用

在 Cursor 里对模型说（路径换成实际文件）：

```text
按 script/pdf_review/extract_com_AnswerAndModify.md 的流程，
处理 paper01_SCI/paper_CN-lw_comments.md 里的 C001–C030，
tex 源是 paper01/paper_CN.tex。
```

可选的范围写法：`全部`、`C012,C017,C045`、`第 3 页`、`只处理有评语的（comment 不是 none）`、`只处理章节级意见`。
若尚未生成清单，先运行：

```text
python script/pdf_review/extract_comments.py <带批注.pdf>
python script/pdf_review/extract_com_mapping.py <xxx_comments.md> <main.tex>
```

---

## 以下是给模型的指令

### 1. 读取输入

1. 读 `.json`，取出用户指定范围内的条目。每条的关键字段：`id`、`page`、`line`、`text`（被批注原文）、`context`（所在整行）、`comment`（评语，`none` 表示只做了标记）、`kind`、`more_targets`、`tex_file`、`tex_line`、`tex_col`、`tex_text`、`match`。
2. 对每条，读取 `tex_file` 中 `tex_line` 前后约 15 行，弄清它所在的段落和小节。若评语针对整节（锚点是章节标题，如「方法没讲清楚」），读完整个小节。
3. `match` 为 `partial` 时位置基本可信，但 PDF 与 tex 文本有差异（宏、`\ref`、公式）；为 `none` 时，用 `text`/`context` 在 tex 中自行搜索定位，找不到就在条目里说明。
4. `kind` 中带 `Text+` 的条目，评语与高亮的配对是脚本推断的。若评语内容与被批注文字明显对不上，改看 `context`（便签所在行）或附近文字来理解评语，并在 Answer 里注明「配对存疑」。
5. 必要时查看论文其他部分（定义、算法、实验结果）再作答，不要只凭局部一句话下结论。

### 2. 判断评语性质并决定写什么

| 评语性质 | 写什么 |
| --- | --- |
| 提问（「谁指派？」「如何搜索？」） | Answer 给出答案；若读者会有同样疑问，说明原文写得不清楚，同时给 Modify 补充说明 |
| 质疑表述/逻辑（「太绝对」「与实际相符吗？」） | 认同则给 Modify；不认同则在 Answer 中给出理由和依据（引用文中位置或文献） |
| 修改建议（「先讲例子再给结论」「用加工机器代替机械臂」） | 采纳则给 Modify；不采纳则在 Answer 说明理由；有更好改法则 Modify 写更好的改法并在 Answer 简述为何不照原建议 |
| 风格类（「啰嗦」「描述要通俗易懂」） | 直接给 Modify（精简/改写后的文本） |
| `comment: none`（只高亮/划线） | 推断审阅人可能的关注点（术语不统一、表述生硬、事实存疑等），在 Answer 开头写「推断：…」；确有问题才给 Modify，否则 Answer 写「推断无需修改：理由」 |

同一问题在多条中重复出现时，只在第一条完整作答，后面的条目写「同 C0xx」，并补充本处特有的差异。
同一术语的全文替换（如「机械臂→加工机器」）在第一次出现的条目里给出统一方案，列出受影响的 tex 行号。

### 3. 写作要求

- 用评语的语言作答（中文评语用中文）。
- Answer 面向审阅人：直接、有依据、不辩解；1–4 句为宜。
- Modify 必须可直接执行：给出 tex 位置、原文、改后文本（保持 LaTeX 语法正确，保留 `\cite`、`\ref`、公式和宏）、理由。
- 改后文本要与上下文衔接，不引入新的术语或未定义符号；涉及数字时以 tex 中的宏/实验结果为准，不编造。
- 若一处修改会牵连其他位置（摘要、引言、结论中的同一论断），在 Modify 的「联动」项列出。

### 4. 写回 `.md`（严格遵守格式，脚本据此解析）

在对应 `## Cxxx` 条目的最后一个字段之后（下一个 `## ` 之前）追加，不要改动已有字段：

```markdown
- Answer: 回答正文（可多行，续行以两个空格缩进）
  续行内容
- Modify:
  - 位置: paper_CN.tex L1066 c1
  - 原文: 一段行驶用标签设定（label-setting）搜索来规划。
  - 改为: 每段行驶（从当前节点到目标节点）用标签设定（label-setting）搜索一次性规划完整路径。
  - 理由: 回应「逐跳还是一次性」的疑问，明确为一次性规划。
  - 联动: L478 摘要中的对应表述
- Status: proposed
```

规则：
- 字段名固定为 `Answer`、`Modify`、`Status`，行首为 `- 字段名:`；多行内容的每一续行都以**两个空格**开头。
- 不需要的字段可省略（只有 Answer 或只有 Modify 都可以）。
- 一条有多处修改时，在 Modify 下重复「位置/原文/改为/理由」组，组间可用 `  ---` 分隔。
- `Status` 取值：`proposed`（已给方案，待用户确认）、`agreed`（用户认可）、`applied`（已改入 tex）、`rejected`（决定不改）。新写的一律 `proposed`。
- 已有 Answer/Modify 的条目，若用户要求重写，则替换这两个字段而不是追加第二份。

### 5. 同步 `.json`

`.md` 写完后运行：

```text
python script/pdf_review/extract_com_mapping.py <xxx_comments.md> --sync-only
```

它会把 `.md` 中的 Answer、Modify、Status 等字段同步到同名 `.json`，保留原有的 tex 映射结果。
无法运行 Python 时，才直接编辑 `.json`：在对应 `id` 的对象中加入 `"Answer"`、`"Modify"`、`"Status"` 字符串字段，内容与 `.md` 一致（换行写成 `\n`）。

### 6. 应用修改（仅当用户明确要求）

用户说「应用 C0xx 的修改」或「把 agreed 的都改进 tex」时：

1. 按 Modify 中的位置找到原文；先确认 tex 当前内容仍与「原文」一致（tex 可能已被改过），不一致就报告，不要强改。
2. 用精确替换修改 tex，保证 LaTeX 可编译（括号、`\ref`、宏不破坏）。
3. 把该条 `Status` 改为 `applied`，再运行第 5 节的同步命令。
4. tex 改动后行号会变化，后续条目以 `原文` 文本定位为准，不要只依赖 `tex_line`。

### 7. 每轮结束时向用户汇报

- 处理了哪些编号；其中 Answer / Modify / 两者兼有各多少条。
- 需要用户拍板的条目（不采纳审阅意见的、改动较大的、涉及全文联动的），逐条用一句话说明。
- 定位失败或配对存疑的条目。
