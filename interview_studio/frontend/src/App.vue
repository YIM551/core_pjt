<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import ToastHost from './components/ToastHost.vue'

const auth = useAuthStore()
onMounted(() => auth.restore())
</script>

<template>
  <router-view />
  <ToastHost />
</template>
