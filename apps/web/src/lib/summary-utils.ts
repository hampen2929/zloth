/**
 * Utility functions for structured summary display.
 */
import type { Run, StructuredSummary, SummaryType } from '@/types';

/**
 * Derive structured summary from run data.
 * This function generates a structured summary based on available run information,
 * providing useful context even when there are no code changes.
 */
export function deriveStructuredSummary(run: Run): StructuredSummary {
  // Use provided structured_summary if available
  if (run.structured_summary) {
    return run.structured_summary;
  }

  const hasNoChanges = !run.patch || run.patch.trim() === '';

  // Determine summary type
  let type: SummaryType = 'code_change';
  if (hasNoChanges) {
    // Check if it's a Q&A or analysis based on instruction/summary content
    const instruction = run.instruction?.toLowerCase() || '';

    if (
      instruction.includes('what') ||
      instruction.includes('how') ||
      instruction.includes('why') ||
      instruction.includes('explain') ||
      instruction.includes('describe') ||
      instruction.includes('?') ||
      instruction.includes('教えて') ||
      instruction.includes('なぜ') ||
      instruction.includes('どう')
    ) {
      type = 'qa_response';
    } else if (
      instruction.includes('analyze') ||
      instruction.includes('review') ||
      instruction.includes('check') ||
      instruction.includes('find') ||
      instruction.includes('search') ||
      instruction.includes('調べ') ||
      instruction.includes('確認')
    ) {
      type = 'analysis';
    } else {
      type = 'no_action';
    }
  }

  // Generate title based on type
  let title = '';
  switch (type) {
    case 'code_change':
      title = `Changed ${run.files_changed?.length || 0} file(s)`;
      break;
    case 'qa_response':
      title = 'Question Answered';
      break;
    case 'analysis':
      title = 'Analysis Completed';
      break;
    case 'no_action':
      title = 'Task Completed';
      break;
  }

  // Extract key points from logs if available
  const keyPoints: string[] = [];
  if (run.logs && run.logs.length > 0) {
    // Look for meaningful log entries
    for (const log of run.logs.slice(-20)) {
      // Skip raw JSON lines
      if (log.startsWith('{') || log.startsWith('[system]')) continue;
      // Skip empty or very short lines
      if (!log.trim() || log.trim().length < 10) continue;
      // Add meaningful content
      if (keyPoints.length < 3 && !log.includes('Executing:') && !log.includes('Working directory:')) {
        keyPoints.push(log.trim().slice(0, 150));
      }
    }
  }

  // Extract analyzed files from logs (files that were read)
  const analyzedFiles: string[] = [];
  if (run.logs) {
    const filePattern = /(?:Read|Viewed|Analyzed|Opened|Reading)\s+([^\s]+\.[a-z]+)/gi;
    for (const log of run.logs) {
      const matches = log.matchAll(filePattern);
      for (const match of matches) {
        if (!analyzedFiles.includes(match[1]) && analyzedFiles.length < 5) {
          analyzedFiles.push(match[1]);
        }
      }
    }
  }

  return {
    type,
    title,
    description: run.summary || 'No description available',
    key_points: keyPoints,
    analyzed_files: analyzedFiles,
    references: [],
  };
}

/**
 * Get display properties for summary type
 */
export interface SummaryTypeDisplay {
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
}

export function getSummaryTypeStyles(type: SummaryType): SummaryTypeDisplay {
  switch (type) {
    case 'code_change':
      return {
        color: 'text-green-400',
        bgColor: 'bg-green-500/10',
        borderColor: 'border-green-500/30',
        label: 'Code Changes',
      };
    case 'qa_response':
      return {
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/10',
        borderColor: 'border-blue-500/30',
        label: 'Q&A Response',
      };
    case 'analysis':
      return {
        color: 'text-purple-400',
        bgColor: 'bg-purple-500/10',
        borderColor: 'border-purple-500/30',
        label: 'Analysis',
      };
    case 'no_action':
      return {
        color: 'text-gray-400',
        bgColor: 'bg-gray-500/10',
        borderColor: 'border-gray-500/30',
        label: 'Completed',
      };
  }
}
