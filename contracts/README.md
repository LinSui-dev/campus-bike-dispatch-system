# v1公共契约

本目录由E维护，所有成员共同遵循。JSON Schema使用draft-2020-12，ID为字符串，时间秒、距离米、速度km/h。schema.json中的$defs为DTO权威，road_network.schema.json与station.schema.json为数据入口，examples供Mock。Python端口只依赖标准库，不含业务实现。

Schema负责字段与局部范围；跨字段约束（库存≤容量、OD时段、步长整除、到达时间、守恒、ID引用）必须由业务和语义测试实现。未知字段拒绝。PATCH只允许文档指定字段；不可直接使用完整DTO校验部分更新，应先验证可编辑字段再合并验证。

修改流程见docs/11，禁止单方改接口。examples/state.json是虚拟联调状态，不能由后端自动返回来掩盖未实现业务。当前版本为1.1.0，版本文件version.json。此次分发前修订新增StationCreate、StationPatch、RunContext，并在State中强制包含context；未实现的各模块统一按1.1.0开工，不要求兼容旧草案。

StationCreate不含道路接入字段；StationPatch只允许可编辑字段，x/y必须成对。A将PATCH合并当前Station后移除road_edge_id/road_offset，向D传完整StationCreate；D.validate_station返回完整Station。DTO允许的字段以Schema为准，业务补充容量、投影和引用约束。

State.context包含运行时场景起点、种子、完整初始参数、当前倍速、路网版本；HTTP完整快照和每次WS状态都包含它。params为冻结的初始参数，speed命令只改current_speed，不能悄悄改历史初始配置。schema扩展的具体使用流程见07。

Python从根目录可import contracts.python_interfaces；uvicorn --app-dir backend启动时A的main.py将项目根目录加入路径。业务代码只依赖协议，不导入其他成员私有文件。协议中run_once负责执行并保存单个运行，ExperimentRunner不写数据库。
