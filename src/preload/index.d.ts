import type { BodyTalkApi } from './index'

declare global {
  interface Window {
    bodytalk: BodyTalkApi
  }
}

export {}
