# 校园地图与数据审阅

在浏览器打开 [地图预览](map-preview.html)。可切换双校区全图和跨区局部，按需打开「已选站点」「道路编号」「边长口径」。另外可查看 [场景审阅](scenario-review.html) 和 [路网路径自测](route-check-review.html)。

## 首批接入范围

`app.network.NetworkService` 按契约 1.1.0 接收 RoadNetwork 和 Station 列表。A/B 可使用 `data/fixtures` 对接。C 可从审阅包取得 PNG、尺寸和同画布坐标。调用说明、命令和验收范围见 [D 交接报告](../../docs/handoffs/D/network-map.md)。

## 正式实验场景

用户已确认正式实验采用审阅包中的全部八组场景。沿用三种策略和五个种子时，完整批次为 120 次。公共批次和验收由 E 协调相关成员同步。

## 审阅包与限制

- [校园审阅包](profile-review/sources.md) 含 4500 × 3163 像素 PNG、路网、14 个已选站点、八个合成 OD 场景和默认配置。状态为 draft，供本地自测和 E 审阅。
- [站点配置](profile-input-review.md) 为用户确认的主校区 11 站、东校区 3 站，容量共 565 辆，初始 290 辆。现行 AC-D03 为主 8、东 4，待 E 协调。
- 唯一跨区链为主校区南门出门先向南，再向东，经上园村路至东校区小西门。审阅包采用确认的 469 米总长，分段按绘图折线比例分配。道路 50 采用确认的 100 米。其他边长见 [来源说明](road-graph-review.md)。
- 审阅包位于 `profile-review`，正式 `DATA_PROFILE=campus` 数据尚未启用。真实 A/C 联调和正式 AC-D03 由后续集成复验。

## 底图来源与再生成

底图以北交大招生办公室 2025 年报考指南第 18 页为参考，参考 [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) 的公开地物和道路，再按用户圈注调整。建筑外形和道路宽度经过概化。

重生成脚本位于本目录。几何修改时依次重生成候选图、SVG、边长、站点、PNG、数据包、边长图层和路线证据。Python 数据制作脚本使用 Shapely 2.2.0，PNG 渲染脚本使用 Microsoft Edge。数据来源和生成步骤见 [审阅包说明](profile-review/sources.md)。
