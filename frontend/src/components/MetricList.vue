<script setup lang="ts">
import { metricFields, metricKeys, metricValue } from '../domain'
import type { Metrics } from '../types'
defineProps<{ metrics?: Metrics }>()
</script>

<template>
  <dl v-if="metrics" class="metric-details">
    <div v-for="key in metricKeys" :key="key">
      <dt>{{ metricFields[key][0] }}</dt>
      <dd>{{ metricValue(key, metrics[key]) }} <small v-if="metrics[key] !== null">{{ metricFields[key][1] }}</small></dd>
    </div>
  </dl>
  <p v-else class="empty-state">暂无数据</p>
</template>
