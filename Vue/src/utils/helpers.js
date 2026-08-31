export const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`
}

export const allowedExtensions = ['.pdf', '.png', '.webp', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.txt', '.md', '.markdown', '.tex', '.latex', '.doc', '.docx']

export const isValidFileType = (file) => allowedExtensions.includes(file.name.toLowerCase().slice(file.name.lastIndexOf('.')))

export const createFilePreview = (file) => {
  if (file.type?.startsWith('image/')) return Promise.resolve(URL.createObjectURL(file))
  return Promise.resolve('data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="80" height="80"%3E%3Crect width="80" height="80" fill="%23e8f5ef"/%3E%3Ctext x="40" y="45" text-anchor="middle" font-size="12" fill="%23359469"%3EDOC%3C/text%3E%3C/svg%3E')
}
