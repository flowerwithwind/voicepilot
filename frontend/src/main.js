import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import App from './App.vue'
import ChatView from './views/ChatView.vue'
import SettingsView from './views/SettingsView.vue'
import ReplayView from './views/ReplayView.vue'
import './assets/base.css'

const app = createApp(App)
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: ChatView },
    { path: '/settings', component: SettingsView },
    { path: '/replay/:sessionId', component: ReplayView },
  ],
})

app.use(ElementPlus, { locale: zhCn })
app.use(router)
app.mount('#app')
