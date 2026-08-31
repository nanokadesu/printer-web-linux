<template>
  <router-view v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup>
// 此文件现在主要用于路由视图的渲染和过渡动画
</script>

<style>
/* 全局样式导入 */
/* 确保 animate.css 被正确引入，如果需要的话 */
/* @import 'animate.css'; */

/* 全局路由过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 全局样式重置和基础设定 */
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: #f9fbf9; /* 淡绿色主题背景 */
}
</style>