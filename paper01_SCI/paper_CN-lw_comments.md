# PDF 审阅批注清单：paper_CN-lw.pdf

- source_pdf: C:\Users\analy\Desktop\AI_Folder\paper01_SCI\paper_CN-lw.pdf
- generated: 2026-11-05 13:14
- total: 212（有评语 87，仅标记无评语 125）
- 字段：line_src=lineno 表示 PDF 页边印刷行号，page_row 表示本页第几行；col 从 1 起；len 为选中字符数；context 为所在整行原文；comment=none 表示只做了标记未写评语；标尺式行号可能有 ±1 偏差
- 便签与高亮的配对为启发式推断，可直接修改本文件纠正；后续脚本以本文件为准

## C001
- page: 1
- line: 1
- line_src: lineno
- col: 1
- len: 31
- kind: Highlight
- author: xchlw
- text: 柔性作业车间调度与AGV 无冲突路由的路由内嵌评价闭环双层框架
- context: 柔性作业车间调度与AGV 无冲突路由的路由内嵌评价闭环双层框架
- comment: none

## C002
- page: 1
- line: 7-8
- line_src: lineno
- col: 50
- len: 15
- kind: Text+Highlight
- author: xchlw
- text: 当有限车队共享稀疏的走廊网络时
- context: 柔性作业车间的加工与运输一体化调度通常将行驶时间设为按位置索引的常数矩阵，即假定车辆之间互不干扰。当有限车队 共享稀疏的走廊网络时，行驶时间不再是固定数据，而是路由决策的结果（本文的路由指车辆在走廊网络上的无冲突路径规
- comment: 描述要通俗易懂、简明扼要 / 用加工机器代替机械臂
- more_targets:
  - page=1 | line=8-9 | line_src=lineno | col=23 | len=35 | text=，而是路由决策的结果（本文的路由指车辆在走廊网络上的无冲突路径规划）； | context=共享稀疏的走廊网络时，行驶时间不再是固定数据，而是路由决策的结果（本文的路由指车辆在走廊网络上的无冲突路径规 划）；一个工件对走廊的占用会影响其他工件的作业时间。本文研究如下问题：在运输耗时超过加工、拥堵集中于少数共享
  - page=1 | line=9-10 | line_src=lineno | col=36 | len=25 | text=在运输耗时超过加工、拥堵集中于少数共享走廊的车间中 | context=划）；一个工件对走廊的占用会影响其他工件的作业时间。本文研究如下问题：在运输耗时超过加工、拥堵集中于少数共享 走廊的车间中，每道工序可由若干台能力同构、效率异构的机械臂之一加工，同时AGV 须在该网络上无冲突行驶。机器柔
- Answer: 采纳。摘要第一段句子长、术语密（「按位置索引的常数矩阵」「稀疏的走廊网络」「能力同构、效率异构」），改为通俗表述；「机械臂」统一改为「加工机器」（全文 73 行共 88 处，另有 11 行「快臂/慢臂」）。
- Modify:
  - 位置: paper_CN.tex L472-475
  - 原文: 柔性作业车间的加工与运输一体化调度通常将行驶时间设为按位置索引的常数矩阵……以往工作未将这一权衡纳入搜索的评价目标加以度量。
  - 改为: 柔性作业车间的加工与运输一体化调度通常把 AGV 的行驶时间视为常数，即假定车辆之间互不干扰。但当多辆 AGV 共用少量单车道走廊时，车辆须相互让行，行驶时间取决于路径规划的结果，一个工件的运输还会推迟其他工件的作业；按常数行驶时间排出的计划在实际执行时因此会延误，甚至选错加工机器。本文研究这样一类车间：运输耗时超过加工，拥堵集中在少数共享走廊上，每道工序可在多台效率不同的加工机器中任选其一，AGV 须无冲突行驶。此时，若通往快速机器的走廊拥堵，选一台较慢但通行顺畅的机器可能更优；已有方法在搜索中未计入这一权衡。
  - 理由: 通俗、简明；同时回答 C003「导致什么后果」。
  ---
  - 位置: paper_CN.tex 全文
  - 原文: 机械臂（88 处）；快臂/慢臂（11 行）
  - 改为: 加工机器（首次出现后可简称「机器」）；快机/慢机（或「快速机器/慢速机器」）
  - 理由: 审阅意见：用加工机器代替机械臂，更符合 FJSP 文献用语。
  - 联动: 图 1（fig/fig_motivating_CN.py）与图 2（fig/fig_framework_CN.py）中的文字标签需同步修改后重新生成；符号表 tab:notation 中「机械臂集合」等同步改。
- Status: applied

## C003
- page: 1
- line: 10
- line_src: lineno
- col: 27
- len: 3
- kind: Text+Highlight
- author: xchlw
- text: 机械臂
- context: 走廊的车间中，每道工序可由若干台能力同构、效率异构的机械臂之一加工，同时AGV 须在该网络上无冲突行驶。机器柔
- comment: 导致什么后果？
- Answer: 配对存疑：评语被配到「机械臂」，按位置应针对第 6 行「即假定车辆之间互不干扰」。后果：按常数矩阵排出的计划在共享走廊上执行时，车辆须让行，实际完工时间长于计划；更严重的是，矩阵评价下更优的指派在实际中可能更差（图 1：矩阵下选快机 41 对 54，无冲突路由下变为 95 对 60）。
- Modify:
  同 C002：改写后的摘要第一段已加入「按常数行驶时间排出的计划在实际执行时因此会延误，甚至选错加工机器」。
- Status: applied

## C004
- page: 1
- line: 11
- line_src: lineno
- col: 20
- len: 3
- kind: Highlight
- author: xchlw
- text: 机械臂
- context: 性使这一耦合成为可操作的权衡：通往快速机械臂的走廊拥堵时，一台较慢但连通性更好的机械臂可能是更优指派。以往工
- comment: none

## C005
- page: 1
- line: 11
- line_src: lineno
- col: 41
- len: 2
- kind: Highlight
- author: xchlw
- text: 机械
- context: 性使这一耦合成为可操作的权衡：通往快速机械臂的走廊拥堵时，一台较慢但连通性更好的机械臂可能是更优指派。以往工
- comment: none

## C006
- page: 1
- line: 11-12
- line_src: lineno
- col: 52
- len: 24
- kind: Text+Highlight
- author: xchlw
- text: 以往工作未将这一权衡纳入搜索的评价目标加以度量。
- context: 性使这一耦合成为可操作的权衡：通往快速机械臂的走廊拥堵时，一台较慢但连通性更好的机械臂可能是更优指派。以往工 作未将这一权衡纳入搜索的评价目标加以度量。
- comment: AGV谁指派？ / 上层的指派方法？
- Answer: 配对存疑：评语应针对第 13 行「上层决定机器指派与工序排序，下层以时间窗预约生成无冲突路径」。AGV 指派不在上层染色体中，而是在解码时为每个运输任务按预约表感知派遣选车（第 4.4 节）；上层的方法是文化基因算法（遗传算法 + 局部搜索，第 4.3、4.7、4.8 节）。摘要未交代这两点，确实不清楚。
- Modify:
  - 位置: paper_CN.tex L477
  - 原文: 本文提出\emph{闭环双层框架}：上层决定机器指派与工序排序，下层以时间窗预约生成无冲突路径；下层的路由信息以两种方式进入决策。
  - 改为: 本文提出\emph{闭环双层框架}：上层用文化基因算法（遗传算法结合局部搜索）搜索机器指派与工序排序；解码时为每个运输任务选派 AGV；下层以时间窗预约为所选 AGV 规划无冲突路径。下层的路由信息以两种方式进入决策。
  - 理由: 明确 AGV 由谁指派、上层用什么方法。
  - 联动: 1.3 节 L635 同步（见 C047）
- Status: applied

## C007
- page: 1
- line: 13
- line_src: lineno
- col: 5
- len: 6
- kind: Highlight
- author: xchlw
- text: 闭环双层框架
- context: 本文提出闭环双层框架：上层决定机器指派与工序排序，下层以时间窗预约生成无冲突路径；下层的路由信息以两种方
- comment: none

## C008
- page: 1
- line: 14
- line_src: lineno
- col: 9
- len: 7
- kind: Highlight
- author: xchlw
- text: 为路由内嵌评价
- context: 式进入决策。其一为路由内嵌评价（评价通路）：每个候选解的适应度取自下层无冲突路由后的完工时间，让行延误因此进
- comment: none

## C009
- page: 1
- line: 14
- line_src: lineno
- col: 15
- len: 8
- kind: Highlight
- author: xchlw
- text: 价（评价通路）：
- context: 式进入决策。其一为路由内嵌评价（评价通路）：每个候选解的适应度取自下层无冲突路由后的完工时间，让行延误因此进
- comment: none

## C010
- page: 1
- line: 14
- line_src: lineno
- col: 48
- len: 4
- kind: Text+Highlight
- author: xchlw
- text: 让行延误
- context: 式进入决策。其一为路由内嵌评价（评价通路）：每个候选解的适应度取自下层无冲突路由后的完工时间，让行延误因此进
- comment: 评价方法？
- more_targets:
  - page=1 | line=17-18 | line_src=lineno | col=48 | len=22 | text=两项加速——可采纳下界剪枝与胜者路径复用—— | context=选实际送达最早的车辆，而非按假定一路畅通的行驶时间估算选车。为使其单次评价保持低开销，本文给出两项加速——可 采纳下界剪枝与胜者路径复用——并证明它们只减少计算量，不改变所选车辆与最终时间表。
- Answer: 评价方法：把候选解（机器指派 + 工序序列）交给解码器，按序生成运输任务、选车，并用时间窗 Dijkstra 逐一规划无冲突路径，全部任务完成后得到含让行等待的完工时间，作为该候选解的适应度。摘要只说「取自下层无冲突路由后的完工时间」，过程不清楚。
- Modify:
  - 位置: paper_CN.tex L478
  - 原文: 其一为\emph{路由内嵌评价}（评价通路）：每个候选解的适应度取自下层无冲突路由后的完工时间，让行延误因此进入搜索的优化目标，而非仅用于事后校验。
  - 改为: 其一为\emph{路由内嵌评价}（评价通路）：对每个候选解，先由解码器生成运输任务并逐一完成无冲突路由，再以所得完工时间（含让行等待）作为其适应度；让行延误因此直接进入搜索目标，而非仅用于事后校验。
  - 理由: 交代评价的具体过程。
- Status: applied

## C011
- page: 1
- line: 16
- line_src: lineno
- col: 20
- len: 14
- kind: Highlight
- author: xchlw
- text: 其二为预约表感知派遣（决策通
- context: 入搜索的优化目标，而非仅用于事后校验。其二为预约表感知派遣（决策通路）：选车时在当前预约表上对两段运输做试算，
- comment: none

## C012
- page: 1
- line: 24
- line_src: lineno
- col: 64
- len: 10
- kind: Highlight
- author: xchlw
- text: 预约表感知的车辆派遣
- context: Additional Key Words and Phrases: 柔性作业车间调度，无冲突路由，闭环双层框架，路由内嵌评价，预约表感知的车辆派遣
- comment: none

## C013
- page: 1
- line: 32
- line_src: lineno
- col: 1
- len: 10
- kind: Text
- author: xchlw
- text: 1.1研究背景与动机
- context: 1.1研究背景与动机
- comment: 路网描述不够清晰。拥堵？碰撞？排队？
- Answer: 采纳。本文的路网：节点为上下料点、机器工位与路口，边为单车道走廊。为避免碰撞与迎面死锁，一条走廊同一时刻只允许一辆车（排他）；其余车辆在节点停靠位排队等待；「拥堵」即多车争用同一走廊而产生的等待。引言中未先交代这些概念就使用了「走廊」「拥堵」「让行」。
- Modify:
  - 位置: paper_CN.tex L564 末尾（「单车道路段无法在同一时刻被双向通行；」之后）
  - 原文: （新增）
  - 改为: 本文把车间路网抽象为图：节点为上下料点、机器工位与路口，边为单车道走廊。为避免碰撞与迎面死锁，一条走廊同一时刻只允许一辆车通行，其余车辆在节点处的停靠位排队等待；这种因争用走廊而产生的等待，即本文所说的拥堵。
  - 理由: 先定义路网、碰撞、排队与拥堵，再展开动机。
- Status: applied

## C014
- page: 1
- line: 35
- line_src: lineno
- col: 4
- len: 30
- kind: Highlight
- author: xchlw
- text: 可从按位置对索引的矩阵中读出。这是文献中的主流约定[22]，
- context: 常数，可从按位置对索引的矩阵中读出。这是文献中的主流约定[22]，近期的模型仍普遍沿用[7, 14, 16]。当车
- comment: none

## C015
- page: 1
- line: 35-36
- line_src: lineno
- col: 56
- len: 33
- kind: Highlight
- author: xchlw
- text: 当车队规模相对于通道网络足够小、车辆彼此很少相遇时，该假设是合理的
- context: 常数，可从按位置对索引的矩阵中读出。这是文献中的主流约定[22]，近期的模型仍普遍沿用[7, 14, 16]。当车 队规模相对于通道网络足够小、车辆彼此很少相遇时，该假设是合理的。然而实际车间并非如此构造：少量车
- comment: none

## C016
- page: 1
- line: 43
- line_src: lineno
- col: 36
- len: 12
- kind: Highlight
- author: xchlw
- text: , 230240012@
- context: Authors’ Contact Information: Qi Yu, 230240012@seu.edu.cn, School of Cyber Science and Engineering, Southeast University, Nanjing, Jiangsu, PR
- comment: none

## C017
- page: 2
- line: 53
- line_src: lineno
- col: 15
- len: 9
- kind: Highlight
- author: xchlw
- text: 距离计算的行驶时间
- context: 次运输的耗时由两部分组成：按距离计算的行驶时间，以及因走廊被其他车辆占用而在停靠点等待或绕行的时
- comment: none

## C018
- page: 2
- line: 53
- line_src: lineno
- col: 44
- len: 5
- kind: Text+Highlight
- author: xchlw
- text: 或绕行的时
- context: 次运输的耗时由两部分组成：按距离计算的行驶时间，以及因走廊被其他车辆占用而在停靠点等待或绕行的时
- comment: 绕行就不考虑按距离计算了？
- Answer: 绕行同样按距离计算。原文把绕行多出的时间归入第二部分，是因为它和等待一样由争用引起，但写法容易误解为绕行不按距离计。
- Modify:
  - 位置: paper_CN.tex L567
  - 原文: 由此，一次运输的耗时由两部分组成：按距离计算的行驶时间，以及因走廊被其他车辆占用而在停靠点等待或绕行的时间。
  - 改为: 由此，一次运输的耗时由两部分组成：沿最短路行驶的时间，以及因走廊被其他车辆占用而产生的额外时间——在停靠点等待，或改走更长路径而多出的行驶时间。
  - 理由: 消除「绕行不按距离计算」的误解。
- Status: applied

## C019
- page: 2
- line: 54
- line_src: lineno
- col: 3
- len: 20
- kind: Highlight
- author: xchlw
- text: 后者使一个工件的运输会推迟其他工件的作业
- context: 间。后者使一个工件的运输会推迟其他工件的作业。
- comment: none

## C020
- page: 2
- line: 56
- line_src: lineno
- col: 14
- len: 20
- kind: Text+Highlight
- author: xchlw
- text: 只有在调度器可以调整作业指派时才有优化空
- context: 这种在工件之间传递的延误，只有在调度器可以调整作业指派时才有优化空间，而机器柔性恰好允许改派机
- comment: 太绝对，实时、局部优化也是可以的
- Answer: 采纳。路由层的实时避让、局部调整也能缓解延误；本文的论点应是：能改派机器时，可从源头改变运输去向，优化空间更大。
- Modify:
  - 位置: paper_CN.tex L569
  - 原文: 这种在工件之间传递的延误，只有在调度器可以调整作业指派时才有优化空间，而机器柔性恰好允许改派机械臂（即更换工序的加工地点）。
  - 改为: 这种在工件之间传递的延误，可以在路由层通过实时避让或局部调整加以缓解；若调度器还能调整作业指派，则可从源头改变运输任务的去向，优化空间更大。机器柔性正允许这种改派（即更换工序的加工机器）。
  - 理由: 去掉绝对化表述。
- Status: applied

## C021
- page: 2
- line: 57
- line_src: lineno
- col: 1
- len: 48
- kind: Text
- author: xchlw
- text: 械臂（即更换工序的加工地点）。当一道工序可由某个可选集合中的任一机械臂加工、且加工时间取决于所选
- context: 械臂（即更换工序的加工地点）。当一道工序可由某个可选集合中的任一机械臂加工、且加工时间取决于所选
- comment: 啰嗦
- Answer: 采纳，压缩为三句。
- Modify:
  - 位置: paper_CN.tex L569-575（「当一道工序可由某个可选集合中……」至「……等待与绕行不同。」）
  - 原文: 当一道工序可由某个可选集合中的任一机械臂加工、且加工时间取决于所选机械臂时……通道网络中的不同路径使车辆途中的等待与绕行不同。
  - 改为: 当一道工序可由多台加工时间不同的机器加工时，指派同时决定了运输目的地与加工时长。例如，一道工序可交给远端的快速机器，也可交给靠近上下料点的慢速机器：按常数运输时间，比较的只是两者「加工 + 行驶」之和；存在走廊争用时，通往快速机器的走廊可能正被其他车辆占用，这部分等待从常数矩阵中看不出来，慢速但通行顺畅的机器反而可能更优，且结论随拥堵程度而变。
  - 理由: 删除重复论述（「两个要素同时存在」一句与前文重复）。
- Status: applied

## C022
- page: 2
- line: 66-67
- line_src: lineno
- col: 5
- len: 51
- kind: Text+Highlight
- author: xchlw
- text: 一个可复算的最小算例表明：同一对指派，用常数运输时间矩阵评价时选快臂更优，用无冲突路由评价时选慢臂更优
- context: 图1 用一个可复算的最小算例表明：同一对指派，用常数运输时间矩阵评价时选快臂更优，用无冲突路由评 价时选慢臂更优。算例共4 个工件、2 辆AGV：焦点工件J1 的一道工序可选M1（𝑡𝑃= 3）或M2（𝑡𝑃= 14），另
- comment: 先讲例子，再给出结论
- Answer: 采纳：先给出算例，再在算例末尾给出结论。
- Modify:
  - 位置: paper_CN.tex L578
  - 原文: 图~\ref{fig:motivating} 用一个可复算的最小算例表明：同一对指派，用常数运输时间矩阵评价时选快臂更优，用无冲突路由评价时选慢臂更优。
  - 改为: 下面用一个可复算的最小算例（图~\ref{fig:motivating}）说明这一权衡。
  - 理由: 先讲例子。
  ---
  - 位置: paper_CN.tex L603 末尾
  - 原文: 两种评价下，机器指派与工序顺序完全相同，不同的只是完工时间的算法：……
  - 改为: （在该句后新增）可见，对同一对指派，用常数运输时间矩阵评价时快机更优，用无冲突路由评价时慢机更优，两种评价给出相反的选择。
  - 理由: 再给结论。
- Status: applied

## C023
- page: 2
- line: 67
- line_src: lineno
- col: 25
- len: 4
- kind: Highlight
- author: xchlw
- text: 焦点工件
- context: 价时选慢臂更优。算例共4 个工件、2 辆AGV：焦点工件J1 的一道工序可选M1（𝑡𝑃= 3）或M2（𝑡𝑃= 14），另
- comment: none

