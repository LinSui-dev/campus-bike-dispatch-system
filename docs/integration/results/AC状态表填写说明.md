# 最终AC状态表

E维护最终docs/integration/results/acceptance.json；当前尚未建立，不创建伪装通过的记录。模板见acceptance-template.json，复制后只能根据实际结果更新。每个AC的actual_result写真实操作和结果，evidence是仓库内已存在文件路径，可指日志、人工矩阵、截图或交接报告。

每项需要reviewer、status（pending/failed/passed）、actual_result和至少一个证据路径。根commit填写实际被测完整40位SHA，contract_version必须与版本文件一致。自动检查只验证24项齐全、均为passed、路径存在和必要字段；它不能判断截图真假、结论正确与否，E必须实际审阅。

正式门禁依次运行常规检查、非空真实业务验收测试、状态表检查。没有业务或尚未执行时预期失败，不得编造SHA、写占位断言或把pending改成passed绕过。人工C/D/F项也必须有证据；只跑pytest不代表完整课程交付。
