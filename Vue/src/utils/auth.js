import Cookies from 'js-cookie'

// 设置登录cookie
export const setLoginCookie = (username, token) => {
  Cookies.set('username', username, { expires: 1 }) // 1天过期
  Cookies.set('token', token, { expires: 1 })
}

// 获取用户名
export const getUsername = () => {
  return Cookies.get('username')
}

// 获取认证token
export const getToken = () => {
  return Cookies.get('token')
}

// 检查是否已登录
export const isLoggedIn = () => {
  return !!Cookies.get('token')
}

// 清除登录信息
export const removeToken = () => {
  Cookies.remove('username')
  Cookies.remove('token')
}