## C024
- page: 2
- line: 67
- line_src: lineno
- col: 34
- len: 3
- kind: Text+Highlight
- author: xchlw
- text: 道工序
- context: 价时选慢臂更优。算例共4 个工件、2 辆AGV：焦点工件J1 的一道工序可选M1（𝑡𝑃= 3）或M2（𝑡𝑃= 14），另
- comment: 加工机器之间的移动？
- more_targets:
  - page=2 | line=71 | line_src=lineno | col=10 | len=24 | text=，「𝑡= 𝑥」表示自开始（𝑡= 0）起算的时刻。 | context=时𝑥」表示一段时长，「𝑡= 𝑥」表示自开始（𝑡= 0）起算的时刻。
  - page=2 | line=72-73 | line_src=lineno | col=16 | len=39 | text=底部是焦点工件J1 单独一件的往返时间，用来确定快、慢两臂加工时间至少要差多少 | context=图1 中的数字分两种：(a) 底部是焦点工件J1 单独一件的往返时间，用来确定快、慢两臂加工时间至少要差 多少；(b) 的柱高是四个工件一起排产时的整例完工时间，用来比较两种评价方式给出的指派次序。图1(a) 底
- Answer: 本例中每个工件只有一道工序，运输只有 v0→机器→v0 的往返，不涉及机器之间的移动；一般问题中，前后工序换机器时才产生机器之间的运输（式 (1)）。
- Modify:
  - 位置: paper_CN.tex L579（「另三个背景工件只能在 M3 上加工，成品须运回上下料点 $v_0$。」之后）
  - 原文: （新增）
  - 改为: 本例每个工件只有一道工序，因此运输只有自 $v_0$ 往返机器的两段，不涉及机器之间的搬运。
  - 理由: 回答读者疑问。
- Status: applied

## C025
- page: 2
- line: 73
- line_src: lineno
- col: 29
- len: 17
- kind: Highlight
- author: xchlw
- text: 用来比较两种评价方式给出的指派次序
- context: 多少；(b) 的柱高是四个工件一起排产时的整例完工时间，用来比较两种评价方式给出的指派次序。图1(a) 底
- comment: none

## C026
- page: 2
- line: 78
- line_src: lineno
- col: 14
- len: 30
- kind: Highlight
- author: xchlw
- text: 当19 < 6 + 𝑡s𝑃low，即𝑡s𝑃low > 13；
- context: 其余车辆时，快臂占优当且仅当19 < 6 + 𝑡s𝑃low，即𝑡s𝑃low > 13；本例在𝜏= 6、𝑡f𝑃ast = 3 下取𝑡s𝑃low = 14，两种指派
- comment: none

## C027
- page: 2
- line: 82
- line_src: lineno
- col: 38
- len: 12
- kind: Highlight
- author: xchlw
- text: 由与全文相同的解码器求得
- context: 图1(b) 的柱高为整例完工时间𝐶max，即最晚一件成品返回𝑣0 的时刻，由与全文相同的解码器求得。四件工
- comment: none

## C028
- page: 2
- line: 86
- line_src: lineno
- col: 16
- len: 8
- kind: Highlight
- author: xchlw
- text: 廊让行不进入评价
- context: 在常数矩阵下，车辆互不干扰，走廊让行不进入评价。若将J1 指派至M1，则𝐶max = 41：第一波中J1→M1
- comment: none

## C029
- page: 2
- line: 93
- line_src: lineno
- col: 1
- len: 15
- kind: Highlight
- author: xchlw
- text: 将同一对指派改由无冲突路由评价
- context: 将同一对指派改由无冲突路由评价。指派M1 时𝐶max = 95：J1 自身的畅通往返时间仍为19，但其去程在
- comment: none

## C030
- page: 3
- line: 124
- line_src: lineno
- col: 21
- len: 11
- kind: Highlight
- author: xchlw
- text: 两种评价下给出相反次序
- context: Fig. 1. 动机算例：同一指派决策在两种评价下给出相反次序。(a) 通往快臂M1 的唯一通路是排他干道（𝜏= 6），慢臂M2 位
- comment: none

## C031
- page: 3
- line: 127
- line_src: lineno
- col: 44
- len: 12
- kind: Highlight
- author: xchlw
- text: 差值由−13 变为+35
- context: 矩阵下𝐶max 为41 对54，选快臂；无冲突路由下同一对指派为95 对60，选慢臂，差值由−13 变为+35。图中时间均为无量
- comment: none

## C032
- page: 3
- line: 127
- line_src: lineno
- col: 16
- len: 32
- kind: Highlight
- author: xchlw
- text: 在围绕该算例的1200 组参数中，有205 组（17%）出现反转
- context: 纲时间单位。本图为存在性示例；在围绕该算例的1200 组参数中，有205 组（17%）出现反转。
- comment: none

## C033
- page: 3
- line: 131
- line_src: lineno
- col: 1
- len: 11
- kind: Text
- author: xchlw
- text: 1.2与已有工作的差距
- context: 1.2与已有工作的差距
- comment: 已有工作存在问题没讲清楚
- Answer: 采纳。1.2 节列举了现有工作「覆盖了哪些」，但没有直接点明「存在什么问题」。建议开门见山列出三个问题，再说明本文聚焦的场景。
- Modify:
  - 位置: paper_CN.tex L625-631（替换「现有工作大多只覆盖其中一部分……」至「……尚缺少同等算力下的度量。」）
  - 原文: 现有工作大多只覆盖其中一部分：……尚缺少同等算力下的度量。
  - 改为: 现有工作存在以下三个问题。其一，带运输时间的柔性作业车间调度以常数运输时间矩阵表示行驶~\cite{xin2025review,meng2025cp,qin2026knowledge}，假定车辆互不干扰，排出的计划在单车道走廊上执行时会因让行而延误，矩阵评价下更优的指派实际可能更差（图~\ref{fig:motivating}）。其二，无冲突路径规划与派车的研究~\cite{gao2023mapf,zhang2024guidance,kim2026congestion} 中，任务的起点、终点与释放时刻由外部给定，只能被动避让，无法通过改派机器从源头减少争用。其三，同时考虑二者的工作中，精确方法（van Os 与 Basten~\cite{vanos2026exact}）只能求解小规模算例；启发式或先排产、后消解冲突（Sun 等~\cite{sun2023integrated}），或只回传一次运输时长而不修改指派（Li 等~\cite{li2026framework}），或在解码中嵌入路由但未度量其收益与代价（Lyu 等~\cite{lyu2019approach}）。因此，在运输耗时超过加工、拥堵集中于少数共享走廊的车间中，把让行延误计入搜索评价能带来多少收益、需付出多少计算代价，尚无同等算力下的度量。
  - 理由: 直接讲出存在的问题。
  - 联动: 同时回应 C035、C038
- Status: applied

## C034
- page: 3
- line: 131
- line_src: lineno
- col: 4
- len: 8
- kind: Highlight
- author: xchlw
- text: 与已有工作的差距
- context: 1.2与已有工作的差距
- comment: none

## C035
- page: 3
- line: 132
- line_src: lineno
- col: 50
- len: 1
- kind: Text+Highlight
- author: xchlw
- text: ，
- context: 贴近实际AGV 车间的设定要求三者同时成立：工序可选机器且加工时间随机器而变；车辆在显式路网上行驶，
- comment: 存在啥问题？要直接讲出存在的问题
- more_targets:
  - page=3 | line=132 | line_src=lineno | col=50 | len=1 | text=， | context=贴近实际AGV 车间的设定要求三者同时成立：工序可选机器且加工时间随机器而变；车辆在显式路网上行驶，
- Answer: 同 C033（配对的两处高亮只是逗号，评语针对第 132 行整句）。
- Status: applied

## C036
- page: 3
- line: 133
- line_src: lineno
- col: 1
- len: 4
- kind: Highlight
- author: xchlw
- text: 走廊排他
- context: 走廊排他，行驶时间由各车路径共同决定，而非取自常数矩阵；车辆之间无冲突。现有工作大多只覆盖其中一
- comment: none

## C037
- page: 3
- line: 133
- line_src: lineno
- col: 14
- len: 4
- kind: Highlight
- author: xchlw
- text: 径共同决
- context: 走廊排他，行驶时间由各车路径共同决定，而非取自常数矩阵；车辆之间无冲突。现有工作大多只覆盖其中一
- comment: none

## C038
- page: 3
- line: 133
- line_src: lineno
- col: 37
- len: 12
- kind: Text+Highlight
- author: xchlw
- text: 现有工作大多只覆盖其中一
- context: 走廊排他，行驶时间由各车路径共同决定，而非取自常数矩阵；车辆之间无冲突。现有工作大多只覆盖其中一
- comment: 与实际相符吗？
- more_targets:
  - page=3 | line=135 | line_src=lineno | col=32 | len=5 | text=车辆互不干 | context=部分：带运输时间的柔性作业车间调度以常数运输时间矩阵表示行驶，车辆互不干扰；无冲突路径规划处理车
- Answer: 相符：Xin 等综述指出常数矩阵是该领域主导的建模方式，近期工作（Meng、Qin、Jafarian 等）仍沿用；MAPF 与派车工作的任务均为外生输入（表 1）。但「大多」需有引用支撑，原文此处没有引用。
- Modify:
  同 C033：改写后的句子已在两类工作后分别加上引用。
- Status: applied

## C039
- page: 3
- line: 135
- line_src: lineno
- col: 1
- len: 2
- kind: Highlight
- author: xchlw
- text: 部分
- context: 部分：带运输时间的柔性作业车间调度以常数运输时间矩阵表示行驶，车辆互不干扰；无冲突路径规划处理车
- comment: none

## C040
- page: 3
- line: 136
- line_src: lineno
- col: 25
- len: 17
- kind: Highlight
- author: xchlw
- text: 不随排产改变。同时满足三者的工作较
- context: 辆行驶，但任务的起点、终点与释放时刻由外部给定，不随排产改变。同时满足三者的工作较少。van Os 与
- comment: none

## C041
- page: 3
- line: 140
- line_src: lineno
- col: 1
- len: 57
- kind: Text
- author: xchlw
- text: 对象的一类场景：运输耗时超过加工（𝑇𝑡̄/𝑇 𝑝̄≈4.0，常用公开算例最高仅0.12），机械臂之间以单车道走廊相
- context: 对象的一类场景：运输耗时超过加工（𝑇𝑡̄/𝑇 𝑝̄≈4.0，常用公开算例最高仅0.12），机械臂之间以单车道走廊相
- comment: 不超过就可以不用考虑？
- Answer: 不是不用考虑。运输不超过加工时争用仍存在，但运输通常不是瓶颈，让行等待对完工时间的影响较小，闭环收益预期也较小（本文实验中争用强度最低的网格算例收益也最小）。本文聚焦高比值，是为了让争用成为主要约束、便于度量；低比值区间未单独测试，应在文中说明。
- Modify:
  - 位置: paper_CN.tex L628（「……拥堵集中在少数共享走廊上。」之后）
  - 原文: （新增）
  - 改为: 运输不超过加工时，车辆争用依然存在，但通常不是主要瓶颈，闭环带来的收益预期较小；本文实验未覆盖该区间，见第~\ref{sec:limitations}~节。
  - 理由: 说明适用范围，避免被理解为「不超过就不用考虑」。
  - 联动: 第 6 章局限小节补充一条「未测试 $\bar{T}_t/\bar{T}_p\le1$ 的车间」
- Status: applied

## C042
- page: 3
- line: 140
- line_src: lineno
- col: 1
- len: 57
- kind: Text
- author: xchlw
- text: 对象的一类场景：运输耗时超过加工（𝑇𝑡̄/𝑇 𝑝̄≈4.0，常用公开算例最高仅0.12），机械臂之间以单车道走廊相
- context: 对象的一类场景：运输耗时超过加工（𝑇𝑡̄/𝑇 𝑝̄≈4.0，常用公开算例最高仅0.12），机械臂之间以单车道走廊相
- comment: 是否普遍？
- Answer: 需要证据。这类场景出现在搬运距离长、加工节拍短的车间（如脊式布局的量产厂房，已引 suh2022spine），但不是所有车间都如此。文中目前只说明公开算例未覆盖该场景，没有说明它在实际中多常见。建议作者补充 1–2 篇实际案例或现场数据；若无，则弱化表述。
- Modify:
  - 位置: paper_CN.tex L628
  - 原文: 但聚焦于已有工作未作为专门研究对象的一类场景：
  - 改为: 但聚焦于已有工作未作为专门研究对象、而在搬运距离长且加工节拍短的车间中常见的一类场景~\cite{suh2022spine}（【待作者补充实际案例文献】）：
  - 理由: 回应「是否普遍」；若找不到依据，删去「常见」二字。
- Status: applied（需作者补充文献）

## C043
- page: 3
- line: 142
- line_src: lineno
- col: 23
- len: 16
- kind: Highlight
- author: xchlw
- text: 以争用强度为受控变量考察这一权衡
- context: 约束，同一指派的优劣会随拥堵程度而改变；本文以争用强度为受控变量考察这一权衡，并面向精确分解难以
- comment: none

## C044
- page: 3
- line: 142
- line_src: lineno
- col: 41
- len: 8
- kind: Highlight
- author: xchlw
- text: 面向精确分解难以
- context: 约束，同一指派的优劣会随拥堵程度而改变；本文以争用强度为受控变量考察这一权衡，并面向精确分解难以
- comment: none

## C045
- page: 3
- line: 144
- line_src: lineno
- col: 1
- len: 5
- kind: Highlight
- author: xchlw
- text: 求解的规模
- context: 求解的规模。在这一规模上，已有启发式或先排产、后消解冲突（Sun 等[19]），或把路径层实现的运输时长回
- comment: none

## C046
- page: 3
- line: 145
- line_src: lineno
- col: 23
- len: 6
- kind: Highlight
- author: xchlw
- text: 解码中嵌入路
- context: 传一次但不修改指派（Li 等[10]），或在解码中嵌入路由但未度量其收益与代价（Lyu 等[13]）。因此，在这一
- comment: none

## C047
- page: 3
- line: 146-147
- line_src: lineno
- col: 6
- len: 74
- kind: Text+Highlight
- author: xchlw
- text: 派如何在「快而路堵」与「慢而路通」的机械臂之间权衡，将让行延误计入搜索评价能带来多少收益、在何种争用程度下值得付出其计算代价，尚缺少同等算力下的度量
- context: 设定下，指派如何在「快而路堵」与「慢而路通」的机械臂之间权衡，将让行延误计入搜索评价能带来多少收 益、在何种争用程度下值得付出其计算代价，尚缺少同等算力下的度量。
- comment: AGV指派呢？采用的方法？
- more_targets:
  - page=3 | line=151-152 | line_src=lineno | col=46 | len=50 | text=；下层的路由信息以评价与决策两种方式进入排产（详见下两段），本文分别度量这两种方式对完工时间的贡献。 | context=针对上述缺口，本文采用双层结构：上层决定机器指派与工序排序，下层以时间窗预约生成无冲突路径；下层 的路由信息以评价与决策两种方式进入排产（详见下两段），本文分别度量这两种方式对完工时间的贡献。
- Answer: AGV 指派在解码时按预约表感知派遣决定（不由上层搜索）；上层方法为文化基因算法。1.3 节开头未交代，补上。
- Modify:
  - 位置: paper_CN.tex L635
  - 原文: 针对上述缺口，本文采用双层结构：上层决定机器指派与工序排序，下层以时间窗预约生成无冲突路径；
  - 改为: 针对上述缺口，本文采用双层结构：上层用文化基因算法搜索机器指派与工序排序；解码时逐个生成运输任务并为其选派 AGV；下层以时间窗预约为 AGV 规划无冲突路径；
  - 理由: 明确 AGV 指派与上层方法。
  - 联动: 与 C006 摘要改写一致
- Status: applied

## C048
- page: 3
- line: 152
- line_src: lineno
- col: 1
- len: 47
- kind: Text
- author: xchlw
- text: 的路由信息以评价与决策两种方式进入排产（详见下两段），本文分别度量这两种方式对完工时间的贡献。
- context: 的路由信息以评价与决策两种方式进入排产（详见下两段），本文分别度量这两种方式对完工时间的贡献。
- comment: 文章的目的是啥？
- Answer: 目的有二：一是让无冲突路由的结果直接参与机器指派与排序的决策；二是在同等算力下度量这样做的收益与计算代价。原文未明说。
- Modify:
  - 位置: paper_CN.tex L635 段首
  - 原文: （新增）
  - 改为: 本文的目的是：在走廊争用显著的柔性作业车间中，让无冲突路由的结果直接参与机器指派与排序的决策，并在同等算力下回答这样做能降低多少完工时间、需付出多少计算代价。
  - 理由: 开宗明义。
- Status: applied

## C049
- page: 3
- line: 154-155
- line_src: lineno
- col: 5
- len: 58
- kind: Text+Highlight
- author: xchlw
- text: 将每个候选解的适应度取为下层完成无冲突路由后的完工时间，让行等待因此进入搜索所优化的目标，而不再是事后做可行性校验。
- context: 评价通路将每个候选解的适应度取为下层完成无冲突路由后的完工时间，让行等待因此进入搜索所优化的 目标，而不再是事后做可行性校验。一次无冲突解码的计算开销比按不计争用的最短路时间解码高出一个数量
- comment: 方法没讲清楚
- Answer: 采纳。1.3 节以概念为主，缺少「输入→上层→解码→下层→输出」的流程，读者难以把握方法如何运转。
- Modify:
  - 位置: paper_CN.tex L635 段末（「……本文分别度量这两种方式对完工时间的贡献。」之后）
  - 原文: （新增）
  - 改为: 具体流程为：(1) 上层种群中的每个个体编码一组机器指派与工序序列；(2) 解码器按工序序列依次生成运输任务，并为每个任务选派 AGV；(3) 下层用时间窗 Dijkstra 在预约表上为该 AGV 规划无冲突路径并写入预约表；(4) 全部任务完成后得到含让行等待的完工时间，作为该个体的适应度回传上层；(5) 上层据此进行选择、交叉、变异与局部搜索，直至挂钟预算用完。
  - 理由: 补充方法流程。
- Status: applied

## C050
- page: 4
- line: 157
- line_src: lineno
- col: 4
- len: 8
- kind: Highlight
- author: xchlw
- text: ；在固定算力下，
- context: 级以上；在固定算力下，更高的单次评价开销会减少可完成的评价次数。Lyu 等[13] 已在遗传算法解码中嵌入
- comment: none

## C051
- page: 4
- line: 157
- line_src: lineno
- col: 13
- len: 18
- kind: Highlight
- author: xchlw
- text: 高的单次评价开销会减少可完成的评价次
- context: 级以上；在固定算力下，更高的单次评价开销会减少可完成的评价次数。Lyu 等[13] 已在遗传算法解码中嵌入
- comment: none

## C052
- page: 4
- line: 158
- line_src: lineno
- col: 17
- len: 11
- kind: Highlight
- author: xchlw
- text: 「扩展为完全迭代的回路
- context: 时间窗路由，Li 等[10] 将「扩展为完全迭代的回路」列为未来工作，但二者均未报告这一做法的计算代价及其
- comment: none

## C053
- page: 4
- line: 158-160
- line_src: lineno
- col: 36
- len: 43
- kind: Highlight
- author: xchlw
- text: 但二者均未报告这一做法的计算代价及其相对开环排产的收益。本文在同等挂钟预算下度量该权衡
- context: 时间窗路由，Li 等[10] 将「扩展为完全迭代的回路」列为未来工作，但二者均未报告这一做法的计算代价及其 相对开环排产的收益。本文在同等挂钟预算下度量该权衡。
- comment: none

## C054
- page: 4
- line: 162
- line_src: lineno
- col: 1
- len: 3
- kind: Highlight
- author: xchlw
- text: 预约表
- context: 预约表上依次试算两段的最早可行时刻（试算过程中不写入最终时间表），选中可行送达最早的车辆，而不是
- comment: none

## C055
- page: 4
- line: 162
- line_src: lineno
- col: 9
- len: 2
- kind: Highlight
- author: xchlw
- text: 两段
- context: 预约表上依次试算两段的最早可行时刻（试算过程中不写入最终时间表），选中可行送达最早的车辆，而不是
- comment: none

## C056
- page: 4
- line: 165
- line_src: lineno
- col: 25
- len: 18
- kind: Highlight
- author: xchlw
- text: 使单次评价在同等挂钟预算下保持低开销
- context: 性规则[12]，亦为Li 等[10] 所用）。为使单次评价在同等挂钟预算下保持低开销，本文给出两项加速：可采纳
- comment: none

