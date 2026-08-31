import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn } from '../utils/auth'
import Home from '../views/Home.vue'
import Login from '../views/Login.vue'
import Present from '../views/Present.vue'
import PrintDashboard from '../views/PrintDashboard.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/print',
    name: 'PrintDashboard',
    component: PrintDashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  },
  {
    path: '/present',
    name: 'Present',
    component: Present,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth) {
    if (isLoggedIn()) {
      next();
    } else {
      next({ 
        path: '/login', 
        replace: true,
        query: { redirect: to.fullPath }
      });
    }
  } else {
    next();
  }
});

export default router