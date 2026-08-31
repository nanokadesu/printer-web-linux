<template>
  <div class="container">
    <!-- 左侧静态表格区域 -->
    <div class="w-table-container">
      <h3>技术目录</h3>
      <table>
        <thead>
          <tr>
            <th>组件</th>
            <th>技术</th>
          </tr>
        </thead>
        <tbody>
          <!-- 后端部分：合并 3 行 -->
          <tr>
            <td rowspan="3">后端</td>
            <td>waitress WSGI 服务器</td>
          </tr>
          <tr>
            <td>Flask 高性能 HTTP 服务器</td>
          </tr>
          <tr>
            <td>Python 3.12 环境</td>
          </tr>

          <!-- 前端部分：合并 2 行 -->
          <tr>
            <td rowspan="2">前端</td>
            <td>Vue 极简前端框架</td>
          </tr>
          <tr>
            <td>Vite 模板</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 右侧 Markdown 展示区域 -->
    <div class="markdown-container">
      <h3 style="padding-bottom: 20px;">简介</h3>
      <div class="preview-container">
        <!-- 修复：将 :content 改为 :source -->
        <MarkdownIt :source="markdownContent" class="markdown-preview" />
      </div>

      <div class="router-tips">
        <p>
          可选功能有 
          <router-link to="/print" class="router-link">/print</router-link>
          打印服务、
          <router-link to="/present" class="router-link">/present</router-link>
          自定义打印服务
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import MarkdownIt from 'vue3-markdown-it'

// 初始 Markdown 内容（示例）
const markdownContent = ref(`
所有用到的技术都在左侧，请根据需要进行修改

所有的 __前端__ 文件都在 __Vue__ 目录，所有的 __后端__ 文件都在 __Python/WSGI__ 目录

本服务器已配置 __Redis、PostgreSQL、Nginx、Node.js（Nvm）、VScode__
`)
</script>

<style scoped>
/* 全局容器样式 */
.container {
  display: flex;
  gap: 24px; /* 增大间距，提升呼吸感 */
  padding: 24px;
  min-height: 60vh;
  box-sizing: border-box;
  background-color: #f8f9fa; /* 更柔和的背景色 */
}

/* 左侧表格样式 */
.w-table-container {
  flex: 0 0 500px;
  background: white;
  padding: 24px;
  border-radius: 12px; /* 更大圆角，更现代 */
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); /* 更柔和的阴影 */
  transition: box-shadow 0.3s ease; /* 增加过渡效果 */
}

.w-table-container:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08); /* hover 增强阴影 */
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 16px;
}

th,
td {
  border: 1px solid #e9ecef; /* 更浅的边框色 */
  padding: 14px 16px;
  text-align: left;
}

th {
  background-color: #f1f3f5; /* 更柔和的表头背景 */
  font-weight: 600; /* 适中的字重 */
  color: #212529; /* 更清晰的文字色 */
}

tr:nth-child(even) {
  background-color: #f8f9fa;
}

/* 鼠标悬浮行高亮 */
tr:hover {
  background-color: #eef7fa;
  transition: background-color 0.2s ease;
}

/* 右侧 Markdown 区域样式 */
.markdown-container {
  flex: 1;
  background: white;
  padding: 28px; /* 增大内边距 */
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.3s ease;
}

.markdown-container:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.preview-container {
  border-top: 1px solid #e9ecef;
  padding-top: 24px;
  margin-top: 20px;
}

/* 核心 Markdown 预览样式（修改行高和间距） */
.markdown-preview {
  line-height: 2.5; /* 增大行高（原1.85 → 2.1） */
  color: #343a40;
  font-size: 16px;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
}

/* 段落样式（增大上下间距） */
.markdown-preview p {
  margin: 18px 0; /* 原14px → 18px */
  text-align: justify;
}

/* 标题样式层级（增大上下间距） */
.markdown-preview h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 36px 0 20px; /* 原32px/16px → 36px/20px */
  padding-bottom: 12px;
  border-bottom: 2px solid #42b983;
  color: #212529;
}

.markdown-preview h2 {
  font-size: 24px;
  font-weight: 600;
  margin: 32px 0 18px; /* 原28px/14px → 32px/18px */
  padding-bottom: 10px;
  border-bottom: 1px solid #e9ecef;
  color: #212529;
}

