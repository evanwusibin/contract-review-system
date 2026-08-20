const STORAGE_KEY = 'contract_review_user'

// 角色 → 显示名/描述（与后端 auth.py 角色常量保持一致）
export const ROLE_LABELS = {
  admin: { roleName: '系统管理员', roleDesc: '管理员角色' },
  business_reviewer: { roleName: '业务评审员', roleDesc: '业务审核角色' },
  legal_reviewer: { roleName: '法务审核人', roleDesc: '法务审核角色' },
  warranty_reviewer: { roleName: '质保评审员', roleDesc: '质保审核角色' }
}

export function getUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

export function setUser(user) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
}

export function clearUser() {
  localStorage.removeItem(STORAGE_KEY)
}

// 由后端用户记录构造前端会话对象（含角色显示信息）
export function enrichUser(user) {
  const labels = ROLE_LABELS[user.role] || { roleName: user.role, roleDesc: '审核角色' }
  const sessionUser = {
    id: user.id,
    name: user.username,
    displayName: user.display_name || user.username,
    role: user.role,
    roleName: labels.roleName,
    roleDesc: labels.roleDesc
  }
  setUser(sessionUser)
  return sessionUser
}

// 向后端 /v1/auth/me 校验 cookie 会话；有效则返回用户，未认证返回 null
export async function checkSession() {
  try {
    const { api } = await import('./api.js')
    const resp = await api.me()
    if (!resp.ok || !resp.data?.authenticated || !resp.data.user) return null
    return enrichUser(resp.data.user)
  } catch {
    return null
  }
}

// 认证由后端 /v1/auth/login 校验，此处仅保留向后兼容的空校验（不再有前端固定账号）
export function validateLogin() {
  return true
}
