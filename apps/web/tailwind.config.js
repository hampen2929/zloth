/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        // Background semantic colors
        'bg-primary': 'var(--bg-primary)',
        'bg-secondary': 'var(--bg-secondary)',
        'bg-tertiary': 'var(--bg-tertiary)',
        'bg-elevated': 'var(--bg-elevated)',
        // Text semantic colors
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-muted': 'var(--text-muted)',
        'text-disabled': 'var(--text-disabled)',
        // Status colors
        success: 'var(--success)',
        'success-muted': 'var(--success-muted)',
        error: 'var(--error)',
        'error-muted': 'var(--error-muted)',
        warning: 'var(--warning)',
        'warning-muted': 'var(--warning-muted)',
        info: 'var(--info)',
        'info-muted': 'var(--info-muted)',
        // Border colors
        'border-default': 'var(--border-default)',
        'border-hover': 'var(--border-hover)',
        'border-focus': 'var(--border-focus)',
        'border-subtle': 'var(--border-subtle)',
        // Interactive colors
        'interactive-primary': 'var(--interactive-primary)',
        'interactive-primary-hover': 'var(--interactive-primary-hover)',
        'interactive-secondary': 'var(--interactive-secondary)',
        'interactive-secondary-hover': 'var(--interactive-secondary-hover)',
      },
      borderColor: {
        DEFAULT: 'var(--border-default)',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
