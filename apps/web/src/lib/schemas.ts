import { z } from 'zod';
import type { Provider, ExecutorType, CodingMode, PRCreationMode } from '@/types';

// Provider enum schema
export const providerSchema = z.enum(['openai', 'anthropic', 'google']) satisfies z.ZodType<Provider>;

// Executor type enum schema
export const executorTypeSchema = z.enum([
  'patch_agent',
  'claude_code',
  'codex_cli',
  'gemini_cli',
]) satisfies z.ZodType<ExecutorType>;

// Coding mode enum schema
export const codingModeSchema = z.enum([
  'interactive',
  'semi_auto',
  'full_auto',
]) satisfies z.ZodType<CodingMode>;

// PR creation mode enum schema
export const prCreationModeSchema = z.enum(['create', 'link']) satisfies z.ZodType<PRCreationMode>;

// Add Model Form Schema
export const addModelSchema = z.object({
  provider: providerSchema,
  modelName: z.string().min(1, 'Model name is required'),
  displayName: z.string().optional(),
  apiKey: z
    .string()
    .min(1, 'API key is required')
    .refine(
      (val) => {
        // Basic format validation for common API key patterns
        return val.length >= 10;
      },
      { message: 'API key appears to be too short' }
    ),
});

export type AddModelInput = z.infer<typeof addModelSchema>;

// GitHub App Configuration Schema
export const githubAppSchema = z.object({
  appId: z
    .string()
    .min(1, 'App ID is required')
    .regex(/^\d+$/, 'App ID must be a number'),
  privateKey: z.string().min(1, 'Private key is required'),
  installationId: z
    .string()
    .optional()
    .refine((val) => !val || /^\d+$/.test(val), {
      message: 'Installation ID must be a number',
    }),
});

export type GitHubAppInput = z.infer<typeof githubAppSchema>;

// Task Creation Form Schema
export const createTaskSchema = z.object({
  instruction: z.string().min(1, 'Please enter an instruction'),
  repoFullName: z.string().min(1, 'Please select a repository'),
  branch: z.string().min(1, 'Please select a branch'),
  executors: z.array(executorTypeSchema).min(1, 'Please select at least one executor'),
  codingMode: codingModeSchema,
});

export type CreateTaskInput = z.infer<typeof createTaskSchema>;

// User Preferences Schema
export const userPreferencesSchema = z.object({
  default_repo_owner: z.string().nullable().optional(),
  default_repo_name: z.string().nullable().optional(),
  default_branch: z.string().nullable().optional(),
  default_branch_prefix: z.string().nullable().optional(),
  default_pr_creation_mode: prCreationModeSchema.nullable().optional(),
  default_coding_mode: codingModeSchema.nullable().optional(),
  auto_generate_pr_description: z.boolean().nullable().optional(),
  enable_gating_status: z.boolean().nullable().optional(),
  notify_on_ready: z.boolean().nullable().optional(),
  notify_on_complete: z.boolean().nullable().optional(),
  notify_on_failure: z.boolean().nullable().optional(),
  notify_on_warning: z.boolean().nullable().optional(),
  merge_method: z.string().nullable().optional(),
  review_min_score: z.number().min(0).max(1).nullable().optional(),
});

export type UserPreferencesInput = z.infer<typeof userPreferencesSchema>;

// Backlog Item Creation Schema
export const createBacklogSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  description: z.string().optional(),
  type: z.enum(['feature', 'bug_fix', 'refactoring', 'docs', 'test']).optional(),
  estimatedSize: z.enum(['small', 'medium', 'large']).optional(),
  targetFiles: z.array(z.string()).optional(),
  implementationHint: z.string().optional(),
  tags: z.array(z.string()).optional(),
});

export type CreateBacklogInput = z.infer<typeof createBacklogSchema>;

// Review Request Schema
export const createReviewSchema = z.object({
  targetRunIds: z.array(z.string()).min(1, 'Please select at least one run to review'),
  executorType: executorTypeSchema.optional(),
  modelId: z.string().optional(),
  focusAreas: z
    .array(
      z.enum([
        'security',
        'bug',
        'performance',
        'maintainability',
        'best_practice',
        'style',
        'documentation',
        'test',
      ])
    )
    .optional(),
});

export type CreateReviewInput = z.infer<typeof createReviewSchema>;
