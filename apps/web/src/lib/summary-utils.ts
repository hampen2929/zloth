/**
 * Utility functions for structured summary display.
 */
import type { Run, StructuredSummary, SummaryType } from '@/types';

/**
 * Check if a log line is metadata/noise that should be skipped for plain text extraction.
 */
function isMetadataLine(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed) return true;

  // Skip common metadata patterns
  const metadataPatterns = [
    /^Executing:/i,
    /^Working directory:/i,
    /^Instruction length:/i,
    /^Running in (read-only|full-auto) mode/i,
    /^Continuing session:/i,
    /^---\s*codex attempt/i,
    /^\[system\]/i,
    /^To continue this session/i,
    /^session id:/i,
    /^Detected \d+ changed file/i,
    /^Committed:/i,
    /^Pushed to branch:/i,
    /^Pull(ed)? remote changes/i,
    /^Push failed/i,
    /^No changes detected/i,
    /^codex\s+exec/i,
    /^claude\s+-p/i,
  ];

  for (const pattern of metadataPatterns) {
    if (pattern.test(trimmed)) {
      return true;
    }
  }

  return false;
}

/**
 * Extract assistant's response text from logs.
 * Handles both:
 * - Claude Code: JSON lines in stream-json format
 * - Codex/Gemini: Plain text output
 */
function extractResponseFromLogs(logs: string[]): string {
  const responseTexts: string[] = [];
  let hasJsonContent = false;

  // First pass: try to extract from JSON format (Claude Code stream-json)
  for (const log of logs) {
    if (log.startsWith('{')) {
      try {
        const data = JSON.parse(log);
        if (data.type === 'assistant' && data.message?.content) {
          hasJsonContent = true;
          const content = data.message.content;
          if (Array.isArray(content)) {
            for (const block of content) {
              if (block.type === 'text' && block.text) {
                responseTexts.push(block.text);
              }
            }
          }
        }
      } catch {
        // Not valid JSON, skip in this pass
      }
    }
  }

  // If we found JSON content, return it
  if (hasJsonContent && responseTexts.length > 0) {
    return responseTexts.join('\n').trim();
  }

  // Second pass: extract plain text for Codex/Gemini or when no JSON content found
  // This handles CLI executors that output plain text
  const plainTextLines: string[] = [];

  for (const log of logs) {
    // Skip JSON lines (already processed or noise)
    if (log.startsWith('{') || log.startsWith('[')) {
      continue;
    }

    // Skip metadata lines
    if (isMetadataLine(log)) {
      continue;
    }

    // Add meaningful content
    const trimmed = log.trim();
    if (trimmed && trimmed.length > 0) {
      plainTextLines.push(trimmed);
    }
  }

  // Return collected plain text
  if (plainTextLines.length > 0) {
    return plainTextLines.join('\n').trim();
  }

  return '';
}

/**
 * Extract key points from the response text.
 * Looks for bullet points, numbered lists, or important sentences.
 */
function extractKeyPoints(response: string): string[] {
  const keyPoints: string[] = [];

  // Look for bullet points or numbered lists
  const lines = response.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    // Match bullet points (-, *, •) or numbered lists (1., 2., etc.)
    if (/^[-*•]\s+.+/.test(trimmed) || /^\d+\.\s+.+/.test(trimmed)) {
      // Remove the bullet/number prefix
      const content = trimmed.replace(/^[-*•]\s+/, '').replace(/^\d+\.\s+/, '');
      if (content.length > 10 && content.length < 200 && keyPoints.length < 5) {
        keyPoints.push(content);
      }
    }
  }

  return keyPoints;
}

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

  // Get instruction
  const instruction = run.instruction || '';

  // Extract response from logs
  let response = '';
  if (run.logs && run.logs.length > 0) {
    response = extractResponseFromLogs(run.logs);
  }

  // If no response from logs, use summary as fallback
  if (!response && run.summary) {
    response = run.summary;
  }

  // Extract key points from response
  const keyPoints = extractKeyPoints(response);

  // If no bullet points found, try to extract from non-JSON logs
  if (keyPoints.length === 0 && run.logs) {
    for (const log of run.logs.slice(-20)) {
      // Skip raw JSON lines
      if (log.startsWith('{') || log.startsWith('[system]')) continue;
      // Skip empty or very short lines
      if (!log.trim() || log.trim().length < 10) continue;
      // Add meaningful content
      if (
        keyPoints.length < 3 &&
        !log.includes('Executing:') &&
        !log.includes('Working directory:') &&
        !log.includes('Instruction length:')
      ) {
        keyPoints.push(log.trim().slice(0, 150));
      }
    }
  }

  // Extract analyzed files from logs (files that were read)
  // Only match actual file paths with common source file extensions
  const analyzedFiles: string[] = [];
  if (run.logs) {
    // Match file paths that contain / and have common source code extensions
    const filePattern = /(?:Read|Viewed|Analyzed|Opened|Reading)\s+((?:[\w./\-]+\/)?[\w.\-]+\.(?:ts|tsx|js|jsx|py|go|rs|java|rb|vue|svelte|css|scss|html|json|yaml|yml|md|txt))/gi;
    for (const log of run.logs) {
      const matches = log.matchAll(filePattern);
      for (const match of matches) {
        const filePath = match[1];
        // Skip if it looks like code (contains parentheses, braces, or camelCase properties)
        if (filePath.includes('(') || filePath.includes('{') || /\.[a-z]+[A-Z]/.test(filePath)) {
          continue;
        }
        if (!analyzedFiles.includes(filePath) && analyzedFiles.length < 5) {
          analyzedFiles.push(filePath);
        }
      }
    }
  }

  return {
    type,
    title,
    instruction,
    response: response || 'No response available',
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
