# 独立开发替身

E提供NetworkStub和DispatchStub，只返回调用方显式给出的数据，不实现真实投影、路径或预测。A/B可在自己的单元测试中导入tests.support.doubles；不得在backend/app生产代码中导入，也不能用于最终联调验收。每个模块可在自己的测试目录增加专用替身。

示例（根目录.venv，模块测试内）：

```python
from tests.support.doubles import NetworkStub, DispatchStub
network = NetworkStub({('s1', 's2'): {'distance_m': 250, 'polyline': [[100,200],[350,200]]}})
# 反向路径必须另外显式提供；未提供的对抛UNREACHABLE，不偷偷画直线。
dispatcher = DispatchStub(analysis={'estimator_version': 'test', 'now_sec': 0,
    'horizon_sec': 1800, 'stations': []})
```

B测试批量时在自己的测试中实现run_once(spec)：记录收到的RunSpec，返回显式构造的RunOutcome，或针对指定组合抛异常；不要创建真实DB。A集成时再注入实际run_once。C负责frontend/src/mocks（自己的所有权）下的请求与WS替身，按07全部响应形状生成场景，VITE_USE_MOCK=true显式开启。
