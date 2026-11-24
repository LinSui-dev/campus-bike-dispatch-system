# 智能体协作规则

先读README、docs/00-开发入口.md、docs/10-团队分工与开发计划.md，再读自己的docs/roles任务书。课程原始要求见根目录项目要求.png与附件2：论文版面示例.doc。仅做P0。

六人：A后端与引擎、B调度与实验、C前端、D地图路网数据、E联调测试、F文档。各自独立分支或worktree，禁止多个可写智能体共享工作目录。只修改自己拥有的文件，详见分工表。

contracts/是v1公共契约，E维护。变更通过docs/integration/requests/<成员>-<主题>.md提出，由E协调受影响成员后修改版本、示例和测试。不得单方面改字段、枚举、模块签名或他人文件。各人可写docs/handoffs/<成员>/交接报告。F维护其他文档，不虚构结果和贡献。

引擎不依赖HTTP或ORM；算法不能读取未来实际事件；UI不能修改库存。只有运行管理器推进引擎。固定种子和稳定排序，墙钟不得决定模拟结果。未实现功能明确501或NotImplementedError，不伪装成功。fixture不是校园实测。

成员各自维护模块单元测试，E维护跨模块验收。不得删除断言或跳过失败来通过检查。交接须含改动、命令和实际结果、未完成项、契约影响。E串行集成，合并后复验，禁止force push公共分支。

所有成员还须读docs/13-验收矩阵.md。docs/10的唯一文件归属表优先于任务书摘要；分发前准备工作由当前协调者统一更新基线，正式六人开工后执行各自归属。按docs/handoffs/TEMPLATE.md交接，ready不代表accepted。E可在各报告的接收结论节填写复验结果，其余正文由对应成员维护。

常规检查不含scaffold和acceptance；骨架诊断仅显式运行，业务实现后无需继续保持501。正式验收用scripts/check.ps1 -Acceptance，未建立测试视为未验收，不得放过退出码5。测试替身仅用于模块自测，不能导入生产代码。

完成明确交接范围、自测并填写handoff后，提交并推送到docs/10规定的本人分支：A=feat/a-engine，B=feat/b-dispatch，C=feat/c-frontend，D=feat/d-map，E=test/e-integration，F=docs/f-delivery。用户已授权这些个人分支的成果推送，无需再次确认；核对origin与当前分支，只暂存本人文件，推送后核对远程SHA并返回分支链接。禁止个人交付直接推main或force push；E仍按11承担公共集成。
