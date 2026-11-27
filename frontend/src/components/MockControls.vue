<script setup lang="ts">
import { ref } from 'vue'
import { mockActions } from '../mocks/transport'
const disconnected = ref(false)
const notice = ref('')
function inject(action: Exclude<keyof typeof mockActions, 'toggleConnection'>, text: string) {
  mockActions[action]()
  notice.value = text
}
</script>

<template>
  <details class="mock-controls">
    <summary>虚拟联调模式 <span>夹具数据</span></summary>
    <div class="mock-menu">
      <p>虚拟地图和计数仅供界面自测。</p>
      <div class="toolbar">
        <button @click="disconnected = mockActions.toggleConnection()">{{ disconnected ? '恢复连接' : '断开连接' }}</button>
        <button @click="inject('stale', '已发送旧序号。')">发送旧序号</button>
        <button @click="inject('vanish', '下次读取运行状态时模拟重置。')">恢复时重置</button>
        <button @click="inject('timeout', '下次含请求 ID 的提交将返回超时。')">注入请求超时</button>
        <button @click="inject('failSave', '下次保存将失败。')">注入保存失败</button>
        <button @click="inject('failBatch', '下一批量子项将失败。')">注入批量失败</button>
      </div>
      <p v-if="notice" role="status">{{ notice }}</p>
    </div>
  </details>
</template>
