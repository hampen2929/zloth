# Skill: Add New React Component

## Description
Guide for adding a new React component to the dursor frontend.

## Steps

### 1. Create Component File
- Location: `apps/web/src/components/{ComponentName}.tsx`
- Use PascalCase for component names

### 2. Add TypeScript Types (if needed)
- Location: `apps/web/src/types.ts`

### 3. Export Component (if reusable UI)
- For UI primitives: add to `apps/web/src/components/ui/index.ts`

### 4. Verify
```bash
cd apps/web
npm run lint
npm run build
```

## Template

```tsx
'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';

interface YourComponentProps {
  className?: string;
  // Add your props here
}

export function YourComponent({ className }: YourComponentProps) {
  const [state, setState] = useState<string>('');

  return (
    <div className={cn('your-base-classes', className)}>
      {/* Component content */}
    </div>
  );
}
```

## Conventions

- Use `'use client'` directive for components with interactivity
- Use `cn()` from `@/lib/utils` for conditional class merging
- Follow existing component patterns in the codebase
- Use Tailwind CSS for styling
- Keep components focused and single-responsibility
