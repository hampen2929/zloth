/**
 * Design Tokens for dursor UI
 * Centralized design system values for consistent styling
 */

export const colors = {
  // Background
  bg: {
    primary: '#030712',    // gray-950
    secondary: '#111827',  // gray-900
    tertiary: '#1f2937',   // gray-800
    elevated: '#374151',   // gray-700
  },

  // Text
  text: {
    primary: '#f9fafb',    // gray-50
    secondary: '#d1d5db',  // gray-300 (improved contrast)
    muted: '#9ca3af',      // gray-400
    inverse: '#030712',    // gray-950
  },

  // Brand
  brand: {
    primary: '#2563eb',    // blue-600
    primaryHover: '#1d4ed8', // blue-700
    secondary: '#7c3aed',  // violet-600
  },

  // Status
  status: {
    success: '#22c55e',    // green-500
    successBg: '#14532d',  // green-900
    error: '#ef4444',      // red-500
    errorBg: '#7f1d1d',    // red-900
    warning: '#f59e0b',    // amber-500
    warningBg: '#78350f',  // amber-900
    info: '#3b82f6',       // blue-500
    infoBg: '#1e3a8a',     // blue-900
  },

  // Border
  border: {
    default: '#374151',    // gray-700
    subtle: '#1f2937',     // gray-800
    focus: '#2563eb',      // blue-600
  },
} as const;

export const spacing = {
  xs: '0.25rem',   // 4px
  sm: '0.5rem',    // 8px
  md: '0.75rem',   // 12px
  lg: '1rem',      // 16px
  xl: '1.5rem',    // 24px
  '2xl': '2rem',   // 32px
  '3xl': '3rem',   // 48px
} as const;

export const radii = {
  sm: '0.25rem',   // 4px
  md: '0.375rem',  // 6px
  lg: '0.5rem',    // 8px
  xl: '0.75rem',   // 12px
  full: '9999px',
} as const;

export const shadows = {
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  md: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
  xl: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
} as const;

export const transitions = {
  fast: '150ms ease-in-out',
  normal: '200ms ease-in-out',
  slow: '300ms ease-in-out',
} as const;

export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;

// Status color mapping for run states
export const runStatusColors = {
  queued: {
    bg: 'bg-gray-500',
    text: 'text-gray-400',
    dot: 'bg-gray-500',
  },
  running: {
    bg: 'bg-yellow-500',
    text: 'text-yellow-400',
    dot: 'bg-yellow-500 animate-pulse',
  },
  completed: {
    bg: 'bg-green-500',
    text: 'text-green-400',
    dot: 'bg-green-500',
  },
  failed: {
    bg: 'bg-red-500',
    text: 'text-red-400',
    dot: 'bg-red-500',
  },
  cancelled: {
    bg: 'bg-gray-500',
    text: 'text-gray-400',
    dot: 'bg-gray-500',
  },
} as const;

export type RunStatus = keyof typeof runStatusColors;
