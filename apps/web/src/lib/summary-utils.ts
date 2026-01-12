/**
 * Utility functions for structured summary display.
 */
import type { Run, StructuredSummary, SummaryType } from '@/types';

/**
 * Extract assistant's response text from logs.
 * Logs may contain JSON lines in stream-json format from Claude Code CLI.
 */
function extractResponseFromLogs(logs: string[]): string {
  const responseTexts: string[] = [];

  for (const log of logs) {
    // Try to parse as JSON (stream-json format)
    if (log.startsWith('{')) {
      try {
        const data = JSON.parse(log);
        if (data.type === 'assistant' && data.message?.content) {
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
        // Not valid JSON, skip
      }
    }
  }

  // Join all response texts
  const fullResponse = responseTexts.join('\n').trim();

  // If we got a response, return it (truncated if too long)
  if (fullResponse) {
    // Return first 2000 chars for display
    if (fullResponse.length > 2000) {
      return fullResponse.slice(0, 2000) + '...';
    }
    return fullResponse;
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
