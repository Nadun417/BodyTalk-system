// Allow importing .sql files as raw strings (Vite/electron-vite `?raw` suffix),
// so the schema is inlined into the bundle and needs no runtime file path.
declare module '*.sql?raw' {
  const content: string
  export default content
}
