<script setup lang="ts">
import { onMounted, ref } from 'vue'
defineProps<{ title: string; locked?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
onMounted(() => dialog.value?.showModal())
</script>

<template>
  <dialog ref="dialog" class="dialog" aria-labelledby="dialog-title" @cancel.prevent="!locked && emit('close')">
    <header><h2 id="dialog-title">{{ title }}</h2><button type="button" class="icon-button" aria-label="关闭" :disabled="locked" @click="emit('close')">×</button></header>
    <slot />
  </dialog>
</template>
