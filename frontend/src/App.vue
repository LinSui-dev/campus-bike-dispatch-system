<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { DataAnalysis, Histogram, Location, Operation, Van, Bicycle } from '@element-plus/icons-vue'
import { ElIcon } from 'element-plus'
import 'element-plus/es/components/icon/style/css'
import { mockMode } from './api'
import GlobalControls from './components/GlobalControls.vue'
import { useConfig } from './stores/config'
import { useRuntime } from './stores/runtime'

const pages = [
  { path: 'overview', label: '运营总览', icon: Histogram, component: defineAsyncComponent(() => import('./pages/OverviewPage.vue')) },
  { path: 'stations', label: '停车点管理', icon: Location, component: defineAsyncComponent(() => import('./pages/StationsPage.vue')) },
  { path: 'control', label: '仿真控制', icon: Operation, component: defineAsyncComponent(() => import('./pages/ControlPage.vue')) },
  { path: 'dispatch', label: '智能调度', icon: Van, component: defineAsyncComponent(() => import('./pages/DispatchPage.vue')) },
  { path: 'experiments', label: '实验分析', icon: DataAnalysis, component: defineAsyncComponent(() => import('./pages/ExperimentsPage.vue')) },
]
const MockControls = mockMode ? defineAsyncComponent(() => import('./components/MockControls.vue')) : null
const route = ref(location.hash)
const page = computed(() => pages.find(item => route.value === '#/' + item.path) ?? pages[0])
const config = useConfig()
const run = useRuntime()
function routeChange() {
  route.value = location.hash
  window.scrollTo({ top: 0, behavior: 'instant' })
}
onMounted(() => {
  window.addEventListener('hashchange', routeChange)
  run.mount()
  void config.load()
})
onBeforeUnmount(() => {
  window.removeEventListener('hashchange', routeChange)
  run.unmount()
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#/overview" aria-label="校园单车仿真运营总览">
        <span class="brand-mark"><ElIcon aria-hidden="true"><Bicycle /></ElIcon></span>
        <span><strong>校园单车仿真</strong><small>双校区调度实验</small></span>
      </a>
      <nav aria-label="主导航">
        <a v-for="item in pages" :key="item.path" :href="'#/' + item.path" :aria-current="page.path === item.path ? 'page' : undefined">
          <ElIcon aria-hidden="true"><component :is="item.icon" /></ElIcon><span>{{ item.label }}</span>
        </a>
      </nav>
      <div class="sidebar-source">
        <span class="live-dot" :class="{ on: !mockMode && run.available }" />
        <span>{{ mockMode ? '虚拟联调模式' : run.available ? '后端已连接' : '等待后端连接' }}</span>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="topbar-head"><span>北京交通大学 <i /> 共享单车调度</span><component :is="MockControls" v-if="MockControls" /></div>
        <GlobalControls />
      </header>
      <main class="main-content">
        <div v-if="config.issues.length" class="banner error" role="alert">
          <div v-for="issue in config.issues" :key="issue">{{ issue }}</div>
          <button class="text-button" @click="config.load">重试加载</button>
        </div>
        <component :is="page.component" :key="page.path" />
      </main>
    </div>
  </div>
</template>
