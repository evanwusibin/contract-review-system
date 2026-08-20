export function showToast(message, type = 'info') {
  let toast = document.getElementById('app-toast')
  if (!toast) {
    toast = document.createElement('div')
    toast.id = 'app-toast'
    document.body.appendChild(toast)
  }
  toast.textContent = message
  toast.className = `toast show toast-${type}`
  clearTimeout(toast._timer)
  toast._timer = setTimeout(() => { toast.className = 'toast' }, 3000)
}