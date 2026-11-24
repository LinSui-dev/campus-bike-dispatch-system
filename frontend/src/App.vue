<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElAlert } from 'element-plus'

const health = ref('正在检查服务')
const error = ref('')
const mapUrl = ref('')
onMounted(async () => {
  try {
    const response = await fetch('/api/v1/health')
    if (!response.ok) throw new Error(`服务检查失败：${response.status}`)
    const info = await response.json()
    health.value = `后端已连接 · ${info.stage}`
    const mapResponse = await fetch('/api/v1/map')
    if (!mapResponse.ok) throw new Error(`地图检查失败：${mapResponse.status}`)
    const metadata = await mapResponse.json()
    mapUrl.value = metadata.image_url
  } catch (e) {
    error.value = e instanceof Error ? e.message : '连接失败'
    health.value = '后端尚未连接'
  }
})
</script>

<template>
  <main>
    <p class="eyebrow">六人并行开发基线 · v1</p>
    <h1>校园共享单车智能调度与可视化仿真系统</h1>
    <el-alert title="开发骨架：业务功能尚未实现；当前没有运行实验。" type="info" :closable="false" />
    <section>
      <h2>服务与数据</h2>
      <p>{{ health }}</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <p>下图是虚拟联调夹具，4站40车，不是校园实测地图或实验结果。</p>
      <img v-if="mapUrl" :src="mapUrl" alt="明确标注为虚拟数据的双校区测试示意图" />
    </section>
    <section>
      <h2>待开发的五个页面</h2>
      <div class="pages"><span v-for="name in ['运营总览', '停车点管理', '仿真控制', '智能调度', '实验分析']" :key="name">{{ name }}</span></div>
      <p>具体交互、接口与验收要求见仓库开发文档。本页面不会自动启动任何实验。</p>
    </section>
  </main>
</template>

<style>
body { margin: 0; background: #f3f6fa; color: #24354a; font-family: 'Microsoft YaHei', sans-serif; }
main { max-width: 1120px; margin: 48px auto; padding: 0 28px; }
h1 { font-size: 28px; line-height: 1.5; } h2 { font-size: 20px; }
.eyebrow { color: #527394; } section { margin-top: 24px; padding: 24px; background: white; border-radius: 10px; }
img { width: 100%; height: auto; } p { line-height: 1.8; }
.pages { display: flex; flex-wrap: wrap; gap: 16px; } .pages span { padding: 12px 18px; background: #edf3fa; border-radius: 6px; }
</style>
