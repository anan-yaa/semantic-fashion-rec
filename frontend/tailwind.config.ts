import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#111111',
        secondary: '#6b6b6b',
        muted: '#9a9a9a',
        border: '#e7e5e4',
        hover: '#f5f5f4',
        surface: '#fafaf9',
        // Reserved for what the LLM contributed, so it reads as distinct from the catalogue.
        accent: {
          DEFAULT: '#6d28d9',
          soft: '#f3efff',
          border: '#ddd2fb',
        },
      },
    },
  },
  plugins: [],
}
export default config
