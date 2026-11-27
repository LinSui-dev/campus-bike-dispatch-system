import { defineStore } from 'pinia'
import { computed, shallowRef, ref } from 'vue'
import { api, message } from '../api'
import type { BatchResult, RunDetail, RunSummary, Sample, Task } from '../types'

export const useHistory = defineStore('history', () => {
  const runs = shallowRef<RunSummary[]>([])
  const selected = ref('')
  const detail = shallowRef<RunDetail | null>(null)
  const samples = shallowRef<Sample[]>([])
  const tasks = shallowRef<Task[]>([])
  const archiveBatch = shallowRef<BatchResult | null>(null)
  const listError = ref('')
  const detailError = ref('')
  const error = computed(() => [listError.value, detailError.value].filter(Boolean).join('；'))
  const loading = ref(false)
  let version = 0
  let listVersion = 0

  async function load() {
    const ticket = ++listVersion
    listError.value = ''
    try {
      const result = await api.history()
      if (ticket === listVersion) runs.value = result.items
    } catch (failure) {
      if (ticket === listVersion) listError.value = message(failure)
    }
  }

  async function open(id: string) {
    selected.value = id
    detail.value = null
    archiveBatch.value = null
    samples.value = []
    tasks.value = []
    detailError.value = ''
    const ticket = ++version
    loading.value = true
    try {
      const results = await Promise.allSettled([api.detail(id), api.metrics(id), api.tasks(id)])
      if (ticket !== version) return
      const [snapshot, metrics, savedTasks] = results
      if (snapshot.status === 'fulfilled') detail.value = snapshot.value
      if (metrics.status === 'fulfilled') samples.value = metrics.value.items
      if (savedTasks.status === 'fulfilled') tasks.value = savedTasks.value.items
      const errors = results.flatMap(result => result.status === 'rejected' ? [message(result.reason)] : [])
      detailError.value = [...new Set(errors)].join('；')
      const batchId = detail.value?.run.batch_id
      if (batchId) {
        const batch = await api.batch(batchId)
        if (ticket === version) archiveBatch.value = batch
      }
    } catch (failure) {
      if (ticket === version) detailError.value = message(failure)
    } finally {
      if (ticket === version) loading.value = false
    }
  }
  return { runs, selected, detail, samples, tasks, archiveBatch, error, loading, load, open }
})
