<script setup lang="ts">
import { paramFields, paramKeys } from '../domain'
import type { Params } from '../types'
const params = defineModel<Params>({ required: true })
defineProps<{ disabled?: boolean }>()
</script>

<template>
  <fieldset class="fields fields-4" :disabled="disabled" aria-label="仿真参数">
    <label v-for="key in paramKeys" :key="key" class="field">
      <span>{{ paramFields[key].label }} <small>{{ paramFields[key].unit }}</small></span>
      <input v-model.number="params[key]" type="number" :min="paramFields[key].min"
        :max="Number.isFinite(paramFields[key].max) ? paramFields[key].max : undefined"
        :step="paramFields[key].integer ? 1 : 'any'" required />
    </label>
  </fieldset>
</template>