.markdown-preview h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 28px 0 16px; /* 原24px/12px → 28px/16px */
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f3f5;
  color: #212529;
}

.markdown-preview h4 {
  font-size: 18px;
  font-weight: 600;
  margin: 24px 0 12px;
  color: #212529;
}

.markdown-preview h5,
.markdown-preview h6 {
  font-size: 16px;
  font-weight: 600;
  margin: 16px 0 8px;
  color: #212529;
}

/* 段落样式 */
.markdown-preview p {
  margin: 14px 0;
  text-align: justify; /* 两端对齐，提升可读性 */
}

/* 强调文本（粗体/斜体） */
.markdown-preview strong {
  font-weight: 600;
  color: #212529;
}

.markdown-preview em {
  color: #495057;
  font-style: italic;
}

/* 列表样式 */
.markdown-preview ul,
.markdown-preview ol {
  margin: 16px 0;
  padding-left: 28px;
}

.markdown-preview ul {
  list-style-type: disc;
}

.markdown-preview ol {
  list-style-type: decimal;
}

.markdown-preview li {
  margin: 8px 0;
  padding-left: 8px;
}

/* 嵌套列表样式优化 */
.markdown-preview li > ul,
.markdown-preview li > ol {
  margin: 8px 0 8px 16px;
}

/* 引用样式 */
.markdown-preview blockquote {
  border-left: 4px solid #42b983;
  padding: 16px 20px;
  margin: 18px 0;
  color: #495057;
  background-color: #f8f9fa;
  border-radius: 0 8px 8px 0; /* 圆角优化 */
  font-style: italic;
}

/* 代码块样式（核心优化） */
.markdown-preview pre {
  background: #282c34; /* 暗色背景，适配代码高亮 */
  color: #abb2bf;
  padding: 20px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 20px 0;
  font-size: 14px;
  line-height: 1.7;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 行内代码 */
.markdown-preview code {
  background: #f1f3f5;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 14px;
  color: #e53e3e; /* 醒目但不刺眼的代码色 */
  font-family: "Fira Code", "Consolas", "Monaco", monospace;
}

/* 代码块内的代码取消行内样式 */
.markdown-preview pre > code {
  background: transparent;
  padding: 0;
  color: inherit;
}

/* 链接样式 */
.markdown-preview a {
  color: #42b983;
  text-decoration: none;
  border-bottom: 1px solid rgba(66, 185, 131, 0.3);
  transition: all 0.2s ease;
}

.markdown-preview a:hover {
  color: #359469;
  border-bottom: 1px solid #42b983;
}

/* 表格样式 */
.markdown-preview table {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.markdown-preview table th {
  background-color: #42b983;
  color: white;
  border: none;
}

.markdown-preview table td {
  border: 1px solid #e9ecef;
}

/* 分割线样式 */
.markdown-preview hr {
  border: none;
  height: 1px;
  background: linear-gradient(to right, transparent, #e9ecef, transparent);
  margin: 32px 0;
}

/* 图片样式 */
.markdown-preview img {
  max-width: 100%;
  border-radius: 8px;
  margin: 20px 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s ease;
}

.markdown-preview img:hover {
  transform: scale(1.01); /* 轻微放大效果 */
}

/* 路由链接样式 */
.router-tips {
  margin-top: 24px;
  padding: 16px;
  background-color: #eef7fa;
  border-radius: 8px;
  border-left: 4px solid #42b983;
}

.router-link {
  font-weight: 600;
  color: #42b983;
  text-decoration: none;
  padding: 2px 4px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.router-link:hover {
  color: white;
  background-color: #42b983;
}

/* 响应式适配 */
@media (max-width: 1200px) {
  .container {
    flex-direction: column; /* 小屏垂直排列 */
  }
  .w-table-container {
    flex: none;
    width: 100%;
    margin-bottom: 24px;
  }
}

@media (max-width: 768px) {
  .container {
    padding: 16px;
  }
  .w-table-container,
  .markdown-container {
    padding: 16px;
  }
  .markdown-preview {
    font-size: 14px;
  }
  .markdown-preview h1 {
    font-size: 24px;
  }
  .markdown-preview h2 {
    font-size: 20px;
  }
}
</style>