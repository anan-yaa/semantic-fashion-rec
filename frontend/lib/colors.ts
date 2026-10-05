/**
 * Display colors for the catalogue's color names (products have no images).
 */

const COLOR_HEX: Record<string, string> = {
  Beige: '#e8dcc4',
  Black: '#1f1f1f',
  Blue: '#2563eb',
  Bronze: '#a97142',
  Brown: '#7b4a2d',
  Burgundy: '#800020',
  Charcoal: '#36454f',
  'Coffee Brown': '#4b3621',
  Copper: '#b87333',
  Cream: '#f5efdc',
  'Fluorescent Green': '#39d353',
  Gold: '#d4af37',
  Green: '#2f855a',
  Grey: '#8a8a8a',
  'Grey Melange': '#a8a8a8',
  Khaki: '#c3b091',
  Lavender: '#b9a6e0',
  'Lime Green': '#65c832',
  Magenta: '#d6249f',
  Maroon: '#800000',
  Mauve: '#b784a7',
  Metallic: '#aaa9ad',
  'Mushroom Brown': '#a39383',
  Mustard: '#e1ad01',
  'Navy Blue': '#1f2a5a',
  Nude: '#e3bc9a',
  'Off White': '#f4f1ea',
  Olive: '#708238',
  Orange: '#f97316',
  Peach: '#ffcba4',
  Pink: '#ec4899',
  Purple: '#7e22ce',
  Red: '#dc2626',
  Rose: '#e8a0a8',
  Rust: '#b7410e',
  'Sea Green': '#2e8b57',
  Silver: '#c0c0c0',
  Skin: '#f1c27d',
  Steel: '#71797e',
  Tan: '#d2b48c',
  Taupe: '#8b8589',
  Teal: '#0d9488',
  'Turquoise Blue': '#30b6c8',
  White: '#ffffff',
  Yellow: '#facc15',
}

const MULTI = 'linear-gradient(135deg, #ef4444, #f59e0b, #10b981, #3b82f6, #8b5cf6)'
const NEUTRAL = '#d6d3d1'

/** CSS background for a swatch of this catalogue color. */
export function swatchBackground(color: string | null): string {
  if (color === 'Multi') return MULTI
  return (color && COLOR_HEX[color]) || NEUTRAL
}

/** Very light tint of the color, for the card's image area. */
export function tileBackground(color: string | null): string {
  if (color === 'Multi') return 'linear-gradient(135deg, #fef2f2, #fffbeb, #ecfdf5, #eff6ff, #f5f3ff)'
  const hex = (color && COLOR_HEX[color]) || NEUTRAL
  return `${hex}1a`
}
