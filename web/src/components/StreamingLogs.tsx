'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { runsApi } from '@/lib/api';
import type { OutputLine } from '@/types';
import { cn } from '@/lib/utils';

interface StreamingLogsProps {
  /** The run ID to stream logs for */
  runId: string;
  /** Whether the run is currently running */
  isRunning: boolean;
  /** Initial logs to display (from previous fetches) */
  initialLogs?: string[];
  /** Optional class name for the container */
  className?: string;
}

/**
 * StreamingLogs component displays CLI output in real-time via polling.
 *
 * Features:
 * - Real-time polling of CLI output (500ms interval)
 * - Auto-scroll to bottom (toggleable)
 * - Line numbers
 * - Error handling
 * - Graceful completion when run finishes
 */
export function StreamingLogs({
  runId,
  isRunning,
  initialLogs = [],
  className,
}: StreamingLogsProps) {
  const [lines, setLines] = useState<string[]>(initialLogs);
  const [isConnected, setIsConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const linesLengthRef = useRef(initialLogs.length);

  // Handle scroll to detect if user manually scrolled up
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  }, []);

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  // Update linesLengthRef when lines change
  useEffect(() => {
    linesLengthRef.current = lines.length;
  }, [lines.length]);

  // SSE connection effect
  useEffect(() => {
    // Only connect if running
    if (!isRunning) {
      setIsConnected(false);
      return;
    }

    setError(null);
    setIsConnected(true);

    // Start streaming from the current line count
    // This avoids duplicate lines if we already have some from initialLogs
    // Using ref to avoid reconnection loops when lines change
    const fromLine = linesLengthRef.current;

    const cleanup = runsApi.streamLogs(runId, {
      fromLine,
      onLine: (outputLine: OutputLine) => {
        setLines((prev) => {
          // Avoid duplicates by checking line number
          if (outputLine.line_number < prev.length) {
            return prev;
          }
          // Fill any gaps with empty lines if needed
          const newLines = [...prev];
          while (newLines.length < outputLine.line_number) {
            newLines.push('');
          }
          newLines.push(outputLine.content);
          return newLines;
        });
      },
      onComplete: () => {
        setIsConnected(false);
      },
      onError: (err: Error) => {
        console.error('Stream error:', err);
        setError(err.message);
        setIsConnected(false);
      },
    });

    cleanupRef.current = cleanup;

    return () => {
      cleanup();
      cleanupRef.current = null;
    };
  }, [runId, isRunning]);

  // Scroll to bottom button click
  const scrollToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
      setAutoScroll(true);
    }
  }, []);

  return (
    <div className={cn('relative', className)}>
      {/* Connection status indicator */}
      {isRunning && (
        <div className="absolute top-2 right-2 flex items-center gap-2 z-10">
          {isConnected ? (
            <span className="flex items-center gap-1.5 text-xs text-green-400 bg-gray-800/90 px-2 py-1 rounded">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              Streaming
            </span>
          ) : error ? (
            <span className="flex items-center gap-1.5 text-xs text-red-400 bg-gray-800/90 px-2 py-1 rounded">
              <span className="w-2 h-2 bg-red-400 rounded-full" />
              Disconnected
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-yellow-400 bg-gray-800/90 px-2 py-1 rounded">
              <span className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
              Connecting...
            </span>
          )}
        </div>
      )}

      {/* Log container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="font-mono text-xs bg-gray-900 rounded-lg p-3 overflow-y-auto max-h-[500px] min-h-[200px]"
      >
        {lines.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            {isRunning ? 'Waiting for output...' : 'No logs available.'}
          </div>
        ) : (
          lines.map((line, i) => (
            <div
              key={i}
              className="text-gray-400 leading-relaxed whitespace-pre-wrap hover:bg-gray-800/50 -mx-2 px-2"
            >
              <span className="text-gray-600 mr-3 select-none inline-block w-8 text-right">
                {i + 1}
              </span>
              <span>{line}</span>
            </div>
          ))
        )}

        {/* Streaming indicator at bottom */}
        {isRunning && isConnected && (
          <div className="flex items-center gap-2 text-blue-400 mt-2 pt-2 border-t border-gray-800">
            <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
            <span className="text-xs">Receiving output...</span>
          </div>
        )}
      </div>

      {/* Scroll to bottom button (shown when not at bottom) */}
      {!autoScroll && lines.length > 10 && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 right-4 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1.5 rounded-full shadow-lg transition-colors flex items-center gap-1.5"
        >
          <svg
            className="w-3 h-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
          Scroll to bottom
        </button>
      )}

      {/* Error message */}
      {error && (
        <div className="mt-2 text-xs text-red-400 bg-red-900/20 px-3 py-2 rounded">
          Connection error: {error}
        </div>
      )}
    </div>
  );
}
