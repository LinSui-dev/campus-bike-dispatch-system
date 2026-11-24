# 地图与需求数据

fixtures是项目自建虚拟小图：4站40车，仅供开发和测试，不是北京交通大学真实地图，不满足正式地图与12站验收。campus由D提交正式素材。两个profile文件名和格式相同：

- metadata.json：profile、image_file、width、height、network_version、synthetic、snap_tolerance_px、source。
- campus_map.png（正式）；fixture使用项目自绘SVG，后端按metadata定位文件。
- road_network.json：契约RoadNetwork，synthetic标识；真实路网synthetic=false。
- default_stations.json：Station数组。
- scenarios.json：Scenario数组，四预设；合成率在description与sources.md中声明。
- default_config.json：Config。
- sources.md：地图来源、许可状态、道路长度核验方法、站点与需求假设。

元数据尺寸与路网一致，底图尺寸由D核对。默认数据的道路、站点、OD引用必须自洽；generator_version记录在运行快照。正式campus未提供时禁止把fixture冒充正式场景。
