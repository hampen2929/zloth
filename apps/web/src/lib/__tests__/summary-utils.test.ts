import { describe, it, expect } from 'vitest';
import { deriveStructuredSummary, getSummaryTypeStyles } from '../summary-utils';
import type { Run, StructuredSummary } from '@/types';

// Helper to create a minimal Run object for testing
function createMockRun(overrides: Partial<Run> = {}): Run {
  return {
    id: 'run-1',
    task_id: 'task-1',
    message_id: null,
    model_id: null,
    model_name: null,
    provider: null,
    executor_type: 'claude_code',
    working_branch: null,
    worktree_path: null,
    instruction: '',
    base_ref: null,
    commit_sha: null,
    status: 'succeeded',
    summary: null,
    structured_summary: null,
    patch: null,
    files_changed: [],
    logs: [],
    warnings: [],
    error: null,
    created_at: '2025-01-15T12:00:00Z',
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

describe('deriveStructuredSummary', () => {
  describe('when structured_summary is provided', () => {
    it('should return the existing structured_summary', () => {
      const existingSummary: StructuredSummary = {
        type: 'code_change',
        title: 'Existing Summary',
        instruction: 'Test instruction',
        response: 'Test response',
        key_points: ['Point 1'],
        analyzed_files: [],
        references: [],
      };

      const run = createMockRun({ structured_summary: existingSummary });
      const result = deriveStructuredSummary(run);

      expect(result).toBe(existingSummary);
    });
  });

  describe('type detection', () => {
    it('should detect code_change when patch is present', () => {
      const run = createMockRun({
        patch: '--- a/file.ts\n+++ b/file.ts\n@@ -1,1 +1,1 @@\n-old\n+new',
        files_changed: [{ path: 'file.ts', added_lines: 1, removed_lines: 1, patch: '' }],
      });
      const result = deriveStructuredSummary(run);

      expect(result.type).toBe('code_change');
      expect(result.title).toBe('Changed 1 file(s)');
    });

    it('should detect qa_response for questions', () => {
      const run = createMockRun({
        instruction: 'What does this function do?',
      });
      const result = deriveStructuredSummary(run);

      expect(result.type).toBe('qa_response');
      expect(result.title).toBe('Question Answered');
    });

    it('should detect qa_response for Japanese questions', () => {
      const run = createMockRun({
        instruction: 'この関数について教えてください',
      });
      const result = deriveStructuredSummary(run);

      expect(result.type).toBe('qa_response');
    });

    it('should detect analysis for review/analyze instructions', () => {
      const run = createMockRun({
        instruction: 'analyze this code for performance issues',
      });
      const result = deriveStructuredSummary(run);

      expect(result.type).toBe('analysis');
      expect(result.title).toBe('Analysis Completed');
    });

    it('should detect analysis for Japanese analysis keywords', () => {
      const run = createMockRun({
        instruction: 'コードを確認してください',
      });
      const result = deriveStructuredSummary(run);

      expect(result.type).toBe('analysis');
    });

    it('should default to no_action when no patch and no matching keywords', () => {
      const run = createMockRun({
        instruction: 'prepare the environment',
      });
      const result = deriveStructuredSummary(run);

      expect(result.type).toBe('no_action');
      expect(result.title).toBe('Task Completed');
    });
  });

  describe('extracting response from logs', () => {
    it('should extract text from Claude Code CLI JSON format', () => {
      const run = createMockRun({
        logs: [
          '{"type":"assistant","message":{"content":[{"type":"text","text":"This is the response"}]}}',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.response).toBe('This is the response');
    });

    it('should join multiple response texts', () => {
      const run = createMockRun({
        logs: [
          '{"type":"assistant","message":{"content":[{"type":"text","text":"Part 1"}]}}',
          '{"type":"assistant","message":{"content":[{"type":"text","text":"Part 2"}]}}',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.response).toBe('Part 1\nPart 2');
    });

    it('should fall back to summary when no logs', () => {
      const run = createMockRun({
        summary: 'Fallback summary text',
      });
      const result = deriveStructuredSummary(run);

      expect(result.response).toBe('Fallback summary text');
    });

    it('should handle invalid JSON in logs gracefully', () => {
      const run = createMockRun({
        logs: ['{invalid json', 'regular log line'],
        summary: 'Fallback',
      });
      const result = deriveStructuredSummary(run);

      expect(result.response).toBe('Fallback');
    });
  });

  describe('extracting key points', () => {
    it('should extract bullet points from response', () => {
      const run = createMockRun({
        logs: [
          '{"type":"assistant","message":{"content":[{"type":"text","text":"Summary:\\n- First important point here\\n- Second important point here\\n- Third point"}]}}',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.key_points).toContain('First important point here');
      expect(result.key_points).toContain('Second important point here');
    });

    it('should extract numbered lists from response', () => {
      const run = createMockRun({
        logs: [
          '{"type":"assistant","message":{"content":[{"type":"text","text":"Steps:\\n1. First step to take\\n2. Second step follows"}]}}',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.key_points).toContain('First step to take');
      expect(result.key_points).toContain('Second step follows');
    });

    it('should limit key points to 5', () => {
      const run = createMockRun({
        logs: [
          '{"type":"assistant","message":{"content":[{"type":"text","text":"- Point 1 is here\\n- Point 2 is here\\n- Point 3 is here\\n- Point 4 is here\\n- Point 5 is here\\n- Point 6 is here\\n- Point 7 is here"}]}}',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.key_points.length).toBeLessThanOrEqual(5);
    });

    it('should extract from non-JSON logs when no key points found', () => {
      const run = createMockRun({
        logs: [
          '[system] Starting execution',
          'This is a meaningful log message with information',
          'Another useful piece of information here',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.key_points.length).toBeGreaterThan(0);
    });
  });

  describe('extracting analyzed files', () => {
    it('should extract file paths from logs with Read prefix', () => {
      const run = createMockRun({
        logs: [
          'Read src/components/Button.ts',
          'Analyzed src/lib/utils.ts',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.analyzed_files).toContain('src/components/Button.ts');
      expect(result.analyzed_files).toContain('src/lib/utils.ts');
    });

    it('should limit analyzed files to 5', () => {
      const run = createMockRun({
        logs: [
          'Read file1.ts',
          'Read file2.ts',
          'Read file3.ts',
          'Read file4.ts',
          'Read file5.ts',
          'Read file6.ts',
          'Read file7.ts',
        ],
      });
      const result = deriveStructuredSummary(run);

      expect(result.analyzed_files.length).toBeLessThanOrEqual(5);
    });
  });
});

describe('getSummaryTypeStyles', () => {
  it('should return correct styles for code_change', () => {
    const styles = getSummaryTypeStyles('code_change');
    expect(styles.label).toBe('Code Changes');
    expect(styles.color).toContain('green');
  });

  it('should return correct styles for qa_response', () => {
    const styles = getSummaryTypeStyles('qa_response');
    expect(styles.label).toBe('Q&A Response');
    expect(styles.color).toContain('blue');
  });

  it('should return correct styles for analysis', () => {
    const styles = getSummaryTypeStyles('analysis');
    expect(styles.label).toBe('Analysis');
    expect(styles.color).toContain('purple');
  });

  it('should return correct styles for no_action', () => {
    const styles = getSummaryTypeStyles('no_action');
    expect(styles.label).toBe('Completed');
    expect(styles.color).toContain('gray');
  });
});
