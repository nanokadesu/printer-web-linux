import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// 完整引入 ElementPlus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

// 引入全局样式文件
import './assets/css/main.css'

// 创建 app 实例
const app = createApp(App)

// 使用插件
app.use(router)
app.use(ElementPlus)

// 挂载应用
app.mount('#app')