## C057
- page: 4
- line: 169
- line_src: lineno
- col: 1
- len: 7
- kind: Text
- author: xchlw
- text: 1.4主要结果
- context: 1.4主要结果
- comment: 结论没讲清楚
- Answer: 采纳。1.4 节先用大段篇幅讲基线阶梯与比较规则，结论被淹没；应先给结论，基线细节移至第 5.2 节。
- Modify:
  - 位置: paper_CN.tex L649 段首
  - 原文: 为分别度量闭环评价与预约表感知派遣的贡献，本文构造四级基线阶梯，……
  - 改为: 主要结论有三：(1) 闭环评价是收益的主要来源，使完工时间降低 \GainLoopRule{}，在绝大多数算例上逐组显著；(2) 预约表感知派遣在闭环内再降低 \GainProbeLoop{}，但只有合并各组检验时才显著；(3) 两项机制不可互相替代，也不互相放大；两项加速使派遣在同挂钟预算下取得净收益。（其后保留基线阶梯的简要说明。）
  - 理由: 先给结论。
  ---
  - 位置: paper_CN.tex L667-669
  - 原文: 上述结论依赖两条比较规则……无法区分收益来自闭环还是派遣。
  - 改为: （移至第~\ref{sec:protocol}~节，此处保留一句「比较规则见第~\ref{sec:protocol}~节」）
  - 理由: 精简。
- Status: applied

## C058
- page: 4
- line: 171
- line_src: lineno
- col: 22
- len: 10
- kind: Text+Highlight
- author: xchlw
- text: 本文构造四级基线阶梯
- context: 为分别度量闭环评价与预约表感知派遣的贡献，本文构造四级基线阶梯，前两级代表文献中两类常见的流程结
- comment: 具体文献的具体方法？
- more_targets:
  - page=4 | line=171-172 | line_src=lineno | col=33 | len=18 | text=前两级代表文献中两类常见的流程结构： | context=为分别度量闭环评价与预约表感知派遣的贡献，本文构造四级基线阶梯，前两级代表文献中两类常见的流程结 构：B0 为开环结构，先按畅通行驶时间排产，再交由无冲突路由执行（按常数矩阵排产的方法[7, 14, 16] 在实
- Answer: B0 对应「按常数矩阵排产、再在实际路网上执行」的流程（Meng/Qin/Jafarian 的模型在实际路网上执行即为此结构；Li 等 2026 的框架亦属此类）；B0+ 对应 Sun 等 2023 的两阶段方法（混合 GA 排产 + 时间窗 Dijkstra 消解冲突）。本文复现的是这些文献的流程结构而非原算法（上层统一为本文的文化基因算法），以排除算法实现强弱的影响；原文 L652 有说明，但离定义太远。
- Modify:
  - 位置: paper_CN.tex L649 （B0+ 定义之后）
  - 原文: \textbf{B0+} 为两阶段结构，排产冻结后只在第二阶段按预约表选车（如 Sun 等~\cite{sun2023integrated}）；
  - 改为: \textbf{B0+} 为两阶段结构，排产冻结后只在第二阶段按预约表选车（如 Sun 等~\cite{sun2023integrated}）。B0 与 B0+ 复现的是上述文献的流程结构，而非其具体算法：四个配置的上层统一用本文的文化基因算法，以排除算法实现强弱的影响。
  - 理由: 把「结构复现」的说明紧跟在定义后。
  - 联动: 删除 L652 的重复句
- Status: applied

## C059
- page: 4
- line: 175
- line_src: lineno
- col: 40
- len: 20
- kind: Text+Highlight
- author: xchlw
- text: 四个配置按两个维度构成2 × 2 对照：
- context: 表选车（如Sun 等[19]）；B1 为闭环规划加规则派车；B2 为本文方法。四个配置按两个维度构成2 × 2 对照：搜
- comment: 消融实验？
- more_targets:
  - page=4 | line=176 | line_src=lineno | col=36 | len=11 | text=有仅改变一个维度的对比 | context=索时是否计入冲突造成的延误，以及按畅通时间选车还是按预约表试算选车。只有仅改变一个维度的对比，才
- Answer: 是的，2×2 对照本质上就是消融实验：B0→B1 消融闭环评价，B1→B2 消融预约表感知派遣，B0→B2 为端到端效果。原文未用「消融」一词。
- Modify:
  - 位置: paper_CN.tex L650
  - 原文: 四个配置按两个维度构成 $2\times2$ 对照：搜索时是否计入冲突造成的延误，以及按畅通时间选车还是按预约表试算选车。
  - 改为: 四个配置按两个维度构成 $2\times2$ 消融对照：搜索时是否计入冲突造成的延误，以及按畅通时间选车还是按预约表试算选车。B0→B1 度量闭环评价的贡献，B1→B2 度量预约表感知派遣的贡献，B0→B2 为端到端效果。
  - 理由: 点明消融。
- Status: applied

## C060
- page: 4
- line: 177
- line_src: lineno
- col: 12
- len: 25
- kind: Highlight
- author: xchlw
- text: 四个配置共用同一上层搜索、同一路由器与同一挂钟预算
- context: 能将收益归于对应机制。四个配置共用同一上层搜索、同一路由器与同一挂钟预算，只在上述两处不同，因此
- comment: none

## C061
- page: 4
- line: 178
- line_src: lineno
- col: 9
- len: 16
- kind: Highlight
- author: xchlw
- text: 而不反映各文献具体算法的实现强弱
- context: 差值只反映结构，而不反映各文献具体算法的实现强弱。开环自报的完工时间在真实走廊上往往不可行，因此
- comment: none

## C062
- page: 4
- line: 191
- line_src: lineno
- col: 23
- len: 15
- kind: Highlight
- author: xchlw
- text: 。逐组检验按族做Holm 校正
- context: 按布局、车臂比与柔性分组的结果见第5.4 节。逐组检验按族做Holm 校正。校正后，闭环增益在10 组算例
- comment: none

## C063
- page: 4
- line: 202
- line_src: lineno
- col: 1
- len: 5
- kind: Text
- author: xchlw
- text: 1.5贡献
- context: 1.5贡献
- comment: 贡献描述不清
- Answer: 采纳。四条贡献过长，混入了相关工作对比与实验细节，主张不突出。改为每条「一句主张 + 一句依据」。
- Modify:
  - 位置: paper_CN.tex L673-688（四个 \item 全部替换）
  - 原文: \item \textbf{算例层：……} …… \item \textbf{实证层：……} ……
  - 改为: \item \textbf{问题与算例。} 研究走廊排他下柔性作业车间调度与 AGV 无冲突路由的一体化问题，构造争用强度可控的算例族，用于考察快、慢机器之间的改派权衡。
  \item \textbf{闭环双层框架。} 提出路由内嵌评价，使每个候选解按含让行等待的完工时间排序，并证明任意染色体均可解码为无冲突、无死锁的时间表，无需修复算子。
  \item \textbf{预约表感知派遣及其加速。} 选车时在预约表上试算两段运输，选可行送达最早的车辆；提出两项可证不改变结果的加速，使单次评价开销由 \CostMultBefore{} 倍降至 \CostMultAfter{} 倍。
  \item \textbf{分离度量两条通路。} 在同挂钟预算下，闭环评价为主效应（\GainLoopRule{}），预约表感知派遣为次效应（\GainProbeLoop{}），二者不可互相替代、彼此并不放大。
  - 理由: 简明；对他人工作的讨论移回 1.2 节（见 C065）。
  - 联动: 附加代价与让行记录的负面结论移到第 5 章讨论，不作为贡献
- Status: applied

## C064
- page: 4
- line: 203
- line_src: lineno
- col: 5
- len: 31
- kind: Text+Highlight
- author: xchlw
- text: 算例层：争用强度可控的算例族，用于考察快慢机械臂之间的改派权衡
- context: (1) 算例层：争用强度可控的算例族，用于考察快慢机械臂之间的改派权衡。在机器柔性、加工效率异构与走
- comment: 调度方法？
- Answer: 本条是算例贡献，不含调度方法；「考察改派权衡」容易被读成方法。方法见第 2、3 条。
- Modify:
  同 C063（第 1 条改为「问题与算例」）。
- Status: applied

## C065
- page: 4
- line: 206-207
- line_src: lineno
- col: 19
- len: 78
- kind: Text+Highlight
- author: xchlw
- text: 。以常数运输时间矩阵排产的模型无法反映这一比较，因为矩阵不含让行等待[19]；含无冲突路由但每道工序机器固定的模型同样不涉及这一比较，因为不存在改派[10]
- context: 慢但连通性更好的机械臂可能是更优指派。以常数运输时间矩阵排产的模型无法反映这一比较，因为矩阵 不含让行等待[19]；含无冲突路由但每道工序机器固定的模型同样不涉及这一比较，因为不存在改派[10]。
- comment: 此处通常不讲他人工作
- Answer: 采纳。贡献部分不宜展开他人工作；L676-678 的对比已在 1.2 节和第 2 章出现。
- Modify:
  同 C063：删除第 1 条中「以常数运输时间矩阵排产的模型无法反映……才带来收益。」，相关对比保留在 1.2 节（C033 改写）。
- Status: applied

## C066
- page: 5
- line: 209-210
- line_src: lineno
- col: 1
- len: 68
- kind: Highlight
- author: xchlw
- text: van Os 与Basten [21] 以及Lyu 等[13] 虽同样考虑无冲突路由下的柔性指派，但未以争用强度为受控变量考察其影响；本
- context: van Os 与Basten [21] 以及Lyu 等[13] 虽同样考虑无冲突路由下的柔性指派，但未以争用强度为受控变量考 察其影响；本文面向运输耗时超过加工、拥堵集中于共享走廊的车间，构造争用强度可控的算例族，用以
- comment: none

## C067
- page: 5
- line: 213
- line_src: lineno
- col: 5
- len: 28
- kind: Highlight
- author: xchlw
- text: 框架层：闭环双层框架，并度量路由内嵌评价对完工时间的贡献
- context: (2) 框架层：闭环双层框架，并度量路由内嵌评价对完工时间的贡献。路由内嵌评价将每个候选解的适应度取
- comment: none

## C068
- page: 5
- line: 218
- line_src: lineno
- col: 5
- len: 24
- kind: Highlight
- author: xchlw
- text: 机制层：预约表感知派遣，以及使其低开销的两项加速
- context: (3) 机制层：预约表感知派遣，以及使其低开销的两项加速。选车时在当前预约表上试算两段运输，选可行送
- comment: none

## C069
- page: 5
- line: 222
- line_src: lineno
- col: 2
- len: 30
- kind: Highlight
- author: xchlw
- text: 4) 实证层：两条通路的贡献量级不同，各自起作用且不可互相替
- context: (4) 实证层：两条通路的贡献量级不同，各自起作用且不可互相替代。闭环为主效应，逐组检验几乎全部显著；
- comment: none

## C070
- page: 5
- line: 231
- line_src: lineno
- col: 1
- len: 5
- kind: Text
- author: xchlw
- text: 2相关工作
- context: 2相关工作
- comment: 一是运输时间固定，优化任务指派方案 / 二是任务指派固定，优化运输路径（无冲突） / 三是运输时间和任务指派联合优化？
- Answer: 是的，第 2 章的三类正是如此划分（2.1/2.2/2.3），开头应直接这样表述。
- Modify:
  - 位置: paper_CN.tex L698
  - 原文: 相关文献可分为三类：考虑运输的柔性作业车间调度、任务外生的无冲突路由与派车，以及将二者纳入同一问题的一体化工作。
  - 改为: 相关文献可分为三类：(1) 运输时间固定、优化机器指派与排序的柔性作业车间调度（第~2.1~节）；(2) 运输任务给定、优化车辆无冲突路径与派车的研究（第~2.2~节）；(3) 将机器指派与无冲突路由联合优化的一体化工作（第~2.3~节）。
  - 理由: 采纳审阅人的归纳，更直白。
- Status: applied

## C071
- page: 5
- line: 232-234
- line_src: lineno
- col: 38
- len: 18
- kind: Highlight
- author: xchlw
- text: ，以及将二者纳入同一问题的一体化工作
- context: 相关文献可分为三类：考虑运输的柔性作业车间调度、任务外生的无冲突路由与派车，以及将二者纳入同一问 题的一体化工作。表1 汇总了各类工作与本文的对照。
- comment: none

## C072
- page: 5
- line: 234
- line_src: lineno
- col: 9
- len: 17
- kind: Highlight
- author: xchlw
- text: 表1 汇总了各类工作与本文的对照。
- context: 题的一体化工作。表1 汇总了各类工作与本文的对照。
- comment: none

## C073
- page: 5
- line: 236
- line_src: lineno
- col: 1
- len: 16
- kind: Text
- author: xchlw
- text: 2.1考虑运输的柔性作业车间调度
- context: 2.1考虑运输的柔性作业车间调度
- comment: 运输时间固定导致什么问题？
- Answer: 两个问题：(a) 计划在共享走廊上执行时车辆须让行，实际完工时间长于计划；(b) 评价中看不到拥堵，搜索无法通过改派避开拥堵走廊，可能选错机器（图 1）。2.1 节未点明后果。
- Modify:
  - 位置: paper_CN.tex L708（「车辆之间不会因争用走廊而互相推迟」之后）
  - 原文: 但这些工作的运输时长均取自矩阵，车辆之间不会因争用走廊而互相推迟；
  - 改为: 但这些工作的运输时长均取自矩阵，车辆之间不会因争用走廊而互相推迟；其后果是，按矩阵排出的计划在共享走廊上执行时会因让行而延误，矩阵评价下更优的指派在实际执行中可能更差（图~\ref{fig:motivating}）；
  - 理由: 点明后果。
- Status: applied

## C074
- page: 5
- line: 236
- line_src: lineno
- col: 16
- len: 1
- kind: Highlight
- author: xchlw
- text: 度
- context: 2.1考虑运输的柔性作业车间调度
- comment: none

## C075
- page: 5
- line: 237
- line_src: lineno
- col: 42
- len: 16
- kind: Highlight
- author: xchlw
- text: 综述了该领域至2023 年的进展
- context: 带运输的柔性作业车间调度（FJSP_PT）把物料移动纳入排程。Xin 等[22] 综述了该领域至2023 年的进展，指
- comment: none

## C076
- page: 5
- line: 239
- line_src: lineno
- col: 1
- len: 27
- kind: Text+Highlight
- author: xchlw
- text: 出占主导地位的建模方式是按位置对索引的常数行驶时间矩阵
- context: 出占主导地位的建模方式是按位置对索引的常数行驶时间矩阵：车辆从𝑎到𝑏耗时固定为𝑡(𝑎, 𝑏)，不随其他车
- comment: 运输时间固定，不考虑运输车辆行车路径冲突、拥塞、等待
- Answer: 采纳审阅人的表述。
- Modify:
  - 位置: paper_CN.tex L703
  - 原文: 车辆从 $a$ 到 $b$ 耗时固定为 $t(a,b)$，不随其他车辆是否占用同一走廊而改变。
  - 改为: 车辆从 $a$ 到 $b$ 耗时固定为 $t(a,b)$，不考虑车辆之间的路径冲突、走廊拥塞与让行等待。
  - 理由: 更直接。
- Status: applied

## C077
- page: 5
- line: 239-240
- line_src: lineno
- col: 48
- len: 16
- kind: Text+Highlight
- author: xchlw
- text: 不随其他车辆是否占用同一走廊而改
- context: 出占主导地位的建模方式是按位置对索引的常数行驶时间矩阵：车辆从𝑎到𝑏耗时固定为𝑡(𝑎, 𝑏)，不随其他车 辆是否占用同一走廊而改变。一般FJSP 的建模与算法另见Dauzère-Pérès 等[1]；该族公开基准由Homayouni
- comment: 作用？
- more_targets:
  - page=5 | line=240-241 | line_src=lineno | col=15 | len=64 | text=般FJSP 的建模与算法另见Dauzère-Pérès 等[1]；该族公开基准由Homayouni与Fontes [6] 整理。 | context=辆是否占用同一走廊而改变。一般FJSP 的建模与算法另见Dauzère-Pérès 等[1]；该族公开基准由Homayouni 与Fontes [6] 整理。
