/**
 * Utility functions for executor output comparison.
 */
import type { Run, ExecutorType, FileDiff } from '@/types';

/**
 * Get the latest succeeded run for each executor type.
 * Returns a Map keyed by ExecutorType with the most recent successful run.
 */
export function getComparableRuns(runs: Run[]): Map<ExecutorType, Run> {
  const byExecutor = new Map<ExecutorType, Run>();

  // Sort by created_at descending to get latest first
  const sorted = [...runs].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  for (const run of sorted) {
    if (run.status === 'succeeded' && !byExecutor.has(run.executor_type)) {
      byExecutor.set(run.executor_type, run);
    }
  }

  return byExecutor;
}

/**
 * Result of file overlap analysis between executor runs.
 */
export interface FileOverlapAnalysis {
  /** Files that appear in all compared runs */
  commonFiles: string[];
  /** Files unique to each executor */
  uniqueFiles: Map<ExecutorType, string[]>;
  /** All files across all runs (union) */
  allFiles: string[];
}

/**
 * Analyze file overlap between multiple runs.
 * Identifies common files and files unique to each executor.
 */
export function analyzeFileOverlap(runs: Run[]): FileOverlapAnalysis {
  const filesByExecutor = new Map<ExecutorType, Set<string>>();

  // Collect files from each run
  for (const run of runs) {
    const files = new Set<string>();
    if (run.files_changed) {
      for (const file of run.files_changed) {
        files.add(file.path);
      }
    }
    filesByExecutor.set(run.executor_type, files);
  }

  // Find all files (union)
  const allFilesSet = new Set<string>();
  for (const files of filesByExecutor.values()) {
    for (const file of files) {
      allFilesSet.add(file);
    }
  }
  const allFiles = [...allFilesSet].sort();

  // Find common files (intersection)
  const commonFiles: string[] = [];
  for (const file of allFiles) {
    let inAll = true;
    for (const files of filesByExecutor.values()) {
      if (!files.has(file)) {
        inAll = false;
        break;
      }
    }
    if (inAll) {
      commonFiles.push(file);
    }
  }

  // Find unique files per executor
  const uniqueFiles = new Map<ExecutorType, string[]>();
  for (const [executor, files] of filesByExecutor) {
    const unique: string[] = [];
    for (const file of files) {
      // Check if this file is unique to this executor
      let isUnique = true;
      for (const [otherExecutor, otherFiles] of filesByExecutor) {
        if (otherExecutor !== executor && otherFiles.has(file)) {
          isUnique = false;
          break;
        }
      }
      if (isUnique) {
        unique.push(file);
      }
    }
    uniqueFiles.set(executor, unique.sort());
  }

  return { commonFiles, uniqueFiles, allFiles };
}

/**
 * Extract the patch for a specific file from a run.
 * Returns null if the file was not changed in this run.
 */
export function getFilePatch(run: Run, filePath: string): string | null {
  if (!run.files_changed) return null;

  const file = run.files_changed.find((f) => f.path === filePath);
  return file?.patch || null;
}

/**
 * Get statistics for a run.
 */
export interface RunStats {
  filesChanged: number;
  linesAdded: number;
  linesRemoved: number;
}

export function getRunStats(run: Run): RunStats {
  if (!run.files_changed) {
    return { filesChanged: 0, linesAdded: 0, linesRemoved: 0 };
  }

  let linesAdded = 0;
  let linesRemoved = 0;

  for (const file of run.files_changed) {
    linesAdded += file.added_lines;
    linesRemoved += file.removed_lines;
  }

  return {
    filesChanged: run.files_changed.length,
    linesAdded,
    linesRemoved,
  };
}

/**
 * Parse a unified diff patch into structured format.
 * Used for side-by-side diff comparison.
 */
export interface ParsedDiffLine {
  content: string;
  type: 'add' | 'remove' | 'context';
  lineNumber: number | null;
}

export interface ParsedDiffHunk {
  header: string;
  oldStart: number;
  newStart: number;
  lines: ParsedDiffLine[];
}

export function parseDiff(patch: string): ParsedDiffHunk[] {
  const hunks: ParsedDiffHunk[] = [];
  const lines = patch.split('\n');

  let currentHunk: ParsedDiffHunk | null = null;
  let oldLineNum = 0;
  let newLineNum = 0;

  for (const line of lines) {
    // Skip diff headers
    if (line.startsWith('diff ') || line.startsWith('--- ') || line.startsWith('+++ ')) {
      continue;
    }

    // Hunk header
    if (line.startsWith('@@')) {
      if (currentHunk) {
        hunks.push(currentHunk);
      }

      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      oldLineNum = match ? parseInt(match[1], 10) : 1;
      newLineNum = match ? parseInt(match[2], 10) : 1;

      currentHunk = {
        header: line,
        oldStart: oldLineNum,
        newStart: newLineNum,
        lines: [],
      };
      continue;
    }

    if (currentHunk) {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        currentHunk.lines.push({
          content: line.slice(1),
          type: 'add',
          lineNumber: newLineNum++,
        });
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        currentHunk.lines.push({
          content: line.slice(1),
          type: 'remove',
          lineNumber: oldLineNum++,
        });
      } else {
        currentHunk.lines.push({
          content: line.startsWith(' ') ? line.slice(1) : line,
          type: 'context',
          lineNumber: newLineNum++,
        });
        oldLineNum++;
      }
    }
  }

  if (currentHunk) {
    hunks.push(currentHunk);
  }

  return hunks;
}

/**
 * Get file diff for a specific file from a run.
 */
export function getFileDiff(run: Run, filePath: string): FileDiff | null {
  if (!run.files_changed) return null;
  return run.files_changed.find((f) => f.path === filePath) || null;
}
