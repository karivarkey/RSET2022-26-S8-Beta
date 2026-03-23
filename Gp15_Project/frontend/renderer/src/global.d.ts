export {}

declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void
      close: () => void
      resetToRightmost: () => void 
    }
  }
}
