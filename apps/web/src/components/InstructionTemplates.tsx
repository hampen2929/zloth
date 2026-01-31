'use client';

import { useState } from 'react';
import {
  BugAntIcon,
  BeakerIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

interface Template {
  id: string;
  name: string;
  instruction: string;
  icon: React.ReactNode;
  color: string;
}

const DEFAULT_TEMPLATES: Template[] = [
  {
    id: 'bug-fix',
    name: 'Bug Fix',
    instruction: 'Fix the bug in ',
    icon: <BugAntIcon className="w-4 h-4" />,
    color: 'text-red-400',
  },
  {
    id: 'add-test',
    name: 'Add Tests',
    instruction: 'Add unit tests for ',
    icon: <BeakerIcon className="w-4 h-4" />,
    color: 'text-green-400',
  },
  {
    id: 'refactor',
    name: 'Refactor',
    instruction: 'Refactor ',
    icon: <ArrowPathIcon className="w-4 h-4" />,
    color: 'text-blue-400',
  },
  {
    id: 'docs',
    name: 'Documentation',
    instruction: 'Add documentation for ',
    icon: <DocumentTextIcon className="w-4 h-4" />,
    color: 'text-yellow-400',
  },
  {
    id: 'feature',
    name: 'New Feature',
    instruction: 'Implement a new feature that ',
    icon: <SparklesIcon className="w-4 h-4" />,
    color: 'text-purple-400',
  },
];

const STORAGE_KEY = 'zloth-instruction-templates';

interface InstructionTemplatesProps {
  onSelect: (instruction: string) => void;
  className?: string;
}

function getInitialTemplates(): Template[] {
  if (typeof window === 'undefined') return DEFAULT_TEMPLATES;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const customTemplates = JSON.parse(stored) as Template[];
      return [...DEFAULT_TEMPLATES, ...customTemplates];
    }
  } catch {
    // Ignore parse errors
  }
  return DEFAULT_TEMPLATES;
}

export function InstructionTemplates({ onSelect, className }: InstructionTemplatesProps) {
  const [templates] = useState<Template[]>(getInitialTemplates);

  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {templates.map((template) => (
        <button
          key={template.id}
          onClick={() => onSelect(template.instruction)}
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1.5',
            'text-sm rounded-full',
            'bg-gray-800/50 hover:bg-gray-700/50',
            'border border-gray-700 hover:border-gray-600',
            'transition-colors duration-150',
            'focus:outline-none focus:ring-2 focus:ring-blue-500/50'
          )}
          title={`Use "${template.instruction}" template`}
        >
          <span className={template.color}>{template.icon}</span>
          <span className="text-gray-300">{template.name}</span>
        </button>
      ))}
    </div>
  );
}

// Hook to save custom templates
export function useSaveTemplate() {
  const saveTemplate = (template: Omit<Template, 'icon' | 'color'>) => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      const existing = stored ? JSON.parse(stored) : [];
      const updated = [...existing, { ...template, icon: null, color: 'text-gray-400' }];
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    } catch {
      // Ignore storage errors
    }
  };

  return { saveTemplate };
}