- Answer: 该句仅给出一般 FJSP 综述与公开基准的出处，与本段「常数矩阵」的论点无关。Dauzère-Pérès 已在 3.6 节 NP 难证明处引用，Homayouni 基准在 5.1 节首次使用处介绍即可。
- Modify:
  - 位置: paper_CN.tex L703 末句
  - 原文: 一般 FJSP 的建模与算法另见 Dauz\`ere-P\'er\`es 等~\cite{dauzereperes2024fjsp}；该族公开基准由 Homayouni 与 Fontes~\cite{homayouni2021production} 整理。
  - 改为: （删除）
  - 理由: 与本段论点无关。
  - 联动: 确认 5.1 节 L1391 首次介绍 Homayouni 基准时信息完整
- Status: applied

## C078
- page: 5
- line: 244
- line_src: lineno
- col: 6
- len: 7
- kind: Text+Highlight
- author: xchlw
- text: 双种群遗传算法
- context: 规划辅助的双种群遗传算法，关闭了29 个开放基准算例并改进了27 个最优已知解；Qin 等[16] 结合质量–多
- comment: 解决的是啥问题？
- more_targets:
  - page=5 | line=244 | line_src=lineno | col=14 | len=25 | text=关闭了29 个开放基准算例并改进了27 个最优已知 | context=规划辅助的双种群遗传算法，关闭了29 个开放基准算例并改进了27 个最优已知解；Qin 等[16] 结合质量–多
  - page=5 | line=246-247 | line_src=lineno | col=45 | len=16 | text=，车辆之间不会因争用走廊而互相推 | context=与元启发式框架联合优化U 形柔性流水车间的排产与内部物流。但这些工作的运输时长均取自矩阵，车辆之间 不会因争用走廊而互相推迟；关键链推理虽是作业车间局部搜索的成熟手段[15, 20]，在矩阵上计算的关键路
- Answer: Meng 等研究多 AGV 的带运输柔性作业车间调度（运输时长取自常数矩阵），以约束规划模型与约束规划辅助的双种群遗传算法求解。原文只写了方法和成绩，没写研究的问题。Qin、Jafarian 同理。
- Modify:
  - 位置: paper_CN.tex L707
  - 原文: Meng 等~\cite{meng2025cp} 提出多 AGV 情形下的约束规划模型与约束规划辅助的双种群遗传算法，……
  - 改为: Meng 等~\cite{meng2025cp} 研究多 AGV 的带运输柔性作业车间调度，提出约束规划模型与约束规划辅助的双种群遗传算法，……；Qin 等~\cite{qin2026knowledge} 研究同一问题，……；Jafarian-Moghaddam 等~\cite{jafarian2026integrated} 研究 U 形柔性流水车间排产与内部物流的联合优化，……
  - 理由: 每篇先说研究的问题，再说方法。
- Status: applied

## C079
- page: 5
- line: 245
- line_src: lineno
- col: 30
- len: 4
- kind: Highlight
- author: xchlw
- text: 局部搜索
- context: 样性存档与Q 学习，并设计了由AGV 与关键路径共同制导的局部搜索；Jafarian-Moghaddam 等[7] 以数学模型
- comment: none

## C080
- page: 5
- line: 249
- line_src: lineno
- col: 18
- len: 9
- kind: Highlight
- author: xchlw
- text: 无法定位到具体走廊
- context: 径也只能追溯到前驱工序或机器繁忙，无法定位到具体走廊。Xin 等[22] 亦指出，这类假设「会降低问题复杂
- comment: none

## C081
- page: 5
- line: 249
- line_src: lineno
- col: 46
- len: 1
- kind: Text+Highlight
- author: xchlw
- text: 「
- context: 径也只能追溯到前驱工序或机器繁忙，无法定位到具体走廊。Xin 等[22] 亦指出，这类假设「会降低问题复杂
- comment: 该文章使用什么方法解决的啥问题？
- more_targets:
  - page=5 | line=250 | line_src=lineno | col=34 | len=7 | text=关键问题参数取 | context=度，甚至改变问题的性质」，且现有算例「主要在规模上有差别，缺少针对关键问题参数取值的专门设计」，并
- Answer: Xin 等是综述，不提出方法；引用其观点是为说明「现有算例缺少对 $\bar{T}_t/\bar{T}_p$ 等关键参数的专门设计」，支撑本文构造受控算例。原文未点明这是综述，易被误解为一篇方法论文。
- Modify:
  - 位置: paper_CN.tex L709 句首
  - 原文: Xin 等~\cite{xin2025review} 亦指出，
  - 改为: Xin 等~\cite{xin2025review} 在综述中亦指出，
  - 理由: 说明文献性质。
- Status: applied

## C082
- page: 5
- line: 250
- line_src: lineno
- col: 10
- len: 2
- kind: Highlight
- author: xchlw
- text: 性质
- context: 度，甚至改变问题的性质」，且现有算例「主要在规模上有差别，缺少针对关键问题参数取值的专门设计」，并
- comment: none

## C083
- page: 5
- line: 254
- line_src: lineno
- col: 1
- len: 20
- kind: Text
- author: xchlw
- text: 2.2任务外生的无冲突路由与拥堵感知派车
- context: 2.2任务外生的无冲突路由与拥堵感知派车
- comment: 无冲突路径规划？是用于柔性作业车间调度吗？
- Answer: 2.2 节的工作（MAPF、拥堵感知派车）不是为柔性作业车间调度设计的，运输任务由外部给定；列出它们是因为本文下层的时间窗路由与派车属于同类问题。原文没有交代这一联系。
- Modify:
  - 位置: paper_CN.tex L717 段首
  - 原文: （新增）
  - 改为: 本节工作研究车辆层面的无冲突路径规划与派车，不涉及机器指派与工序排序：运输任务由外部给定。本文下层的时间窗路由与派车属于这一类问题。
  - 理由: 交代与本文的关系。
- Status: applied

## C084
- page: 6
- line: 261-264
- line_src: lineno
- col: 5
- len: 248
- kind: Highlight
- author: xchlw
- text: 相关工作与本文的对照。「机器异构」指一道工序有多台可选机器且加工时间随机器而变；「走廊排他」指一条走廊任一时刻是否至多只容一辆车：在单车道走廊上，两车同向跟驰或对向会车都可能碰撞或死锁，走廊须作为排他资源分时占用，这一建模更符合实际AGV 车间；「排产评价所用运输时长」指上层比较候选排产时所用的运输时长：「畅通估计」为不计其他车辆、按最短路算出的时长，「路由实算」为完成无冲突路由后、含让行等待的时长；「度量闭环收益与代价」指是否在同等算力下、相对开环度量了将路由纳入搜索评价的收益与计算开销。
- context: 表1. 相关工作与本文的对照。「机器异构」指一道工序有多台可选机器且加工时间随机器而变；「走廊排他」指一条走廊任一 时刻是否至多只容一辆车：在单车道走廊上，两车同向跟驰或对向会车都可能碰撞或死锁，走廊须作为排他资源分时占用， 这一建模更符合实际AGV 车间；「排产评价所用运输时长」指上层比较候选排产时所用的运输时长：「畅通估计」为不计其 他车辆、按最短路算出的时长，「路由实算」为完成无冲突路由后、含让行等待的时长；「度量闭环收益与代价」指是否在同 等算力下、相对开环度量了将路由纳入搜索评价的收益与计算开销。
- comment: none

## C085
- page: 6
- line: 286-287
- line_src: lineno
- col: 39
- len: 40
- kind: Highlight
- author: xchlw
- text: 任务的释放时刻、起点与终点都是路由器的输入，路由器无法修改产生这些任务的机器指派
- context: 上相邻而独立的两层，空闲优先与最近车辆是常用的单属性派遣规则。但这类工作中，任务的释放时刻、起点 与终点都是路由器的输入，路由器无法修改产生这些任务的机器指派；对拥堵的刻画也多用局部车辆密度或离
- comment: none

## C086
- page: 6
- line: 293
- line_src: lineno
- col: 1
- len: 19
- kind: Highlight
- author: xchlw
- text: 同时考虑柔性指派与无冲突路由的工作较少
- context: 同时考虑柔性指派与无冲突路由的工作较少。van Os 与Basten [21] 形式化了带无冲突运输约束的柔性作业车
- comment: none

## C087
- page: 6
- line: 296
- line_src: lineno
- col: 10
- len: 12
- kind: Text+Highlight
- author: xchlw
- text: 多数基准算例求至可证最优
- context: 把冲突作为割回传。多数基准算例求至可证最优，约一半相对此前启发式改进完工时间至少10%。但精确分解
- comment: 做什么处理？
- more_targets:
  - page=6 | line=299 | line_src=lineno | col=14 | len=12 | text=也无法改动第一阶段的选择 | context=第二阶段即使发现走廊拥堵，也无法改动第一阶段的选择。Li 等[10] 在栅格上同时禁止节点与边冲突，并加入
- Answer: 配对存疑：评语配到 van Os「多数基准算例求至可证最优」与 Sun「也无法改动第一阶段的选择」两处；按后一处理解为「Sun 的第二阶段做什么处理」：第二阶段对已定的指派与顺序，用时间窗 Dijkstra 逐车规划路径，冲突时令后规划的车等待，不回改第一阶段。
- Modify:
  - 位置: paper_CN.tex L731
  - 原文: 再用时间窗 Dijkstra 消解冲突，节点与路段均同时只容一辆车；但第二阶段即使发现走廊拥堵，也无法改动第一阶段的选择。
  - 改为: 再用时间窗 Dijkstra 为各运输任务依次规划路径、遇冲突时令后规划的车辆等待，节点与路段均同时只容一辆车；但第二阶段即使发现走廊拥堵，也只能靠等待消解，无法改动第一阶段的指派与顺序。
  - 理由: 说清第二阶段的处理。
- Status: applied

## C088
- page: 6
- line: 297
- line_src: lineno
- col: 11
- len: 28
- kind: Text+Highlight
- author: xchlw
- text: 作者也把更充分地利用「不可行由哪些冲突造成」列为后续方向
- context: 只适用于小规模算例；作者也把更充分地利用「不可行由哪些冲突造成」列为后续方向。Sun 等[19] 提出两阶
- comment: 目的是啥？
- Answer: 该句想说明：van Os 等自己也认为冲突信息的利用还不充分，这正是本文让路由信息进入排产的出发点；原文没有把这层联系写出来。
- Modify:
  - 位置: paper_CN.tex L730 末句
  - 原文: 作者也把更充分地利用「不可行由哪些冲突造成」列为后续方向。
  - 改为: 作者也指出，如何更充分地利用「不可行由哪些冲突造成」的信息来指导主问题，是有待研究的方向；本文让路由信息以评价与派遣两条通路进入排产，即是一种做法。
  - 理由: 点明目的。
- Status: applied

## C089
- page: 6
- line: 303
- line_src: lineno
- col: 36
- len: 13
- kind: Text+Highlight
- author: xchlw
- text: 研究重点是确定车队规模，算
- context: 在路由之后计算完工时间，车辆由染色体编码、冲突按局部规则消解；但该文的研究重点是确定车队规模，算
- comment: 导致什么问题？
- Answer: 导致无法判断：在同等算力下，把路由嵌入评价相对开环排产的收益有多大、代价多高、是否值得。
- Modify:
  - 位置: paper_CN.tex L733 末尾
  - 原文: ……算例规模较小，未与开环排产对比，也未报告嵌入路由的计算代价。
  - 改为: ……算例规模较小，未与开环排产对比，也未报告嵌入路由的计算代价；因此无法据此判断，在同等算力下把路由嵌入评价是否值得付出额外的计算开销。
  - 理由: 点明问题。
- Status: applied

## C090
- page: 6
- line: 304
- line_src: lineno
- col: 1
- len: 5
- kind: Text+Highlight
- author: xchlw
- text: 例规模较小
- context: 例规模较小，未与开环排产对比，也未报告嵌入路由的计算代价。
- comment: 没有超过呢？
- more_targets:
  - page=6 | line=306 | line_src=lineno | col=3 | len=42 | text=，现有工作的缺口不在于是否处理车辆冲突，而在于路由结果如何进入排产，以及这样做值多少 | context=综上，现有工作的缺口不在于是否处理车辆冲突，而在于路由结果如何进入排产，以及这样做值多少。本文
- Answer: 同 C041（运输未超过加工时争用仍在，但通常不是瓶颈，闭环收益预期较小；本文未测试该区间）。
- Status: applied

## C091
- page: 6
- line: 308
- line_src: lineno
- col: 30
- len: 7
- kind: Text+Highlight
- author: xchlw
- text: 以预约表感知派
- context: 求解的规模上，每个候选解都用无冲突路由后的完工时间评价，并以预约表感知派遣按试算选车；两条通路的
- comment: 想说明啥？
- more_targets:
  - page=6 | line=308 | line_src=lineno | col=44 | len=3 | text=两条通 | context=求解的规模上，每个候选解都用无冲突路由后的完工时间评价，并以预约表感知派遣按试算选车；两条通路的
  - page=6 | line=309-311 | line_src=lineno | col=19 | len=73 | text=争用强度可控的算例族考察收益随争用的变化—— 𝑇𝑡̄/𝑇 𝑝̄相同的两个算例，其拥堵中可由改派绕开的部分可能差别很大，留给调度的优化空间也随之不同 | context=贡献在同等挂钟预算下分别度量，并借助争用强度可控的算例族考察收益随争用的变化—— 𝑇𝑡̄/𝑇 𝑝̄相同的两个 算例，其拥堵中可由改派绕开的部分可能差别很大，留给调度的优化空间也随之不同。
- Answer: 该句想说明本文与已有工作的区别（大规模、每个候选解路由评价、按试算派车、同算力分别度量），以及为何不用 $\bar{T}_t/\bar{T}_p$ 刻画拥堵。一句话塞了太多内容，拆成三句。
- Modify:
  - 位置: paper_CN.tex L741
  - 原文: 本文研究运输耗时超过加工、拥堵集中于少数共享走廊的车间（……）：在精确分解难以求解的规模上，……留给调度的优化空间也随之不同。
  - 改为: 本文研究运输耗时超过加工、拥堵集中于少数共享走廊的车间（预约走廊而非节点，见第~\ref{sec:fjsppt}~节），面向精确分解难以求解的规模，与已有工作有三点不同：(1) 每个候选解都用无冲突路由后的完工时间评价；(2) 派车按预约表试算选车；(3) 在同等挂钟预算下分别度量这两条通路的贡献。此外，本文构造争用强度可控的算例族，考察收益随争用的变化。之所以不用 $\bar{T}_t/\bar{T}_p$ 刻画拥堵，是因为该比值相同的两个算例，其拥堵中可由改派绕开的部分可能差别很大。
  - 理由: 拆分长句。
- Status: applied

## C092
- page: 6
- line: 309
- line_src: lineno
- col: 4
- len: 11
- kind: Highlight
- author: xchlw
- text: 同等挂钟预算下分别度量
- context: 贡献在同等挂钟预算下分别度量，并借助争用强度可控的算例族考察收益随争用的变化—— 𝑇𝑡̄/𝑇 𝑝̄相同的两个
- comment: none

## C093
- page: 7
- line: 331
- line_src: lineno
- col: 1
- len: 7
- kind: Text
- author: xchlw
- text: 3.1问题描述
- context: 3.1问题描述
- comment: n个工件不同？
- Answer: 是，n 个工件各不相同：工序数 $n_j$ 与各工序加工时间都可不同（实验中每个工件 3 道工序，加工时间各异）。
- Modify:
  - 位置: paper_CN.tex L780
  - 原文: 一个算例由 $n$ 个工件、$N_M$ 台机械臂与 $N_A$ 辆车辆（AGV）构成，
  - 改为: 一个算例由 $n$ 个工件（各工件的工序数与加工时间可不同）、$N_M$ 台加工机器与 $N_A$ 辆车辆（AGV）构成，
  - 理由: 说明工件异质。
- Status: applied

## C094
- page: 7
- line: 332
- line_src: lineno
- col: 1
- len: 3
- kind: Highlight
- author: xchlw
- text: 一个算
- context: 一个算例由𝑛个工件、𝑁𝑀台机械臂与𝑁𝐴辆车辆（AGV）构成，它们在一个以图表示的车间路网中运行。工件
- comment: none

## C095
- page: 7
- line: 332
- line_src: lineno
- col: 2
- len: 3
- kind: Highlight
- author: xchlw
- text: 个算例
- context: 一个算例由𝑛个工件、𝑁𝑀台机械臂与𝑁𝐴辆车辆（AGV）构成，它们在一个以图表示的车间路网中运行。工件
- comment: none

## C096
- page: 7
- line: 332
- line_src: lineno
- col: 14
- len: 3
- kind: Text+Highlight
- author: xchlw
- text: 机械臂
- context: 一个算例由𝑛个工件、𝑁𝑀台机械臂与𝑁𝐴辆车辆（AGV）构成，它们在一个以图表示的车间路网中运行。工件
- comment: 条件or问题？该问题求啥？
- more_targets:
  - page=7 | line=335 | line_src=lineno | col=23 | len=13 | text=机械臂占据图中的固定节点， | context=𝑚上耗时𝑡𝑗𝑃𝑖𝑚，该值取决于所选的机械臂。机械臂占据图中的固定节点，工件由车队在这些节点之间搬运。求
  - page=7 | line=335-336 | line_src=lineno | col=50 | len=19 | text=。求解一个算例意味着同时确定四组决策： | context=𝑚上耗时𝑡𝑗𝑃𝑖𝑚，该值取决于所选的机械臂。机械臂占据图中的固定节点，工件由车队在这些节点之间搬运。求 解一个算例意味着同时确定四组决策：
- Answer: 3.1 第一段是已知条件；「同时确定四组决策」是要求解的内容，目标为最小化 $C_{\max}$。原文已知与所求混在一起，且目标单独放在列表之后。
- Modify:
  - 位置: paper_CN.tex L784
  - 原文: 求解一个算例意味着同时确定四组决策：
  - 改为: 问题要求同时确定以下四组决策，使完工时间 $C_{\max}$ 最小：
  - 理由: 把「求什么」与目标放在一起。
  ---
  - 位置: paper_CN.tex L793
  - 原文: 目标是最小化完工时间 $C_{\max}$。
  - 改为: （删除）
  - 理由: 已并入 L784。
- Status: applied

## C097
- page: 7
- line: 332
- line_src: lineno
- col: 31
- len: 16
- kind: Highlight
- author: xchlw
- text: 它们在一个以图表示的车间路网中运
- context: 一个算例由𝑛个工件、𝑁𝑀台机械臂与𝑁𝐴辆车辆（AGV）构成，它们在一个以图表示的车间路网中运行。工件
- comment: none

## C098
- page: 7
- line: 334
- line_src: lineno
- col: 7
- len: 2
- kind: Highlight
- author: xchlw
- text: 𝑛𝑗
- context: 𝑗具有固定的𝑛𝑗道工序链𝑂𝑗1 →⋯→𝑂𝑗𝑛𝑗；工序𝑂𝑗𝑖可在其可选集Ω𝑗𝑖⊆𝑀中的任一机械臂上加工，在机械臂
- comment: none

## C099
- page: 7
- line: 334
- line_src: lineno
- col: 40
- len: 1
- kind: Highlight
- author: xchlw
- text: 𝑀
- context: 𝑗具有固定的𝑛𝑗道工序链𝑂𝑗1 →⋯→𝑂𝑗𝑛𝑗；工序𝑂𝑗𝑖可在其可选集Ω𝑗𝑖⊆𝑀中的任一机械臂上加工，在机械臂
- comment: none

## C100
- page: 7
- line: 335
- line_src: lineno
- col: 5
- len: 3
- kind: Highlight
- author: xchlw
- text: 𝑡𝑗𝑃
- context: 𝑚上耗时𝑡𝑗𝑃𝑖𝑚，该值取决于所选的机械臂。机械臂占据图中的固定节点，工件由车队在这些节点之间搬运。求
- comment: none

## C101
- page: 7
- line: 338
- line_src: lineno
- col: 1
- len: 26
- kind: Text
- author: xchlw
- text: (i) 把每道工序𝑂𝑗𝑖指派给某台机械臂𝑚∈Ω𝑗𝑖;
- context: (i) 把每道工序𝑂𝑗𝑖指派给某台机械臂𝑚∈Ω𝑗𝑖;
- comment: 指派每个工件的工序？
- Answer: 是，指每个工件的每道工序。
- Modify:
  - 位置: paper_CN.tex L787
  - 原文: \item 把每道工序 $O_{ji}$ 指派给某台机械臂 $m\in\Omega_{ji}$;
  - 改为: \item 把每个工件的每道工序 $O_{ji}$ 指派给其可选集中的某台机器 $m\in\Omega_{ji}$；
  - 理由: 更明确；顺带把半角分号改为全角。
- Status: applied

## C102
- page: 7
- line: 341
- line_src: lineno
- col: 25
- len: 2
- kind: Highlight
- author: xchlw
- text: 时间
- context: (iv) 为每一次车辆移动在图上规划路径，要求在时间与空间上无冲突，允许等待。
- comment: none

## C103
- page: 7
- line: 341
- line_src: lineno
- col: 26
- len: 4
- kind: Highlight
- author: xchlw
- text: 间与空间
- context: (iv) 为每一次车辆移动在图上规划路径，要求在时间与空间上无冲突，允许等待。
- comment: none

## C104
- page: 7
- line: 362-363
- line_src: lineno
- col: 14
- len: 65
- kind: Text+Highlight
- author: xchlw
- text: 一个运输任务是一次单程移动——从𝑣0 到第一台机械臂、在前后两台不同机械臂之间，或当𝛿ret = 1 时从最后一台机械臂返回𝑣0；
- context: 空载停于𝑣0 且立即可用。一个运输任务是一次单程移动——从𝑣0 到第一台机械臂、在前后两台不同机械 臂之间，或当𝛿ret = 1 时从最后一台机械臂返回𝑣0；任一车辆可执行任一任务，因此同一工件的连续移动
- comment: 出发点与加工机器之间，以及加工机器与加工机器之间
- Answer: 采纳，把三类运输任务分条写清。
- Modify:
  - 位置: paper_CN.tex L837-839
  - 原文: 一个运输任务是一次单程移动——从 $v_0$ 到第一台机械臂、在前后两台不同机械臂之间，或当 $\delta_{\mathrm{ret}}=1$ 时从最后一台机械臂返回 $v_0$；
  - 改为: 一个运输任务是一次单程移动，共三类：从上下料点 $v_0$ 到第一台加工机器；在前后两台不同的加工机器之间；以及当 $\delta_{\mathrm{ret}}=1$ 时从最后一台加工机器返回 $v_0$。
  - 理由: 采纳审阅人表述。
- Status: applied

## C105
- page: 8
- line: 366
- line_src: lineno
- col: 3
- len: 3
- kind: Highlight
- author: xchlw
- text: 由路由
- context: 刻可由路由层推迟。
- comment: none

## C106
- page: 8
- line: 366
- line_src: lineno
- col: 3
- len: 4
- kind: Highlight
- author: xchlw
- text: 由路由层
- context: 刻可由路由层推迟。
- comment: none

## C107
- page: 8
- line: 368
- line_src: lineno
- col: 19
- len: 3
- kind: Text+Highlight
- author: xchlw
- text: 走廊𝑒
- context: A6. 路网与无冲突性。𝐺强连通，各走廊𝑒∈𝐸的通行时间𝜏𝑒为已知常数。走廊是排他资源：每条走廊𝑒的两
- comment: 图G的每一条边都是走廊？图G的顶点呢？
- Answer: 是，图 G 的每条边都是一条单车道走廊；顶点为上下料点 $v_0$、各机器所在节点与走廊交汇的路口。原文未定义顶点。
- Modify:
  - 位置: paper_CN.tex L843
  - 原文: \item \textbf{路网与无冲突性。} $G$ 强连通，
  - 改为: \item \textbf{路网与无冲突性。} 车间路网为无向图 $G=(V,E)$：顶点 $V$ 为上下料点 $v_0$、各机器所在节点与走廊交汇的路口，每条边 $e\in E$ 是一条单车道走廊。$G$ 强连通，
  - 理由: 定义顶点与边。
  ---
  - 位置: paper_CN.tex L807（符号表）
  - 原文: $G=(V,E)$, $\tau_e$ & 车间图；走廊 $e\in E$ 的通行时间 \\
  - 改为: $G=(V,E)$, $\tau_e$ & 车间路网（顶点：上下料点、机器节点与路口；边：走廊）；走廊 $e$ 的通行时间 \\
  - 理由: 符号表同步。
- Status: applied

## C108
- page: 8
- line: 374
- line_src: lineno
- col: 1
- len: 17
- kind: Text
- author: xchlw
- text: 工作（第6.3 节第(5) 条）。
- context: 工作（第6.3 节第(5) 条）。
- comment: 现有FJSP工作不考虑该条件？
- Answer: 已有工作考虑过这些条件（如动态到达与故障，已引 gui2023dynamic、zhao2026deep）；A7 只是声明本文不考虑。原文写法容易被理解为「现有 FJSP 工作都不考虑」。
- Modify:
  - 位置: paper_CN.tex L849-850
  - 原文: 机器与车辆故障、有限缓冲与阻塞、电池充电，以及工件的动态到达~\cite{gui2023dynamic,zhao2026deep}，留待后续工作
  - 改为: 机器与车辆故障、有限缓冲与阻塞、电池充电，以及工件的动态到达（已有工作对此有专门研究~\cite{gui2023dynamic,zhao2026deep}）不在本文范围内，留待后续工作
  - 理由: 消除误解。
- Status: applied

## C109
- page: 8
- line: 377
- line_src: lineno
- col: 1
- len: 49
- kind: Text
- author: xchlw
- text: 与机器相关的加工时间）与A6（将争用表述为显式的排他资源约束，而非常数行驶时间矩阵），由此，运输时
- context: 与机器相关的加工时间）与A6（将争用表述为显式的排他资源约束，而非常数行驶时间矩阵），由此，运输时
- comment: 本质是运输时间的动态性，而非静态
- Answer: 采纳。A6 带来的本质变化是运输时间由静态常数变为随路径与走廊占用动态变化。
- Modify:
  - 位置: paper_CN.tex L853-854
  - 原文: 决定本文问题特征的是 A3（……）与 A6（……），由此，运输时长是路由决策的输出，而非固定的输入参数。
  - 改为: 决定本文问题特征的是 A3（部分柔性机器上与机器相关的加工时间）与 A6（将争用表述为显式的排他资源约束）：后者使运输时间不再是静态常数，而随车辆路径与走廊占用动态变化，即运输时长是路由决策的输出，而非固定的输入参数。
  - 理由: 点明「动态性」这一本质。
- Status: applied

## C110
- page: 8
- line: 378
- line_src: lineno
- col: 21
- len: 7
- kind: Text+Highlight
- author: xchlw
- text: 无死锁不列为假
- context: 长是路由决策的输出，而非固定的输入参数。无死锁不列为假设：第4.3 节命题2 基于A4 与A6 证明，任意指
- comment: j、i的含义？
- more_targets:
  - page=8 | line=384 | line_src=lineno | col=29 | len=9 | text=m(𝑗, 𝑖) 为 | context=令𝑥𝑗𝑖𝑚∈{0, 1} 表示𝑂𝑗𝑖被指派给机械臂𝑚，记m(𝑗, 𝑖) 为所选机械臂，𝑑𝑗𝑖= loc(m(𝑗, 𝑖)) 为该臂所在节点。当𝛿ret = 1
- Answer: $j$ 为工件编号，$i$ 为工序在该工件工序链中的序号，$O_{ji}$ 即工件 $j$ 的第 $i$ 道工序；已在 3.1 节与表 2 定义，但隔得较远，3.3 节首次使用时重申。
- Modify:
  - 位置: paper_CN.tex L859
  - 原文: 令 $x_{jim}\in\{0,1\}$ 表示 $O_{ji}$ 被指派给机械臂 $m$，
  - 改为: 令 $x_{jim}\in\{0,1\}$ 表示工件 $j$ 的第 $i$ 道工序 $O_{ji}$ 被指派给机器 $m$，
  - 理由: 就近重申下标含义。
- Status: applied

## C111
- page: 8
- line: 384
- line_src: lineno
- col: 71
- len: 8
- kind: Highlight
- author: xchlw
- text: 𝛿ret = 1
- context: 令𝑥𝑗𝑖𝑚∈{0, 1} 表示𝑂𝑗𝑖被指派给机械臂𝑚，记m(𝑗, 𝑖) 为所选机械臂，𝑑𝑗𝑖= loc(m(𝑗, 𝑖)) 为该臂所在节点。当𝛿ret = 1
- comment: none

## C112
- page: 8
- line: 388
- line_src: lineno
- col: 1
- len: 22
- kind: Highlight
- author: xchlw
- text: 与车辆路径问题不同，运输任务并不是输入的一部
- context: 与车辆路径问题不同，运输任务并不是输入的一部分，而是由指派派生出来的：
- comment: none

## C113
- page: 8
- line: 391
- line_src: lineno
- col: 4
- len: 7
- kind: Highlight
- author: xchlw
- text: 务(𝑗, 𝑖)
- context: 其中任务(𝑗, 𝑖) 把工件𝑗从𝑑𝑗,𝑖−1 搬到𝑑𝑗𝑖，并在𝑟𝑗𝑖= 𝐶𝑗,𝑖−1 时刻就绪（约定𝐶𝑗0 = 0）。若前后两道工序被放在同
- comment: none

## C114
- page: 8
- line: 393
- line_src: lineno
- col: 35
- len: 5
- kind: Highlight
- author: xchlw
- text: 策组(i)
- context: 一台机械臂上，则不产生任何运输任务。因此，运输任务的数量与端点都是决策组(i) 的后果：一个把工件始终
- comment: none

## C115
- page: 8
- line: 401
- line_src: lineno
- col: 4
- len: 10
- kind: Highlight
- author: xchlw
- text: 时序关系与可行性条件
- context: 3.4时序关系与可行性条件
- comment: none

## C116
- page: 8
- line: 407
- line_src: lineno
- col: 6
- len: 3
- kind: Text+Highlight
- author: xchlw
- text: 𝑆𝑗𝑖
- context: 𝐶𝑗𝑖= 𝑆𝑗𝑖+ 𝑝𝑗𝑖,∀𝑗, 𝑖,(3)
- comment: 含义？A是时刻？
- Answer: $S_{ji}$、$C_{ji}$ 分别为 $O_{ji}$ 的开工与完工时刻；$A_{ji}$ 是工件到达该工序所在机器节点的时刻（物料到达时刻），三者都是时刻。表 2 已定义，正文就近补充。
- Modify:
  - 位置: paper_CN.tex L894
  - 原文: 其中 $A_{ji}$ 是工件实际出现在 $d_{ji}$ 的时刻。
  - 改为: 其中 $S_{ji}$、$C_{ji}$ 分别为 $O_{ji}$ 的开工与完工时刻，$A_{ji}$ 是工件 $j$ 实际到达 $d_{ji}$ 的时刻（物料到达时刻）。
  - 理由: 就近定义。
- Status: applied

## C117
- page: 8
- line: 412
- line_src: lineno
- col: 21
- len: 21
- kind: Highlight
- author: xchlw
- text: 若(𝑗, 𝑖) ∉𝒯(𝑥)，则工件本已在该
- context: 其中𝐴𝑗𝑖是工件实际出现在𝑑𝑗𝑖的时刻。若(𝑗, 𝑖) ∉𝒯(𝑥)，则工件本已在该处，𝐴𝑗𝑖= 𝐶𝑗,𝑖−1。否则𝐴𝑗𝑖由承运任务
- comment: none

## C118
- page: 9
- line: 424
- line_src: lineno
- col: 1
- len: 29
- kind: Highlight
- author: xchlw
- text: [𝜂, 𝜂+ 𝜏𝑒) ∩[𝜂′, 𝜂′ + 𝜏𝑒) = ∅
- context: [𝜂, 𝜂+ 𝜏𝑒) ∩[𝜂′, 𝜂′ + 𝜏𝑒) = ∅(8)
- comment: none

## C119
- page: 9
- line: 427
- line_src: lineno
- col: 25
- len: 6
- kind: Highlight
- author: xchlw
- text: 。目标函数为
- context: 空间、而非通过共享机械臂把不同工件耦合起来的约束。目标函数为
- comment: none

## C120
- page: 9
- line: 431
- line_src: lineno
- col: 35
- len: 8
- kind: Highlight
- author: xchlw
- text: (5) 可收紧为
- context: 在半活动排程中（每道工序都在约束允许的最早时刻开工），式(4) 与式(5) 可收紧为
- comment: none

## C121
- page: 9
- line: 438
- line_src: lineno
- col: 2
- len: 14
- kind: Text+Highlight
- author: xchlw
- text: .5与FJSP_PT 的关系
- context: 3.5与FJSP_PT 的关系
- comment: 前面已经讲过了，这里是否冗余？
- Answer: 部分冗余。与 1.2 节、2.1 节重复的是「常数矩阵」这一概念；3.5 节的新内容是形式化关系（去掉式 (9) 即退化为 FJSP_PT，$t^*$ 由此用作下界与开环估计）以及与 van Os、Lyu 冲突模型的区别。建议删去重复的叙述，并把 3.5 节并入 3.4 节末尾。
- Modify:
  - 位置: paper_CN.tex L933-943
  - 原文: \subsection{与 FJSP\_PT 的关系} …… 两个问题的差别因此只在这组走廊排他约束：有它，一次移动的时长由各车路径共同决定；没有它，时长是输入参数。……
  - 改为: 删除小节标题，作为 3.4 节末段「与 FJSP\_PT 及已有冲突模型的关系」；删除「两个问题的差别因此只在……时长是输入参数。」一句，保留退化关系、$t^*$ 的用途与节点/边预约的区别。
  - 理由: 去冗余。
  - 联动: 全文中 \ref{sec:fjsppt} 的引用改指向 3.4 节
- Status: applied

## C122
- page: 9
- line: 445
- line_src: lineno
- col: 1
- len: 25
- kind: Text+Highlight
- author: xchlw
- text: 与同样给出显式路网的工作相比，差别在于预约的对象。
- context: 与同样给出显式路网的工作相比，差别在于预约的对象。van Os 与Basten [21] 预约的是节点：两车不得同时
- comment: 本质区别？
- Answer: 本质区别在于把哪种资源视为被争用的资源：van Os 预约节点（两车不得同占一个节点或交换节点），本文预约边（走廊），并在节点设容量充裕的停靠位。后果是：本文中等待只发生在节点、拥堵只发生在走廊；节点预约模型中节点本身也会拥堵。原文只写了「预约的对象」，没说清后果。
- Modify:
  - 位置: paper_CN.tex L940
  - 原文: 与同样给出显式路网的工作相比，差别在于预约的对象。
  - 改为: 与同样给出显式路网的工作相比，本质区别在于把哪种资源视为被争用的资源，这决定了拥堵发生在哪里。
  - 理由: 点明本质。
- Status: applied

## C123
- page: 9
- line: 454
- line_src: lineno
- col: 17
- len: 11
- kind: Text+Highlight
- author: xchlw
- text: 义的问题是强NP 难的
- context: 命题1. 由式(2)–(9) 定义的问题是强NP 难的；且当所有工序均满足Ω𝑗𝑖= 𝑀时依然如此。
- comment: 啥问题？他人工作是否已证明？
- more_targets:
  - page=9 | line=455 | line_src=lineno | col=9 | len=3 | text=下算例 | context=证明. 限制到如下算例：对所有𝑒∈𝐸有𝜏𝑒= 0，每台机械臂各由一条专用走廊与𝑣0 相连，且𝑁𝐴= 𝑛。此时
- Answer: 「问题」指式 (2)–(10) 定义的本文问题（柔性作业车间调度 + 走廊排他的无冲突路由）。柔性作业车间调度的强 NP 难已有证明（Dauzère-Pérès 等）；本文通过把它规约为本问题的特例得到结论，属直接推论，不是新结果，原文应说明这一点。
- Modify:
  - 位置: paper_CN.tex L949
  - 原文: 由式~\eqref{eq:assign}--\eqref{eq:obj} 定义的问题是强 NP 难的；
  - 改为: 由式~\eqref{eq:assign}--\eqref{eq:obj} 定义的柔性作业车间与无冲突路由一体化调度问题是强 NP 难的；
  - 理由: 说明「啥问题」。
  ---
  - 位置: paper_CN.tex L964（证明之后）
  - 原文: （新增）
  - 改为: 该结论由已知结果经直接规约得到，列出是为说明问题难度，并非本文的贡献。
  - 理由: 说明与他人工作的关系。
- Status: applied

## C124
- page: 9
- line: 455
- line_src: lineno
- col: 5
- len: 6
- kind: Highlight
- author: xchlw
- text: 限制到如下算
- context: 证明. 限制到如下算例：对所有𝑒∈𝐸有𝜏𝑒= 0，每台机械臂各由一条专用走廊与𝑣0 相连，且𝑁𝐴= 𝑛。此时
- comment: none

## C125
- page: 10
- line: 473
- line_src: lineno
- col: 1
- len: 10
- kind: Text
- author: xchlw
- text: 3.7算例特征的刻画
- context: 3.7算例特征的刻画
- comment: 该部分内容的目的？
- Answer: 本节定义刻画算例的特征量（$\bar{T}_t/\bar{T}_p$、$H$、$F$、$N_A/N_M$、争用强度、漏斗宽度）与下界，目的有二：构造只改变单一特征的受控算例（5.1 节），以及按特征分组解释收益来源（5.4 节）；下界只用于正确性校验。原文未交代目的。
- Modify:
  - 位置: paper_CN.tex L973 段首
  - 原文: 本文固定算例规模，只改变其结构；
  - 改为: 本节定义刻画算例的特征量与下界，目的有二：一是在第~\ref{sec:instances}~节据此构造只改变单一特征的受控算例；二是在第~\ref{sec:whichcongestion}~节按这些特征分组解释收益来源；下界只用于正确性校验。本文固定算例规模，只改变其结构；
  - 理由: 交代目的。
- Status: applied

## C126
- page: 10
- line: 504-505
- line_src: lineno
- col: 1
- len: 76
- kind: Highlight
- author: xchlw
- text: 在本文算例上，三者中取到最大的是LBcut（十组中八组）与LBchain（其余两组），LBload 从未最大——这与争用集中在上下料出口的算例设计相符。
- context: 在本文算例上，三者中取到最大的是LBcut（十组中八组）与LBchain（其余两组），LBload 从未最大——这与争 用集中在上下料出口的算例设计相符。该下界较松（与已知最好解的间隙为27% 至58%），只用于正确性校验：
- comment: none

## C127
- page: 10
- line: 505
- line_src: lineno
- col: 17
- len: 35
- kind: Highlight
- author: xchlw
- text: 。该下界较松（与已知最好解的间隙为27% 至58%），只用于正确性校验
- context: 用集中在上下料出口的算例设计相符。该下界较松（与已知最好解的间隙为27% 至58%），只用于正确性校验：
- comment: none

## C128
- page: 10
- line: 506
- line_src: lineno
- col: 1
- len: 5
- kind: Highlight
- author: xchlw
- text: 任何低于它
- context: 任何低于它的解都说明实现有误（第5.1.2 节）；它不能说明解与最优的距离，这一问题见第5.8 节与第6.2 节局
- comment: none

## C129
- page: 10
- line: 506-507
- line_src: lineno
- col: 5
- len: 57
- kind: Highlight
- author: xchlw
- text: 它的解都说明实现有误（第5.1.2 节）；它不能说明解与最优的距离，这一问题见第5.8 节与第6.2 节局限(3)
- context: 任何低于它的解都说明实现有误（第5.1.2 节）；它不能说明解与最优的距离，这一问题见第5.8 节与第6.2 节局 限(3)。
- comment: none

## C130
- page: 10
- line: 506
- line_src: lineno
- col: 10
- len: 48
- kind: Highlight
- author: xchlw
- text: 明实现有误（第5.1.2 节）；它不能说明解与最优的距离，这一问题见第5.8 节与第6.2 节局
- context: 任何低于它的解都说明实现有误（第5.1.2 节）；它不能说明解与最优的距离，这一问题见第5.8 节与第6.2 节局
- comment: none

## C131
- page: 10
- line: 515
- line_src: lineno
- col: 35
- len: 12
- kind: Text+Highlight
- author: xchlw
- text: 指派与排序上搜索[23]
- context: 走廊网络。上层用文化基因算法（memetic algorithm）在指派与排序上搜索[23]；中间由一个事件驱动的解码
- comment: 直接用他人方法？文化基因算法是一个框架？全局和局部具体用什么算法？
- Answer: 是，上层采用常规的文化基因算法（Zhang 等 2024），上层算法本身不是本文的贡献，贡献在于路由信息如何进入评价与派遣。文化基因算法是「全局进化搜索 + 局部搜索」的框架：全局部分为遗传算法（4.8 节：锦标赛选择、顺序交叉/均匀交叉、交换/改派变异），局部部分为按让行记录的局部搜索（4.7 节）。
- Modify:
  - 位置: paper_CN.tex L1017
  - 原文: 上层用文化基因算法（memetic algorithm）在指派与排序上搜索~\cite{zhang2024memetic}；
  - 改为: 上层采用文化基因算法（memetic algorithm，即遗传算法与局部搜索相结合的框架）~\cite{zhang2024memetic} 在指派与排序上搜索：全局搜索为常规遗传算法（第~4.8~节），局部搜索为按让行记录的邻域搜索（第~\ref{sec:ls}~节）；上层算法本身不是本文的贡献。
  - 理由: 说清框架、具体算法与贡献边界。
  - 联动: 建议为 4.8 节加 \label{sec:ga} 后改用 \ref
- Status: applied

## C132
- page: 10
- line: 516
- line_src: lineno
- col: 6
- len: 8
- kind: Text+Highlight
- author: xchlw
- text: 一个候选解翻译成
- context: 器把上层的一个候选解翻译成一串带先后约束的运输任务；下层以时间窗预约把这串任务转化为无冲突路径。
- comment: 候选解是啥？为何要翻译？
- Answer: 候选解即一个染色体：机器指派向量 + 工序序列（4.3.1 节）。它只给出指派与顺序，不含运输任务、车辆与时刻，因此要由解码器转换成具体的运输任务与时间表，才能算出完工时间。「翻译」一词不准确，改为「解码/转换」。
- Modify:
  - 位置: paper_CN.tex L1017-1018
  - 原文: 中间由一个事件驱动的解码器把上层的一个候选解翻译成一串带先后约束的运输任务；
  - 改为: 中间由一个事件驱动的解码器把上层的一个候选解（即一组机器指派与工序序列，见第~\ref{sec:upper}~节）转换为一串带先后约束的运输任务——染色体本身不含运输任务、车辆与时刻，须经解码才能得到时间表与完工时间；
  - 理由: 解释候选解与解码的必要性。
- Status: applied

## C133
- page: 10
- line: 516
- line_src: lineno
- col: 27
- len: 21
- kind: Text+Highlight
- author: xchlw
- text: 下层以时间窗预约把这串任务转化为无冲突路径
- context: 器把上层的一个候选解翻译成一串带先后约束的运输任务；下层以时间窗预约把这串任务转化为无冲突路径。
- comment: 反馈？
- Answer: 「反馈」指下层结果回到上层的两条通路：完工时间作为适应度（评价通路），预约表上的试算结果用于选车（决策通路），紧接着的 description 列表给出了定义，但此处首次出现时没有铺垫。
- Modify:
  - 位置: paper_CN.tex L1019（「输出是一张可执行的无冲突时间表及其完工时间。」之后）
  - 原文: （新增）
  - 改为: 下层的结果通过以下两条通路反馈给上层。
  - 理由: 首次出现时给出铺垫。
- Status: applied

## C134
- page: 11
- line: 521
- line_src: lineno
- col: 1
- len: 0
- kind: Text
- author: xchlw
- text: （批注贴在图上）
- context: 图题：Fig. 2. 闭环双层框架。上层以文化基因算法搜索指派与排序，下层以时间窗预约做无冲突路由，中间的事件驱动解码器把上
- comment: 解码器属于上层还是下层？或者都不是？
- Answer: 解码器是连接两层的中间环节：它按上层染色体模拟执行过程，并调用下层路由器；逻辑上属于上层适应度评价的一部分。图中画在两层之间，正文未说明归属。
- Modify:
  - 位置: paper_CN.tex L1042-1043（图 2 图题）
  - 原文: 中间的事件驱动解码器把上层的一个候选解翻译成一串运输任务。
  - 改为: 中间的事件驱动解码器属于上层的适应度评价过程：它把一个候选解转换为一串运输任务，并调用下层路由器为其规划路径。
  - 理由: 说明归属。
  ---
  - 位置: paper_CN.tex fig/fig_framework_CN.py
  - 原文: 解码器框位于两层之间
  - 改为: 把解码器框画入上层框内，或在其旁标注「上层评价过程」
  - 理由: 图文一致。
- Status: applied

## C135
- page: 11
- line: 537
- line_src: lineno
- col: 1
- len: 0
- kind: Text
- author: xchlw
- text: （批注贴在图上）
- context: 图题：Fig. 2. 闭环双层框架。上层以文化基因算法搜索指派与排序，下层以时间窗预约做无冲突路由，中间的事件驱动解码器把上
- comment: 两种反馈的却别和必要性？
- Answer: 区别：评价通路每个候选解回传一次完工时间，影响上层选哪组机器指派与工序顺序；决策通路每个运输任务试算一次，影响解码中选哪辆车。必要性：二者作用于不同决策，不能互相替代——染色体不编码车辆，评价通路无法改变选车；选车也无法改变机器指派。第 5 章实验证实：闭环为主效应，派遣为次效应，开环下仅改派车远不能替代闭环。
- Modify:
  - 位置: paper_CN.tex L1030（description 环境之后）
  - 原文: （新增）
  - 改为: 两条通路作用于不同决策：评价通路影响上层选择哪组机器指派与工序顺序，每个候选解回传一次；决策通路影响解码时为每个运输任务选哪辆车，每个任务试算一次。二者不能互相替代：染色体不编码车辆，评价通路无法改变选车；选车也无法改变机器指派。第~\ref{sec:Chapter_V}~节的对照证实了这一点。
  - 理由: 说明区别与必要性。
- Status: applied

## C136
- page: 11
- line: 538
- line_src: lineno
- col: 1
- len: 0
- kind: Text
- author: xchlw
- text: （批注贴在图上）
- context: 图题：Fig. 2. 闭环双层框架。上层以文化基因算法搜索指派与排序，下层以时间窗预约做无冲突路由，中间的事件驱动解码器把上
- comment: 整个方法的输入和输出？
- Answer: 正文 L1016-1019 已写明（输入：算例；输出：无冲突时间表及完工时间），但图 2 中没有画出输入与输出。
- Modify:
  - 位置: paper_CN.tex fig/fig_framework_CN.py
  - 原文: 图中无输入、输出
  - 改为: 左侧加「输入：算例（工序链、可选机器与工时、车队规模、走廊网络）」，右侧加「输出：无冲突时间表与 $C_{\max}$」
  - 理由: 图文一致。
  - 联动: 重新生成 fig/fig_framework_CN.pdf
- Status: applied

## C137
- page: 11
- line: 541
- line_src: lineno
- col: 2
- len: 5
- kind: Text+Highlight
- author: xchlw
- text: 无冲突时间
- context: 的无冲突时间表作为适应度回传，每个候选解评价一次；通路二（橙，标记2）在选车前于预约表上试算两段的最早可行送
- comment: 是啥？生成时间表不需要确定运输路径？
- more_targets:
  - page=11 | line=541 | line_src=lineno | col=5 | len=3 | text=时间表 | context=的无冲突时间表作为适应度回传，每个候选解评价一次；通路二（橙，标记2）在选车前于预约表上试算两段的最早可行送
- Answer: 时间表包括每道工序的机器与起止时刻，以及每个运输任务的车辆与路径（含每条走廊的进入时刻）；生成时间表需要确定运输路径，路径由下层路由给出。图题未说明时间表包含什么。
- Modify:
  - 位置: paper_CN.tex L1045（图 2 图题）
  - 原文: 通路一（蓝，标记 1）把下层完成的无冲突时间表作为适应度回传，每个候选解评价一次；
  - 改为: 通路一（蓝，标记 1）在下层为全部运输任务完成无冲突路由后，把所得时间表（含各工序起止时刻与各车辆路径）的完工时间作为适应度回传，每个候选解评价一次；
  - 理由: 说明时间表内容。
- Status: applied

## C138
- page: 11
- line: 544
- line_src: lineno
- col: 1
- len: 12
- kind: Highlight
- author: xchlw
- text: 评价通路，即路由内嵌评价
- context: 评价通路，即路由内嵌评价。每一代中每个候选解的适应度，均取下层完成全部运输任务的无冲突路由之后
- comment: none

## C139
- page: 11
- line: 546
- line_src: lineno
- col: 16
- len: 11
- kind: Text+Highlight
- author: xchlw
- text: 上层即以该值为优化目标
- context: 的完工时间，其中已含让行等待。上层即以该值为优化目标，而非假定车辆互不干扰、一路畅通算出的完工时
- comment: 该值的含义？
- Answer: 该值即候选解解码并完成全部无冲突路由后的完工时间 $C_{\max}$（含让行等待）。
- Modify:
  - 位置: paper_CN.tex L1026
  - 原文: 上层即以该值为优化目标，
  - 改为: 上层即以该完工时间 $C_{\max}$ 为适应度（优化目标），
  - 理由: 指代明确。
- Status: applied

## C140
- page: 11
- line: 548
- line_src: lineno
- col: 1
- len: 4
- kind: Highlight
- author: xchlw
- text: 决策通路
- context: 决策通路。选车时读取当前预约表，而非在路径生成之后才获知结果。具体机制为预约表感知派遣：对每辆
- comment: none

## C141
- page: 11
- line: 552
- line_src: lineno
- col: 23
- len: 11
- kind: Text+Highlight
- author: xchlw
- text: 另实现的两种层间接口为
- context: 两条通路对完工时间的贡献在第5 节分别度量。另实现的两种层间接口为：对已被占用的走廊时段附加额外
- comment: 如何不同？
- more_targets:
  - page=11 | line=554 | line_src=lineno | col=29 | len=24 | text=构造见第4.6、4.7 节，对照结果见第5 节。 | context=代价（后文简称附加代价），以及按让行记录改派或调整顺序；构造见第4.6、4.7 节，对照结果见第5 节。
  - page=11 | line=555 | line_src=lineno | col=9 | len=13 | text=两条通路进入上层的位置不同 | context=框架结构见图2。两条通路进入上层的位置不同，因而单次评价的计算开销也不同。
- Answer: 进入位置不同：评价通路在每个候选解解码结束时回传一次完工时间；决策通路在解码过程中为每个运输任务试算一次，路由调用次数约为前者的 $N_A$ 倍，单次评价开销因而更高。另两种接口：附加代价修改路由的代价函数，让行记录驱动局部搜索改派或调序。
- Modify:
  - 位置: paper_CN.tex L1035
  - 原文: 两条通路进入上层的位置不同，因而单次评价的计算开销也不同。
  - 改为: 两条通路进入上层的位置不同：评价通路在每个候选解解码结束时回传一次完工时间，决策通路在解码过程中为每个运输任务试算一次；后者的路由调用次数约为前者的 $N_A$ 倍，单次评价开销也更高。
  - 理由: 说清如何不同。
- Status: applied

## C142
- page: 11
- line: 557
- line_src: lineno
- col: 1
- len: 17
- kind: Text
- author: xchlw
- text: 4.2下层：时间窗预约与无冲突路由
- context: 4.2下层：时间窗预约与无冲突路由
- comment: 先有任务指派，再有路径规划？
- Answer: 是。解码中每生成一个运输任务，先选车（预约表感知派遣的试算本身也调用路由），选定后再为该车正式规划并写入路径；即：机器指派（染色体）→ 生成任务 → 选车 → 规划路径。4.2 节放在 4.3、4.4 节之前，是因为后两节都要调用路由器，但原文未说明，读者会误以为先规划路径。
- Modify:
  - 位置: paper_CN.tex L1057（4.2 节标题之后）
  - 原文: （新增）
  - 改为: 执行顺序上，路由发生在机器指派与选车之后：解码器每生成一个运输任务并选定车辆，便调用本节的路由器为该车规划路径。本节先介绍路由器，是因为第~\ref{sec:upper}、\ref{sec:dispatch}~节都要调用它。
  - 理由: 说明顺序。
- Status: applied

## C143
- page: 11
- line: 559
- line_src: lineno
- col: 30
- len: 4
- kind: Text+Highlight
- author: xchlw
- text: 此预约表
- context: 4.2.1预约表. 唯一被争用的资源是走廊（假设A6），因此预约表把每条走廊映射到一个按时间排序的半开占
- comment: 表结构？与AGV、道路的关系？
- Answer: 预约表以走廊为索引：每条走廊对应一个按时间排序的占用区间列表，每个区间记录占用的车辆与任务。AGV 通过区间上的车辆标注关联，道路（走廊）就是表的索引。原文描述较抽象。
- Modify:
  - 位置: paper_CN.tex L1060
  - 原文: 因此预约表把每条走廊映射到一个按时间排序的半开占用区间列表 $[t,\,t+\tau_e)$，每个区间标注占用它的车辆与任务。
  - 改为: 因此预约表以走廊为索引：每条走廊 $e$ 对应一个按时间排序的占用区间列表，每个区间 $[t,\,t+\tau_e)$ 记录占用该走廊的车辆编号与任务编号。车辆每规划一段路径，便把途经各走廊的占用区间写入表中；后规划的车辆查询该表以避开已占时段。
  - 理由: 说明表结构及其与 AGV、走廊的关系。
- Status: applied

## C144
- page: 11
- line: 562
- line_src: lineno
- col: 7
- len: 9
- kind: Text+Highlight
- author: xchlw
- text: 穿越节点耗时为零，
- context: 点不被预约：穿越节点耗时为零，等待发生在停靠位上（假设A6 已把停靠位与通行资源分开）。因此只需预约
- comment: 时刻？代价？
- more_targets:
  - page=11 | line=565 | line_src=lineno | col=6 | len=12 | text=时间窗Dijkstra. | context=4.2.2时间窗Dijkstra. 一段行驶用标签设定（label-setting）搜索来规划。标签(𝑢, 𝑡) 表示「在时刻𝑡停在节点𝑢
  - page=11 | line=567 | line_src=lineno | col=6 | len=6 | text=」，代价为𝑡 | context=的停靠位上」，代价为𝑡（算法1）。考察一条从当前节点出发的走廊时，向预约表查询最早可行进入时刻𝑡′ ≥𝑡；
- Answer: 标签 $(u,t)$ 中的 $t$ 是车辆到达节点 $u$（并可从 $u$ 出发）的时刻；Dijkstra 的「代价」就是这个到达时刻，搜索使到达终点的时刻最早。
- Modify:
  - 位置: paper_CN.tex L1066
  - 原文: 标签 $(u,t)$ 表示「在时刻 $t$ 停在节点 $u$ 的停靠位上」，代价为 $t$（算法~\ref{alg:route}）。
  - 改为: 标签 $(u,t)$ 表示车辆最早在时刻 $t$ 到达节点 $u$ 并停在其停靠位上；搜索以到达时刻 $t$ 作为代价（即 Dijkstra 中的距离值），目标是使到达终点的时刻最早（算法~\ref{alg:route}）。
  - 理由: 解释时刻与代价。
- Status: applied

## C145
- page: 11
- line: 564
- line_src: lineno
- col: 22
- len: 3
- kind: Highlight
- author: xchlw
- text: 校验器
- context: 走廊这一种资源，下层路由器与独立于解码器的校验器都只检查走廊占用。
- comment: none

## C146
- page: 11
- line: 565
- line_src: lineno
- col: 1
- len: 69
- kind: Text
- author: xchlw
- text: 4.2.2时间窗Dijkstra. 一段行驶用标签设定（label-setting）搜索来规划。标签(𝑢, 𝑡) 表示「在时刻𝑡停在节点𝑢
- context: 4.2.2时间窗Dijkstra. 一段行驶用标签设定（label-setting）搜索来规划。标签(𝑢, 𝑡) 表示「在时刻𝑡停在节点𝑢
- comment: 如何搜索？逐跳规划or一次性规划？算法1？基本思想？
- Answer: 一次性规划：每次调用为一段行驶（空载段或满载段）从起点到终点规划完整路径，不是逐跳决策。基本思想：在普通 Dijkstra 上，把走廊的边权从固定通行时间换成「等到该走廊空闲所需的时间 + 通行时间」，等待时长由预约表查询得到。算法 1 是其伪代码。
- Modify:
  - 位置: paper_CN.tex L1066 句首（「一段行驶用标签设定……」之前）
  - 原文: （新增）
  - 改为: 基本思想是：在普通 Dijkstra 上，把走廊的边权从固定通行时间 $\tau_e$ 换成「等到该走廊空闲所需的时间 $+\tau_e$」，等待时长由预约表查询得到。每次调用为一段行驶（空载段或满载段）从起点到终点一次性规划完整路径，而非逐跳决策。
  - 理由: 先讲思想与规划方式。
- Status: applied

## C147
- page: 12
- line: 574
- line_src: lineno
- col: 10
- len: 7
- kind: Highlight
- author: xchlw
- text: 起点𝑠、终点𝑔
- context: Require: 起点𝑠、终点𝑔、最早出发时刻𝑡0、预约表𝑅、是否写入预约表的标志commit
- comment: none

## C148
- page: 12
- line: 590
- line_src: lineno
- col: 1
- len: 50
- kind: Text
- author: xchlw
- text: 引理1 (每个节点只需保留最早到达标签). 每个节点只保留到达最早的标签，即可得到在当前预约表下最早
- context: 引理1 (每个节点只需保留最早到达标签). 每个节点只保留到达最早的标签，即可得到在当前预约表下最早
- comment: 任务？车辆？
- Answer: 引理针对一次路由调用：一辆已选定的车执行一段行驶（某运输任务的空载段或满载段）。原文未说明对象。
- Modify:
  - 位置: paper_CN.tex L1073
  - 原文: 每个节点只保留到达最早的标签，即可得到在当前预约表下最早到达终点的路径。
  - 改为: 对给定车辆的一段行驶（某运输任务的空载段或满载段），每个节点只保留到达最早的标签，即可得到在当前预约表下该车最早到达终点的路径。
  - 理由: 说明对象。
- Status: applied

## C149
- page: 12
- line: 600-602
- line_src: lineno
- col: 1
- len: 96
- kind: Highlight
- author: xchlw
- text: 因此用普通Dijkstra 即可，不必像安全区间规划（SIPP）那样按可行时段分标签[8]；若再引入第二项指标（例如走廊时段附加代价），更早到达不再总是更好，须改用多标签搜索（第4.6 节）。
- context: 因此用普通Dijkstra 即可，不必像安全区间规划（SIPP）那样按可行时段分标签[8]；若再引入第二项指标 （例如走廊时段附加代价），更早到达不再总是更好，须改用多标签搜索（第4.6 节）。
- comment: none

## C150
- page: 12
- line: 604
- line_src: lineno
- col: 11
- len: 13
- kind: Highlight
- author: xchlw
- text: 这一点保证下文命题2 成立
- context: 再按畅通最短路行驶。这一点保证下文命题2 成立，因此搜索中不必对不可行解做修复。单次调用的代价为
- comment: none

## C151
- page: 12
- line: 609-612
- line_src: lineno
- col: 1
- len: 110
- kind: Text+Highlight
- author: xchlw
- text: 对空预约表，在所有取货–送货节点对上运行同一搜索，即得到第3 节的畅通最短路矩阵𝑡∗。它用于三处：开环配置里按畅通时间估计到达时刻、改派邻域中的邻近项，以及两阶段基线的运输时间；同时也是第4.5 节剪枝所用的可采纳下界。
- context: 对空预约表，在所有取货–送货节点对上运行同一搜索，即得到第3 节的畅通最短路矩阵𝑡∗。它用于三处：开 环配置里按畅通时间估计到达时刻、改派邻域中的邻近项，以及两阶段基线的运输时间；同时也是第4.5 节剪 枝所用的可采纳下界。
- comment: n个工件的工序总和？
- Answer: 配对存疑：评语应针对 4.3.1 节「设工序总数为 $N$」。是的，$N=\sum_j n_j$，即全部工件的工序总数（实验中 $12\times3=36$）。
- Modify:
  - 位置: paper_CN.tex L1125
  - 原文: 设工序总数为 $N$。
  - 改为: 设工序总数为 $N=\sum_{j\in J}n_j$。
  - 理由: 给出定义式。
- Status: applied

## C152
- page: 12
- line: 614
- line_src: lineno
- col: 1
- len: 15
- kind: Text
- author: xchlw
- text: 4.3上层：编码与事件驱动解码
- context: 4.3上层：编码与事件驱动解码
- comment: 向量元素为执行该工序的机器？
- Answer: 是，机器指派向量的第 $k$ 个元素是执行第 $k$ 道工序的机器编号（取自其可选集）。
- Modify:
  - 位置: paper_CN.tex L1125
  - 原文: 第 $k$ 个分量是第 $k$ 道工序在 $\Omega_{ji}$ 中所选的机械臂；
  - 改为: 第 $k$ 个分量是执行第 $k$ 道工序的机器编号（取自该工序的可选集 $\Omega_{ji}$）；
  - 理由: 更直白。
- Status: applied

## C153
- page: 12
- line: 615
- line_src: lineno
- col: 23
- len: 2
- kind: Text+Highlight
- author: xchlw
- text: 个体
- context: 4.3.1染色体编码. 设工序总数为𝑁。一个个体由两段构成：长度为𝑁的机器指派向量，按固定枚举，第𝑘个
- comment: 啥是个体？
- more_targets:
  - page=12 | line=615-617 | line_src=lineno | col=48 | len=24 | text=，第𝑘个分量是第𝑘道工序在Ω𝑗𝑖中所选的机械臂； | context=4.3.1染色体编码. 设工序总数为𝑁。一个个体由两段构成：长度为𝑁的机器指派向量，按固定枚举，第𝑘个 分量是第𝑘道工序在Ω𝑗𝑖中所选的机械臂；以及工序序列，即允许同一工件多次出现的排列——工件𝑗出现𝑛𝑗
- Answer: 个体即遗传算法种群中的一个染色体，对应一个候选解。
- Modify:
  - 位置: paper_CN.tex L1125
  - 原文: 一个个体由两段构成：
  - 改为: 一个个体（即遗传算法中的一个染色体，对应一个候选解）由两段构成：
  - 理由: 定义术语。
- Status: applied

## C154
- page: 12
- line: 617
- line_src: lineno
- col: 23
- len: 4
- kind: Text+Highlight
- author: xchlw
- text: 工序序列
- context: 分量是第𝑘道工序在Ω𝑗𝑖中所选的机械臂；以及工序序列，即允许同一工件多次出现的排列——工件𝑗出现𝑛𝑗
- comment: 机器指派向量的排序不体现工序序列？并行如何体现？
- Answer: 机器指派向量按固定枚举排列（$O_{11},O_{12},\dots$），其下标次序不表示执行顺序；执行顺序由第二段工序序列给出。并行无需显式编码：解码时每道工序在机器空闲且工件到达后即开工，不同机器上的工序、不同车辆的运输自然在时间上重叠；序列只决定争用同一机器或同一走廊时的先后。
- Modify:
  - 位置: paper_CN.tex L1128（「共用同一台机械臂的工序，相对顺序由它读出。」之后）
  - 原文: （新增）
  - 改为: 指派向量按固定枚举排列，其下标次序不表示执行顺序。并行无需显式编码：解码时每道工序在其机器空闲且工件到达后即开工，不同机器上的工序、不同车辆的运输因而在时间上自然重叠；序列只决定争用同一机器或同一走廊时的先后。
  - 理由: 解释编码如何体现顺序与并行。
- Status: applied

## C155
- page: 12
- line: 619
- line_src: lineno
- col: 1
- len: 12
- kind: Highlight
- author: xchlw
- text: 当𝛿ret = 1 时，
- context: 当𝛿ret = 1 时，每个工件在序列中额外出现一次，对应第3 节的伪工序（地点固定为𝑣0，加工时间为零）。返
- comment: none

## C156
- page: 12
- line: 622-623
- line_src: lineno
- col: 29
- len: 46
- kind: Text+Highlight
- author: xchlw
- text: ）。若另设第三段表示派车，搜索空间会扩大，且不能再保证任意染色体均可解码，从而需要修复算子。
- context: 任务派给哪辆车不写入染色体，而在解码时决定（第4.4 节）。若另设第三段表示派车，搜索空间会扩大，且 不能再保证任意染色体均可解码，从而需要修复算子。
- comment: 不可解？开销大？性能差？
- Answer: 主要是「需要修复」与「搜索空间扩大」两点：运输任务数随机器指派而变（式 (1)），派车段长度不固定，交叉、变异后可能与实际任务不对应，需要修复算子；同时搜索空间约扩大 $N_A^{|\mathcal{T}(x)|}$ 倍。这是设计上的论证，本文未做实验对比，原文表述过简。
- Modify:
  - 位置: paper_CN.tex L1133
  - 原文: 若另设第三段表示派车，搜索空间会扩大，且不能再保证任意染色体均可解码，从而需要修复算子。
  - 改为: 若另设第三段编码派车，会出现两个问题：一是运输任务数随机器指派而变（式~\eqref{eq:tasks}），派车段长度不固定，交叉与变异后可能与实际任务不对应，需要修复算子；二是搜索空间约扩大 $N_A^{|\mathcal{T}(x)|}$ 倍。因此派车留到解码时决定。
  - 理由: 说清原因。
- Status: applied

## C157
- page: 13
- line: 626
- line_src: lineno
- col: 10
- len: 14
- kind: Highlight
- author: xchlw
- text: 算例、路网、指派𝑥、工序序列
- context: Require: 算例、路网、指派𝑥、工序序列
- comment: none

## C158
- page: 13
- line: 646
- line_src: lineno
- col: 1
- len: 52
- kind: Text
- author: xchlw
- text: 4.3.2事件驱动解码器. 解码器（算法2）实现评价通路。它自左向右扫过工序序列，为每台机械臂维护其空闲
- context: 4.3.2事件驱动解码器. 解码器（算法2）实现评价通路。它自左向右扫过工序序列，为每台机械臂维护其空闲
- comment: 先讲整体，再讲局部 / 解码器的必要性？
- Answer: 采纳。4.3.2 节一上来就讲扫描细节；应先说明解码器做什么、为何必要：染色体只给出指派与顺序，不含车辆、路径与时刻，必须经解码模拟才能得到可行时间表与完工时间。
- Modify:
  - 位置: paper_CN.tex L1137
  - 原文: 解码器（算法~\ref{alg:decode}）实现评价通路。它自左向右扫过工序序列，
  - 改为: 解码器把一个染色体转换为可执行的时间表并计算其完工时间：染色体只给出机器指派与工序顺序，不含车辆、路径与时刻，必须经解码才能评价，它也因此是评价通路的实现（算法~\ref{alg:decode}）。具体地，它自左向右扫过工序序列，
  - 理由: 先整体后局部，说明必要性。
- Status: applied

## C159
- page: 13
- line: 646-647
- line_src: lineno
- col: 42
- len: 48
- kind: Text+Highlight
- author: xchlw
- text: 为每台机械臂维护其空闲时刻，为每个工件维护其当前节点与就绪时刻，为每辆车维护其当前节点与可用时刻
- context: 4.3.2事件驱动解码器. 解码器（算法2）实现评价通路。它自左向右扫过工序序列，为每台机械臂维护其空闲 时刻，为每个工件维护其当前节点与就绪时刻，为每辆车维护其当前节点与可用时刻。当某道工序的机械臂与
- comment: 如何做到？节点与机械臂的关系？
- Answer: 每台机器位于图中的固定节点 $\mathrm{loc}(m)$。解码器用三组状态变量记录资源状态，扫描时逐步更新（算法 2 第 1–2 行初始化，第 13–14 行更新）。原文未给出变量名与节点关系。
- Modify:
  - 位置: paper_CN.tex L1137-1139
  - 原文: 为每台机械臂维护其空闲时刻，为每个工件维护其当前节点与就绪时刻，为每辆车维护其当前节点与可用时刻。
  - 改为: 为每台机器维护其空闲时刻 $F_m$（每台机器位于图中的固定节点 $\mathrm{loc}(m)$），为每个工件维护其当前所在节点 $\mathrm{pos}_j$ 与就绪时刻 $\mathrm{ready}_j$，为每辆车维护其当前节点 $\mathrm{loc}_k$ 与可用时刻 $\mathrm{avail}_k$；每处理一道工序便更新这些状态。
  - 理由: 与算法 2 的变量对应。
- Status: applied

## C160
- page: 13
- line: 649
- line_src: lineno
- col: 13
- len: 7
- kind: Highlight
- author: xchlw
- text: 成式(1) 的
- context: 工件当前位置不同时，便生成式(1) 的运输任务，选定一辆车，并针对实时的预约表规划两段路径：到取货点
- comment: none

## C161
- page: 13
- line: 649
- line_src: lineno
- col: 25
- len: 5
- kind: Text+Highlight
- author: xchlw
- text: 选定一辆车
- context: 工件当前位置不同时，便生成式(1) 的运输任务，选定一辆车，并针对实时的预约表规划两段路径：到取货点
- comment: 如何选？
- Answer: 闭环默认用预约表感知派遣，开环用式 (12) 的畅通估计，详见 4.4 节；此处应就近指明。
- Modify:
  - 位置: paper_CN.tex L1140
  - 原文: 选定一辆车，
  - 改为: 选定一辆车（闭环默认用预约表感知派遣，开环用式~\eqref{eq:rule} 的畅通估计，见第~\ref{sec:dispatch}~节），
  - 理由: 就近说明。
- Status: applied

## C162
- page: 13
- line: 650
- line_src: lineno
- col: 18
- len: 6
- kind: Highlight
- author: xchlw
- text: 式(6) 衔
- context: 的空载段与到目的地的满载段，两者由式(6) 衔接。随后工序按式(10) 开工；解码器同时记下开工由哪一项决
- comment: none

## C163
- page: 13
- line: 650
- line_src: lineno
- col: 31
- len: 8
- kind: Highlight
- author: xchlw
- text: 式(10) 开工
- context: 的空载段与到目的地的满载段，两者由式(6) 衔接。随后工序按式(10) 开工；解码器同时记下开工由哪一项决
- comment: none

## C164
- page: 13
- line: 652
- line_src: lineno
- col: 33
- len: 5
- kind: Text+Highlight
- author: xchlw
- text: 按固定规则
- context: 解码具有确定性：预约按解码器生成任务的次序写入；两处时刻相同时均按固定规则决定先后——路由的标
- comment: 啥规则？
- Answer: 规则即冒号后所列的两条平局规则：路由的标签队列以（到达时刻，节点编号）为键；派车按车辆编号升序扫描、保留首个严格更优者。「按固定规则」读起来像另有所指。
- Modify:
  - 位置: paper_CN.tex L1177
  - 原文: 两处时刻相同时均按固定规则决定先后——
  - 改为: 两处时刻相同时均按如下固定的平局规则决定先后：
  - 理由: 表明规则即后文所列。
- Status: applied

## C165
- page: 13
- line: 655
- line_src: lineno
- col: 22
- len: 21
- kind: Highlight
- author: xchlw
- text: 染色体总对应唯一一张时间表，评价是确定性的
- context: 留首个严格更优者（第4.5 节）。因此一个染色体总对应唯一一张时间表，评价是确定性的。第5 节按种子配对、
- comment: none

## C166
- page: 13
- line: 655-656
- line_src: lineno
- col: 43
- len: 28
- kind: Text+Highlight
- author: xchlw
- text: 。第5 节按种子配对、比较同一预算下的结果，依赖这一点。
- context: 留首个严格更优者（第4.5 节）。因此一个染色体总对应唯一一张时间表，评价是确定性的。第5 节按种子配对、 比较同一预算下的结果，依赖这一点。
- comment: 冲突？死锁？完工时间？
- more_targets:
  - page=13 | line=659 | line_src=lineno | col=9 | len=4 | text=的时间表 | context=锁且完工时间有限的时间表。因此搜索中不必调用修复算子。
- Answer: 配对存疑：评语应针对命题 2 中的「无冲突、无死锁且完工时间有限的时间表」。三者含义：无冲突——任意两次走廊占用区间互不重叠；无死锁——不存在车辆之间的循环等待；完工时间有限——所有工序都能在有限时刻完成。
- Modify:
  - 位置: paper_CN.tex L1183
  - 原文: 并返回一张无冲突、无死锁且完工时间有限的时间表。
  - 改为: 并返回一张满足以下三点的时间表：(a) 无冲突，即同一走廊上任意两次占用的区间互不重叠（式~\eqref{eq:excl}）；(b) 无死锁，即不存在车辆之间的循环等待；(c) 完工时间有限。
  - 理由: 逐项说明。
- Status: applied

## C167
- page: 13
- line: 672
- line_src: lineno
- col: 1
- len: 13
- kind: Text
- author: xchlw
- text: 4.4预约表感知的车辆派遣
- context: 4.4预约表感知的车辆派遣
- comment: 如何派车没讲清楚
- Answer: 采纳。4.4 节的文字描述了思路，但缺少可执行的步骤，且剪枝与复用分散在 4.5 节，读者难以拼出完整流程。建议给出分步描述（或补一个伪代码算法）。
- Modify:
  - 位置: paper_CN.tex L1211（「选中的是可行送达最早的车辆……」之后）
  - 原文: （新增）
  - 改为: 完整流程如下。对每个运输任务：(1) 按车辆编号升序遍历车辆 $k$；(2) 计算下界 $\mathrm{lb}(k)$（式~\eqref{eq:lb_dispatch}），若不早于当前最好送达时刻则跳过（第~\ref{sec:speedup}~节）；(3) 保存预约表状态，从 $\mathrm{loc}_k$ 到取货点试算空载段并临时写入，再从取货点到目的地试算满载段，得到送达时刻 $\mathrm{est}(k)$；(4) 回滚预约表；若 $\mathrm{est}(k)$ 严格早于当前最好，则记 $k$ 为当前胜者并缓存其两段路径；(5) 遍历结束后，把胜者的缓存路径正式写入预约表。
  - 理由: 讲清如何派车。
  - 联动: 可另加算法 3「预约表感知派遣」伪代码
- Status: applied

## C168
- page: 13
- line: 673
- line_src: lineno
- col: 1
- len: 26
- kind: Highlight
- author: xchlw
- text: 选车既可以按畅通最短路时间估计，也可以按预约表上的试
- context: 选车既可以按畅通最短路时间估计，也可以按预约表上的试算。开环规则对每辆车打分
- comment: none

## C169
- page: 13
- line: 673
- line_src: lineno
- col: 34
- len: 5
- kind: Text+Highlight
- author: xchlw
- text: 每辆车打分
- context: 选车既可以按畅通最短路时间估计，也可以按预约表上的试算。开环规则对每辆车打分
- comment: 目的？
- Answer: 打分即估计该车完成本任务的送达时刻，分数最小者被选中；原文未说明打分的含义与用法。
- Modify:
  - 位置: paper_CN.tex L1200
  - 原文: 开环规则对每辆车打分
  - 改为: 开环规则按畅通最短路估计每辆车完成该任务的送达时刻，并选估计值最小的车辆：
  - 理由: 说明目的。
- Status: applied

## C170
- page: 14
- line: 677
- line_src: lineno
- col: 19
- len: 10
- kind: Text+Highlight
- author: xchlw
- text: 走廊上却已占用的车辆
- context: 它不查预约表，因此可能选中几何上近、走廊上却已占用的车辆。该式与Li 等[10] 的空闲优先派车相同，也
- comment: 空载、满载交替出现？
- more_targets:
  - page=14 | line=680 | line_src=lineno | col=21 | len=24 | text=：先规划空载段并将其临时写入预约表，再规划满载段 | context=闭环默认改用预约表感知派遣。对每辆候选车：先规划空载段并将其临时写入预约表，再规划满载段，记下
- Answer: 是。每个运输任务都由空载段（车从当前位置去取货点）和满载段（载工件去目的地）组成；同一车连续执行任务时，空载与满载交替出现。车已在取货点时空载段为零。
- Modify:
  - 位置: paper_CN.tex L1209
  - 原文: 对每辆候选车：先规划空载段并将其临时写入预约表，再规划满载段，
  - 改为: 对每辆候选车（每个运输任务都包含两段：空载段从车辆当前位置到取货点，满载段从取货点到目的地；车辆已在取货点时空载段为零）：先规划空载段并将其临时写入预约表，再规划满载段，
  - 理由: 说明两段的构成。
- Status: applied

## C171
- page: 14
- line: 686
- line_src: lineno
- col: 1
- len: 7
- kind: Highlight
- author: xchlw
- text: 该机制的代价是
- context: 该机制的代价是：试算将每个运输任务的路由调用从2 次增至至多2𝑁𝐴次，单次评价开销约为规则派车的
- comment: none

## C172
- page: 14
- line: 688
- line_src: lineno
- col: 1
- len: 20
- kind: Highlight
- author: xchlw
- text: 第5 节因此只在同一挂钟时限下比较两种派
- context: 第5 节因此只在同一挂钟时限下比较两种派车。
- comment: none

## C173
- page: 14
- line: 692
- line_src: lineno
- col: 22
- len: 7
- kind: Highlight
- author: xchlw
- text: 按相同代数比较
- context: 预约表感知派遣在同挂钟预算下面临如下问题：按相同代数比较，预约表感知派遣比规则派车好2.90%（图7）；
- comment: none

## C174
- page: 14
- line: 692
- line_src: lineno
- col: 31
- len: 22
- kind: Text+Highlight
- author: xchlw
- text: 约表感知派遣比规则派车好2.90%（图7）；
- context: 预约表感知派遣在同挂钟预算下面临如下问题：按相同代数比较，预约表感知派遣比规则派车好2.90%（图7）；
- comment: 如何得到的？
- Answer: 来自比较协议对照实验（图 7）：同一算例、同一种子下，两种派车各运行相同代数，取完工时间的配对相对差的均值。原文未交代来源。
- Modify:
  - 位置: paper_CN.tex L1222
  - 原文: 按相同\emph{代数}比较，预约表感知派遣比规则派车好 \GainProbeSameGen{}（图~\ref{fig:protocols}）；
  - 改为: 按相同\emph{代数}比较（同一算例与种子下两种派车各运行相同代数，取完工时间的配对相对差，见图~\ref{fig:protocols} 与第~\ref{sec:protocol}~节），预约表感知派遣比规则派车好 \GainProbeSameGen{}；
  - 理由: 说明数据来源。
- Status: applied

## C175
- page: 14
- line: 693
- line_src: lineno
- col: 1
- len: 18
- kind: Highlight
- author: xchlw
- text: 但其单次评价开销为后者的12.2 倍
- context: 但其单次评价开销为后者的12.2 倍，在相同挂钟时间下，这一增益被额外的计算开销抵消，净效果接近零。因
- comment: none

## C176
- page: 14
- line: 693
- line_src: lineno
- col: 31
- len: 18
- kind: Highlight
- author: xchlw
- text: 增益被额外的计算开销抵消，净效果接近
- context: 但其单次评价开销为后者的12.2 倍，在相同挂钟时间下，这一增益被额外的计算开销抵消，净效果接近零。因
- comment: none

## C177
- page: 15
- line: 733
- line_src: lineno
- col: 4
- len: 17
- kind: Text+Highlight
- author: xchlw
- text: 另两种层间接口：附加代价与让行记录
- context: 4.6另两种层间接口：附加代价与让行记录
- comment: 目的和作用？
- Answer: 目的：检验下层若传递比完工时间更丰富的信息（哪条走廊在何时拥堵、哪次让行由谁造成），能否进一步降低完工时间。作用：作为对照，结果表明二者在等算力下都没有净收益，说明实现时长已足够。由于这是负面结果，建议把本节移到第 5 章讨论，方法章只保留一句说明。
- Modify:
  - 位置: paper_CN.tex L1266（4.6 节首段之前）
  - 原文: （新增）
  - 改为: 本节的目的是检验：若下层向上层传递比完工时间更丰富的信息（哪条走廊在何时拥堵、哪次让行由谁造成），能否进一步降低完工时间。为此实现两种接口作为对照；第~\ref{sec:pricing}~节的结果表明，二者在等算力下都没有带来净收益。
  - 理由: 交代目的与作用。
  - 联动: 可考虑把 4.6 节整体移到第 5 章
- Status: applied

## C178
- page: 15
- line: 760
- line_src: lineno
- col: 1
- len: 13
- kind: Highlight
- author: xchlw
- text: 4.7按让行记录的局部搜索
- context: 4.7按让行记录的局部搜索
- comment: none

## C179
- page: 16
- line: 817
- line_src: lineno
- col: 1
- len: 9
- kind: Text+Highlight
- author: xchlw
- text: 4.8外层遗传算法
- context: 4.8外层遗传算法
- comment: 外层的含义？
- Answer: 「外层」指上层文化基因算法中的全局进化部分（相对于内层的局部搜索），与「上层」容易混淆，统一改称。
- Modify:
  - 位置: paper_CN.tex L1355
  - 原文: \subsection{外层遗传算法}
  - 改为: \subsection{上层的遗传算法（全局搜索）}\label{sec:ga}
  - 理由: 消除歧义；加标签供 C131 引用。
  ---
  - 位置: paper_CN.tex L1357
  - 原文: 外层采用常规的种群搜索。
  - 改为: 上层文化基因算法的全局部分采用常规遗传算法。
  - 理由: 术语统一。
- Status: applied

## C180
- page: 16
- line: 820
- line_src: lineno
- col: 30
- len: 6
- kind: Highlight
- author: xchlw
- text: 择用锦标赛并
- context: 个把每道工序指派给其最快机械臂，一个按负载均衡贪心指派。选择用锦标赛并保留少量精英。交叉时，序列
- comment: none

## C181
- page: 17
- line: 849-850
- line_src: lineno
- col: 1
- len: 74
- kind: Text+Highlight
- author: xchlw
- text: 本节回答四个问题：将让行等待纳入适应度（闭环）带来多大收益？预约表感知派遣再带来多大收益，它能否替代闭环，二者合用时是否相互放大？这些收益在多大的算
- context: 本节回答四个问题：将让行等待纳入适应度（闭环）带来多大收益？预约表感知派遣再带来多大收益，它能否 替代闭环，二者合用时是否相互放大？这些收益在多大的算例范围内成立，以现有种子数能否确定其成立范围？
- comment: 归纳为不同的实验目的和实验方案 / 通常先有整体性能对比，再有消融实验分析 / 1. 实验方案（目的、和谁比、比什么） / 2. 实验环境（数据集、参数、软硬件配置） / 3. 实验结果（与实验方案一一对应，突出结果原因分析，体现工作优势）
- more_targets:
  - page=17 | line=850-851 | line_src=lineno | col=1 | len=74 | text=替代闭环，二者合用时是否相互放大？这些收益在多大的算例范围内成立，以现有种子数能否确定其成立范围？已实现但未取得净收益的其他接口，其失效原因是什么？ | context=替代闭环，二者合用时是否相互放大？这些收益在多大的算例范围内成立，以现有种子数能否确定其成立范围？ 已实现但未取得净收益的其他接口，其失效原因是什么？
- Answer: 采纳。第 5 章目前按「四个问题」组织，但实验方案、环境与结果混在一起，且未先做整体对比。按审阅人建议重组为「方案 → 环境 → 结果」，结果先整体对比，再消融。
- Modify:
  - 位置: paper_CN.tex 第 5 章结构
  - 原文: 5.1 实验设置（算例族、比较协议、实现环境混排）；5.2 四级基线阶梯；……
  - 改为: 5.1 实验方案（四个实验目的 → 对比对象 → 评价指标，用一张表列出）；5.2 实验环境（算例族与数据集、参数、软硬件，见 C202）；5.3 整体性能对比（B0、B0+、B1、B2 的端到端结果）；5.4 消融分析（闭环评价、预约表感知派遣、两项加速）；5.5 敏感性分析（按争用强度、车臂比、柔性）；5.6 其他层间接口与讨论（原 4.6 节内容可移入）。
  - 理由: 按审阅人建议重组。
  ---
  - 位置: paper_CN.tex L1382-1384
  - 原文: 本节回答四个问题：……其失效原因是什么？
  - 改为: 本节实验方案见表~X：实验一比较四个配置的端到端性能；实验二通过 $2\times2$ 消融分别度量闭环评价与预约表感知派遣的贡献；实验三考察收益随争用强度、车臂比与柔性的变化；实验四检验另两种层间接口。各实验的对比对象与指标见表~X。
  - 理由: 以方案代替问题列表。
  - 联动: 需新增「实验方案」表
- Status: applied（结构性大改，需作者确认）

## C182
- page: 17
- line: 854
- line_src: lineno
- col: 1
- len: 7
- kind: Text
- author: xchlw
- text: 5.1实验设置
- context: 5.1实验设置
- comment: 已有工作实验数据集？
- Answer: 已有工作主要使用 Homayouni 与 Fontes 整理的公开 FJSP_PT 基准（矩阵形式，不含走廊网络），不能直接用于本文问题，5.1.1 节说明了原因；5.6 节在去掉争用约束后用该基准做退化对标。原文开头没有先交代这一点。
- Modify:
  - 位置: paper_CN.tex L1390 段首
  - 原文: FJSP\_PT 基准通常把行驶时间写成按位置对索引的矩阵，
  - 改为: 已有 FJSP\_PT 工作普遍采用 Homayouni 与 Fontes~\cite{homayouni2021production} 整理的公开基准，但它不能直接用于本文问题：该基准把行驶时间写成按位置对索引的矩阵，
  - 理由: 先交代已有数据集。
- Status: applied

## C183
- page: 17
- line: 855
- line_src: lineno
- col: 6
- len: 4
- kind: Highlight
- author: xchlw
- text: 受控算例
- context: 5.1.1受控算例族. FJSP_PT 基准通常把行驶时间写成按位置对索引的矩阵，只记端点之间的总时长，不给出走
- comment: none

## C184
- page: 17
- line: 860
- line_src: lineno
- col: 12
- len: 9
- kind: Text+Highlight
- author: xchlw
- text: 文献参考值不再可比
- context: 得到的将是另一个算例，文献参考值不再可比。因此本文生成一组受控算例：路网显式给出，第3.7 节的特征
- comment: 想说明啥？
- Answer: 想说明：不能把公开基准改造成本文的算例来与文献结果比较——改造后算例已变，文献报告的完工时间不再适用。
- Modify:
  - 位置: paper_CN.tex L1395
  - 原文: 若由矩阵反推路网，得到的将是另一个算例，文献参考值不再可比。
  - 改为: 因此，即使由矩阵反推出一张路网，所得也是一个不同的算例，文献中报告的完工时间不再适用于它，无法用于横向比较。
  - 理由: 说清含义。
- Status: applied

## C185
- page: 17
- line: 860-863
- line_src: lineno
- col: 41
- len: 80
- kind: Text+Highlight
- author: xchlw
- text: ，第3.7 节的特征量可逐个单独变化。另有一种公开算例上的比较——删去争用约束、退回与文献同一数学问题——见第5.8 节，它标定的是上层搜索强度，不是本文框架。
- context: 得到的将是另一个算例，文献参考值不再可比。因此本文生成一组受控算例：路网显式给出，第3.7 节的特征 量可逐个单独变化。另有一种公开算例上的比较——删去争用约束、退回与文献同一数学问题——见第5.8 节， 它标定的是上层搜索强度，不是本文框架。
- comment: 工序长短不一？
- more_targets:
  - page=17 | line=864 | line_src=lineno | col=18 | len=18 | text=、每工件3 道工序共36 道真实工序 | context=全部算例共用同一核心：12 个工件、每工件3 道工序共36 道真实工序、8 台机械臂、异构度𝐻= 0.3，运输
- Answer: 每个工件的工序数相同（3 道），但各工序的加工时间不同，且随所选机器而变（异构度 $H=0.3$）。
- Modify:
  - 位置: paper_CN.tex L1399
  - 原文: $12$ 个工件、每工件 $3$ 道工序共 $36$ 道真实工序、
  - 改为: $12$ 个工件、每工件 $3$ 道工序（各工序加工时间不同，且随所选机器而变）共 $36$ 道真实工序、
  - 理由: 回答疑问。
- Status: applied

## C186
- page: 17
- line: 865
- line_src: lineno
- col: 35
- len: 3
- kind: Highlight
- author: xchlw
- text: 十组上
- context: 与加工时间比𝑇𝑡̄/𝑇 𝑝̄标到4.0，使车辆争用成为主要约束。𝐻在十组上同为0.3，不随柔性变化。生成器对每道
- comment: none

## C187
- page: 17
- line: 865
- line_src: lineno
- col: 51
- len: 3
- kind: Highlight
- author: xchlw
- text: 生成器
- context: 与加工时间比𝑇𝑡̄/𝑇 𝑝̄标到4.0，使车辆争用成为主要约束。𝐻在十组上同为0.3，不随柔性变化。生成器对每道
- comment: none

## C188
- page: 17
- line: 868
- line_src: lineno
- col: 14
- len: 2
- kind: Text+Highlight
- author: xchlw
- text: 变𝐹
- context: |Ω𝑗𝑖| 无关，C 族改变𝐹不会改变𝐻。取整带来的小偏差在生成后实测，并随算例记录。在此核心上沿三个方向
- comment: 不同场景？
- Answer: C 族改变柔性度 $F$，对应机器通用程度不同的车间：从每道工序只能在少数机器上加工（$F=0.3$）到可在全部机器上加工（$F=1.0$）。
- Modify:
  - 位置: paper_CN.tex L1402
  - 原文: C 族改变 $F$ 不会改变 $H$。
  - 改为: C 族改变 $F$（对应机器通用程度不同的车间）不会改变 $H$。
  - 理由: 点明场景。
- Status: applied

## C189
- page: 17
- line: 873
- line_src: lineno
- col: 14
- len: 13
- kind: Highlight
- author: xchlw
- text: 量产厂房中常见的脊式布局—
- context: 或两条并行出口接入。这对应量产厂房中常见的脊式布局——加工区沿中央走廊两侧排列，厂内搬运走这条中
- comment: none

## C190
- page: 17
- line: 875-877
- line_src: lineno
- col: 44
- len: 27
- kind: Highlight
- author: xchlw
- text: ，是有意构造的高争用情形，也正是闭环机制要处理的情形。
- context: 缩短运输、分散走廊占用；本文将𝑣0 置于脊的一端，全部运输都须经过同一出口与同一段中廊，是有意构造的 高争用情形，也正是闭环机制要处理的情形。选用脊式布局，还因为它把争用集中在可增删的并行通道上：增
- comment: none

## C191
- page: 17
- line: 878
- line_src: lineno
- col: 15
- len: 35
- kind: Highlight
- author: xchlw
- text: 串联式单车环使车辆互不相遇[17]，几乎没有争用，不适合本文的研究目的
- context: 一条通道只改容量、不改路程；串联式单车环使车辆互不相遇[17]，几乎没有争用，不适合本文的研究目的。
- comment: none

## C192
- page: 17
- line: 879-880
- line_src: lineno
- col: 28
- len: 45
- kind: Highlight
- author: xchlw
- text: ：网格——路口多，绕行也多，被占走廊可以改道，争用下降，但上下料点到最远机械臂的路程变长。
- context: 脊式布局仅覆盖高争用区间。覆盖低争用区间需要另一种拓扑：网格——路口多，绕行也多，被占走廊可以 改道，争用下降，但上下料点到最远机械臂的路程变长。五组算例因此分成两种拓扑：funnel、high、mid 为
- comment: none

## C193
- page: 18
- line: 899
- line_src: lineno
- col: 1
- len: 13
- kind: Highlight
- author: xchlw
- text: B 族：车臂比𝑁𝐴/𝑁𝑀。
- context: B 族：车臂比𝑁𝐴/𝑁𝑀。在funnel 上取𝑁𝐴∈{4, 8, 12, 16}，即车臂比0.5、1.0、1.5、2.0，其中1.5 为三族共用
- comment: none

## C194
- page: 18
- line: 901
- line_src: lineno
- col: 1
- len: 7
- kind: Highlight
- author: xchlw
- text: C 族：柔性𝐹
- context: C 族：柔性𝐹。在同一布局上取𝐹∈{0.3, 0.6, 1.0}，即每道工序可选机械臂的比例，其中0.6 同为基点。|Ω𝑗𝑖|
- comment: none

## C195
- page: 18
- line: 913-917
- line_src: lineno
- col: 1
- len: 221
- kind: Highlight
- author: xchlw
- text: 与公开算例的对照。. 自建算例的𝐻、𝐹与𝑇𝑡̄/ 𝑇𝑝̄以Homayouni 与Fontes [6] 整理的20 个公开算例为外部参照（第5.8 节亦用其做退化对标）；两者的特征以同一特征函数、同一口径计算，可直接比较。柔性中位为0.38，本节基点0.6 约为其一倍半，C 族𝐹= 0.3 落在公开区间内；异构度中位仅0.135，20 个算例中最大为0.258，无一达到本节的𝐻= 0.3；𝑇𝑡̄/𝑇 𝑝̄公开最高仅0.12，本节标到4.0。
- context: 与公开算例的对照。. 自建算例的𝐻、𝐹与𝑇𝑡̄/ 𝑇𝑝̄以Homayouni 与Fontes [6] 整理的20 个公开算例为外部参 照（第5.8 节亦用其做退化对标）；两者的特征以同一特征函数、同一口径计算，可直接比较。柔性中位为0.38， 本节基点0.6 约为其一倍半，C 族𝐹= 0.3 落在公开区间内；异构度中位仅0.135，20 个算例中最大为0.258，无 一达到本节的𝐻= 0.3；𝑇𝑡̄/𝑇 𝑝̄公开最高仅0.12，本节标到4.0。
- comment: none

## C196
- page: 18
- line: 924
- line_src: lineno
- col: 1
- len: 18
- kind: Highlight
- author: xchlw
- text: 5.1.2比较协议. 比较依赖下列规
- context: 5.1.2比较协议. 比较依赖下列规则。
- comment: none

## C197
- page: 18
- line: 926
- line_src: lineno
- col: 19
- len: 28
- kind: Highlight
- author: xchlw
- text: 开环按畅通行驶时间排出的完工时间，在真实走廊上往往不可行
- context: 统一执行器：报可实现的完工时间。. 开环按畅通行驶时间排出的完工时间，在真实走廊上往往不可行。因
- comment: none

## C198
- page: 19
- line: 953-954
- line_src: lineno
- col: 1
- len: 67
- kind: Highlight
- author: xchlw
- text: 表5. 实验批次一览。主批次支撑表7 与表8 的全部统计结论；其余批次各回答一个具体问题，不与主批次逐组并列。「加速」指第4.5 节的
- context: 表5. 实验批次一览。主批次支撑表7 与表8 的全部统计结论；其余批次各回答一个具体问题，不与主批次逐组并列。「加速」 指第4.5 节的剪枝与胜者路径复用是否已实现。附加代价机制与按让行记录的局部搜索在加速前后没有改动，其开销也不受
- comment: none

## C199
- page: 19
- line: 975
- line_src: lineno
- col: 1
- len: 7
- kind: Highlight
- author: xchlw
- text: 种子与配对检验
- context: 种子与配对检验。. 单一种子不足以支撑结论：同一算例、同一配置下，三个种子之间观察到11 个完工时间
- comment: none

## C200
- page: 19
- line: 981
- line_src: lineno
- col: 1
- len: 8
- kind: Highlight
- author: xchlw
- text: 多重比较与效应量
- context: 多重比较与效应量。. 全文二十余个Wilcoxon 检验。不校正则「十组里至少一处显著」在全零假设下约40%，
- comment: none

## C201
- page: 19
- line: 981
- line_src: lineno
- col: 13
- len: 16
- kind: Highlight
- author: xchlw
- text: 文二十余个Wilcoxon 检验
- context: 多重比较与效应量。. 全文二十余个Wilcoxon 检验。不校正则「十组里至少一处显著」在全零假设下约40%，
- comment: none

## C202
- page: 20
- line: 1004
- line_src: lineno
- col: 1
- len: 73
- kind: Text
- author: xchlw
- text: 5.1.3实现与运行环境. 实验在Intel Xeon W-1270 @ 3.40 GHz 上单线程运行；实现为纯Python（≥3.9.6），仅
- context: 5.1.3实现与运行环境. 实验在Intel Xeon W-1270 @ 3.40 GHz 上单线程运行；实现为纯Python（≥3.9.6），仅
- comment: 实验参数
- Answer: 采纳。实验参数散落在 5.1.3 节的一段文字中，建议汇总为参数表。
- Modify:
  - 位置: paper_CN.tex L1537-1539
  - 原文: 外层遗传算法与局部搜索超参取默认值，未调参，全部配置一致：种群 $60$、……至多三轮。
  - 改为: 新增表「实验参数」：种群规模 60；交叉概率 0.8；变异概率 0.2；精英数 5；选择方式 二元锦标赛；局部搜索作用比例 前 10\%；每轮关键工序数 $L=5$；局部搜索轮数 ≤3；挂钟预算（取第~\ref{sec:protocol}~节的值）；每组种子数 \NSeeds{}；算例组数 \NCases{}；硬件 Intel Xeon W-1270 @ 3.40\,GHz 单线程；实现 纯 Python $\ge 3.9.6$。正文保留「超参未调参、各配置一致」一句并引用该表。
  - 理由: 便于查阅与复现。
- Status: applied

## C203
- page: 20
- line: 1005
- line_src: lineno
- col: 21
- len: 28
- kind: Highlight
- author: xchlw
- text: 外层遗传算法与局部搜索超参取默认值，未调参，全部配置一致
- context: 用标准库，无第三方依赖，亦不依赖求解器。外层遗传算法与局部搜索超参取默认值，未调参，全部配置一致：
- comment: none

## C204
- page: 20
- line: 1015-1016
- line_src: lineno
- col: 1
- len: 49
- kind: Highlight
- author: xchlw
- text: 比较需分别回答两个问题：与文献中常见的流程结构对齐时完工时间相差多少，以及只改变一个部件时相差多少
- context: 比较需分别回答两个问题：与文献中常见的流程结构对齐时完工时间相差多少，以及只改变一个部件时相差多 少。前者要求结构对应，后者要求一次只改变一处。仅报告消融无法与常见流程结构对应；仅报告文献比较则
- comment: none

## C205
- page: 20
- line: 1016
- line_src: lineno
- col: 1
- len: 38
- kind: Highlight
- author: xchlw
- text: 少。前者要求结构对应，后者要求一次只改变一处。仅报告消融无法与常见流程结构对
- context: 少。前者要求结构对应，后者要求一次只改变一处。仅报告消融无法与常见流程结构对应；仅报告文献比较则
- comment: none

## C206
- page: 20
- line: 1016-1017
- line_src: lineno
- col: 38
- len: 55
- kind: Highlight
- author: xchlw
- text: 对应；仅报告文献比较则会将无冲突路由本身的收益计入本文机制。因此采用四级阶梯，每一级对应一种可明确指认的结构。
- context: 少。前者要求结构对应，后者要求一次只改变一处。仅报告消融无法与常见流程结构对应；仅报告文献比较则 会将无冲突路由本身的收益计入本文机制。因此采用四级阶梯，每一级对应一种可明确指认的结构。
- comment: none

## C207
- page: 29
- line: 1474
- line_src: lineno
- col: 1
- len: 19
- kind: Highlight
- author: xchlw
- text: 5.7案例：漏斗算例上的甘特图与关键链
- context: 5.7案例：漏斗算例上的甘特图与关键链
- comment: none

## C208
- page: 29
- line: 1485
- line_src: lineno
- col: 1
- len: 13
- kind: Highlight
- author: xchlw
- text: 5.8公开基准上的退化比较
- context: 5.8公开基准上的退化比较
- comment: none

## C209
- page: 32
- line: 1653
- line_src: lineno
- col: 1
- len: 5
- kind: Text
- author: xchlw
- text: 6.1总结
- context: 6.1总结
- comment: 工作？贡献？结论？
- Answer: 采纳。6.1 节与 1.5 节贡献几乎逐条重复，没有区分「做了什么」「贡献是什么」「结论是什么」。
- Modify:
  - 位置: paper_CN.tex 第 6 章结构（L2005-2030）
  - 原文: 6.1 总结（四条，与 1.5 节对应）
  - 改为: 6.1 工作总结：一段话概述问题、方法与实验；6.2 主要结论：三条带数字的结论（闭环主效应 \GainLoopRule{}；派遣次效应 \GainProbeLoop{} 且需合并检验；两者不可替代、不放大）；6.3 局限；6.4 展望。贡献不再在结论中重复。
  - 理由: 区分工作、贡献与结论。
- Status: applied

## C210
- page: 33
- line: 1677-1679
- line_src: lineno
- col: 46
- len: 17
- kind: Highlight
- author: xchlw
- text: 故本文不就机制随规模的变化作结论。
- context: (1) 算例族的范围，以及采用自建算例的原因。主实验固定规模、只改变结构（第3.7 节），故本文不就机制随 规模的变化作结论。异构度𝐻在主实验中固定为0.3。𝐻的影响只在第5.4 节的独立算例上检验过：该批算例
- comment: none

## C211
- page: 34
- line: 1726
- line_src: lineno
- col: 1
- len: 10
- kind: Text+Highlight
- author: xchlw
- text: References
- context: References
- comment: 格式
- Answer: 中文稿的参考文献标题显示为英文「References」（acmart 默认），应改为「参考文献」；同时检查条目格式（如 C212 所标「2024.」一条年份位置）是否统一。
- Modify:
  - 位置: paper_CN.tex 导言区（\begin{document} 之前）
  - 原文: （无）
  - 改为: \renewcommand{\refname}{参考文献}（若无效，再试 \renewcommand{\bibname}{参考文献}）
  - 理由: 中文稿标题应为中文。
  - 联动: 按目标期刊的 bst 检查卷、期、页码、DOI 字段完整性
- Status: applied

## C212
- page: 34
- line: 1727
- line_src: lineno
- col: 75
- len: 5
- kind: Highlight
- author: xchlw
- text: 2024.
- context: [1] Stéphane Dauzère-Pérès, Junwen Ding, Liji Shen, and Karim Tamssaouet. 2024. The Flexible Job Shop Scheduling Problem: A Review. European
- comment: none
