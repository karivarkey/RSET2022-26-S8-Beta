export {}

declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void
      close: () => void
      toggleAlwaysOnTop: () => void
      resetToRightmost: () => void 
    }
  }
}
