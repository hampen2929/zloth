'use client';

import { useState, useMemo, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  DocumentIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClipboardIcon,
  ClipboardDocumentCheckIcon,
  DocumentArrowDownIcon,
  FolderIcon,
  MinusIcon,
  PlusIcon,
} from '@heroicons/react/24/outline';

interface DiffViewerProps {
  patch: string;
}

type ViewMode = 'unified' | 'split';

interface ParsedFile {
  path: string;
  hunks: ParsedHunk[];
  addedLines: number;
  removedLines: number;
}

interface ParsedHunk {
  header: string;
  lines: ParsedLine[];
  oldStart: number;
  newStart: number;
}

interface ParsedLine {
  content: string;
  type: 'add' | 'remove' | 'context';
  oldLineNumber: number | null;
  newLineNumber: number | null;
}

export function DiffViewer({ patch }: DiffViewerProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [collapsedHunks, setCollapsedHunks] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<ViewMode>('unified');
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const [copiedPatch, setCopiedPatch] = useState(false);

  // Parse patch into files
  const files = useMemo(() => parsePatch(patch), [patch]);

  // Initialize all files as expanded
  useState(() => {
    if (files.length > 0) {
      setExpandedFiles(new Set(files.map((f) => f.path)));
    }
  });

  const toggleFile = useCallback((path: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const toggleHunk = useCallback((key: string) => {
    setCollapsedHunks((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    setExpandedFiles(new Set(files.map((f) => f.path)));
    setCollapsedHunks(new Set());
  }, [files]);

  const collapseAll = useCallback(() => {
    setExpandedFiles(new Set());
    setCollapsedHunks(new Set(
      files.flatMap((f, fi) =>
        f.hunks.map((_, hi) => `${fi}-${hi}`)
      )
    ));
  }, [files]);

  const copyPath = useCallback(async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedPath(path);
      setTimeout(() => setCopiedPath(null), 2000);
    } catch {
      // Ignore clipboard errors
    }
  }, []);

  const copyPatch = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(patch);
      setCopiedPatch(true);
      setTimeout(() => setCopiedPatch(false), 2000);
    } catch {
      // Ignore clipboard errors
    }
  }, [patch]);

  const downloadPatch = useCallback(() => {
    const blob = new Blob([patch], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'changes.patch';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [patch]);

  const scrollToFile = useCallback((path: string) => {
    const element = document.getElementById(`file-${path.replace(/[^a-zA-Z0-9]/g, '-')}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    // Ensure file is expanded
    setExpandedFiles((prev) => new Set([...prev, path]));
  }, []);

  if (!patch) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <DocumentIcon className="w-12 h-12 text-gray-700 mb-3" />
        <p className="text-gray-500 text-sm">No changes</p>
      </div>
    );
  }

  const totalAdded = files.reduce((sum, f) => sum + f.addedLines, 0);
  const totalRemoved = files.reduce((sum, f) => sum + f.removedLines, 0);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <FolderIcon className="w-4 h-4 text-gray-500" />
            <span className="text-gray-400">
              {files.length} file{files.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-green-400 flex items-center gap-0.5">
              <PlusIcon className="w-3 h-3" />
              {totalAdded}
            </span>
            <span className="text-red-400 flex items-center gap-0.5">
              <MinusIcon className="w-3 h-3" />
              {totalRemoved}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex bg-gray-800 rounded-md p-0.5">
            <button
              onClick={() => setViewMode('unified')}
              className={cn(
                'px-2 py-1 text-xs rounded transition-colors',
                viewMode === 'unified'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              Unified
            </button>
            <button
              onClick={() => setViewMode('split')}
              className={cn(
                'px-2 py-1 text-xs rounded transition-colors',
                viewMode === 'split'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              Split
            </button>
          </div>

          {/* Expand/Collapse all */}
          <button
            onClick={expandAll}
            className="px-2 py-1 text-xs text-gray-400 hover:text-white transition-colors"
            title="Expand all"
          >
            Expand
          </button>
          <button
            onClick={collapseAll}
            className="px-2 py-1 text-xs text-gray-400 hover:text-white transition-colors"
            title="Collapse all"
          >
            Collapse
          </button>

          {/* Copy/Download */}
          <button
            onClick={copyPatch}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
            title="Copy patch"
          >
            {copiedPatch ? (
              <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-400" />
            ) : (
              <ClipboardIcon className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={downloadPatch}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors"
            title="Download patch"
          >
            <DocumentArrowDownIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* File list sidebar */}
        <div className="w-64 flex-shrink-0 border-r border-gray-800 overflow-y-auto bg-gray-900/30">
          <div className="py-2">
            {files.map((file) => (
              <button
                key={file.path}
                onClick={() => scrollToFile(file.path)}
                className={cn(
                  'w-full px-3 py-1.5 text-left text-xs hover:bg-gray-800 transition-colors',
                  'flex items-center gap-2 group'
                )}
              >
                <DocumentIcon className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
                <span className="truncate text-gray-300 group-hover:text-white flex-1">
                  {getFileName(file.path)}
                </span>
                <span className="text-xs text-gray-600 flex-shrink-0">
                  <span className="text-green-500">+{file.addedLines}</span>
                  {' '}
                  <span className="text-red-500">-{file.removedLines}</span>
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Diff content */}
        <div className="flex-1 overflow-y-auto">
          <div className="space-y-4 p-4">
            {files.map((file, fileIndex) => {
              const isExpanded = expandedFiles.has(file.path);
              const fileId = `file-${file.path.replace(/[^a-zA-Z0-9]/g, '-')}`;

              return (
                <div
                  key={file.path}
                  id={fileId}
                  className="border border-gray-800 rounded-lg overflow-hidden"
                >
                  {/* File header */}
                  <div
                    className={cn(
                      'flex items-center justify-between px-3 py-2 bg-gray-800 cursor-pointer',
                      'hover:bg-gray-750 transition-colors'
                    )}
                    onClick={() => toggleFile(file.path)}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {isExpanded ? (
                        <ChevronDownIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      ) : (
                        <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      )}
                      <span className="text-sm font-mono text-gray-200 truncate">
                        {file.path}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="text-xs">
                        <span className="text-green-400">+{file.addedLines}</span>
                        {' '}
                        <span className="text-red-400">-{file.removedLines}</span>
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          copyPath(file.path);
                        }}
                        className="p-1 text-gray-500 hover:text-white rounded transition-colors"
                        title="Copy file path"
                      >
                        {copiedPath === file.path ? (
                          <ClipboardDocumentCheckIcon className="w-3.5 h-3.5 text-green-400" />
                        ) : (
                          <ClipboardIcon className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Hunks */}
                  {isExpanded && (
                    <div className="overflow-x-auto">
                      {viewMode === 'unified' ? (
                        <UnifiedView
                          file={file}
                          fileIndex={fileIndex}
                          collapsedHunks={collapsedHunks}
                          toggleHunk={toggleHunk}
                        />
                      ) : (
                        <SplitView
                          file={file}
                          fileIndex={fileIndex}
                          collapsedHunks={collapsedHunks}
                          toggleHunk={toggleHunk}
                        />
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Unified view component
function UnifiedView({
  file,
  fileIndex,
  collapsedHunks,
  toggleHunk,
}: {
  file: ParsedFile;
  fileIndex: number;
  collapsedHunks: Set<string>;
  toggleHunk: (key: string) => void;
}) {
  return (
    <pre className="text-xs m-0 bg-gray-950">
      {file.hunks.map((hunk, hunkIndex) => {
        const hunkKey = `${fileIndex}-${hunkIndex}`;
        const isCollapsed = collapsedHunks.has(hunkKey);

        return (
          <div key={hunkIndex}>
            {/* Hunk header */}
            <div
              className={cn(
                'px-3 py-1 bg-blue-900/30 text-blue-400 border-y border-gray-800',
                'flex items-center gap-2 cursor-pointer hover:bg-blue-900/40 transition-colors'
              )}
              onClick={() => toggleHunk(hunkKey)}
            >
              {isCollapsed ? (
                <ChevronRightIcon className="w-3 h-3 flex-shrink-0" />
              ) : (
                <ChevronDownIcon className="w-3 h-3 flex-shrink-0" />
              )}
              <span className="font-mono">{hunk.header}</span>
            </div>

            {/* Hunk lines */}
            {!isCollapsed && (
              <table className="w-full border-collapse">
                <tbody>
                  {hunk.lines.map((line, lineIndex) => (
                    <tr
                      key={lineIndex}
                      className={cn(
                        line.type === 'add' && 'bg-green-900/20',
                        line.type === 'remove' && 'bg-red-900/20'
                      )}
                    >
                      <td className="w-10 px-2 py-0.5 text-right text-gray-600 select-none border-r border-gray-800/50 font-mono">
                        {line.oldLineNumber || ''}
                      </td>
                      <td className="w-10 px-2 py-0.5 text-right text-gray-600 select-none border-r border-gray-800/50 font-mono">
                        {line.newLineNumber || ''}
                      </td>
                      <td
                        className={cn(
                          'px-3 py-0.5 font-mono whitespace-pre',
                          line.type === 'add' && 'text-green-300',
                          line.type === 'remove' && 'text-red-300',
                          line.type === 'context' && 'text-gray-400'
                        )}
                      >
                        {line.content}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </pre>
  );
}

// Split view component
function SplitView({
  file,
  fileIndex,
  collapsedHunks,
  toggleHunk,
}: {
  file: ParsedFile;
  fileIndex: number;
  collapsedHunks: Set<string>;
  toggleHunk: (key: string) => void;
}) {
  return (
    <pre className="text-xs m-0 bg-gray-950">
      {file.hunks.map((hunk, hunkIndex) => {
        const hunkKey = `${fileIndex}-${hunkIndex}`;
        const isCollapsed = collapsedHunks.has(hunkKey);

        // Pair up lines for split view
        const pairs = pairLinesForSplitView(hunk.lines);

        return (
          <div key={hunkIndex}>
            {/* Hunk header */}
            <div
              className={cn(
                'px-3 py-1 bg-blue-900/30 text-blue-400 border-y border-gray-800',
                'flex items-center gap-2 cursor-pointer hover:bg-blue-900/40 transition-colors'
              )}
              onClick={() => toggleHunk(hunkKey)}
            >
              {isCollapsed ? (
                <ChevronRightIcon className="w-3 h-3 flex-shrink-0" />
              ) : (
                <ChevronDownIcon className="w-3 h-3 flex-shrink-0" />
              )}
              <span className="font-mono">{hunk.header}</span>
            </div>

            {/* Split view lines */}
            {!isCollapsed && (
              <table className="w-full border-collapse">
                <tbody>
                  {pairs.map((pair, pairIndex) => (
                    <tr key={pairIndex}>
                      {/* Left side (old) */}
                      <td className="w-10 px-2 py-0.5 text-right text-gray-600 select-none border-r border-gray-800/50 font-mono">
                        {pair.old?.oldLineNumber || ''}
                      </td>
                      <td
                        className={cn(
                          'w-1/2 px-3 py-0.5 font-mono whitespace-pre border-r border-gray-800',
                          pair.old?.type === 'remove' && 'bg-red-900/20 text-red-300',
                          pair.old?.type === 'context' && 'text-gray-400',
                          !pair.old && 'bg-gray-900/50'
                        )}
                      >
                        {pair.old?.content || ''}
                      </td>

                      {/* Right side (new) */}
                      <td className="w-10 px-2 py-0.5 text-right text-gray-600 select-none border-r border-gray-800/50 font-mono">
                        {pair.new?.newLineNumber || ''}
                      </td>
                      <td
                        className={cn(
                          'w-1/2 px-3 py-0.5 font-mono whitespace-pre',
                          pair.new?.type === 'add' && 'bg-green-900/20 text-green-300',
                          pair.new?.type === 'context' && 'text-gray-400',
                          !pair.new && 'bg-gray-900/50'
                        )}
                      >
                        {pair.new?.content || ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </pre>
  );
}

// Helper to pair lines for split view
function pairLinesForSplitView(
  lines: ParsedLine[]
): { old: ParsedLine | null; new: ParsedLine | null }[] {
  const pairs: { old: ParsedLine | null; new: ParsedLine | null }[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.type === 'context') {
      pairs.push({ old: line, new: line });
      i++;
    } else if (line.type === 'remove') {
      // Look ahead for matching add
      const removeLines: ParsedLine[] = [];
      while (i < lines.length && lines[i].type === 'remove') {
        removeLines.push(lines[i]);
        i++;
      }

      const addLines: ParsedLine[] = [];
      while (i < lines.length && lines[i].type === 'add') {
        addLines.push(lines[i]);
        i++;
      }

      // Pair them up
      const maxLen = Math.max(removeLines.length, addLines.length);
      for (let j = 0; j < maxLen; j++) {
        pairs.push({
          old: removeLines[j] || null,
          new: addLines[j] || null,
        });
      }
    } else if (line.type === 'add') {
      // Add without matching remove
      pairs.push({ old: null, new: line });
      i++;
    } else {
      i++;
    }
  }

  return pairs;
}

// Helper to get file name from path
function getFileName(path: string): string {
  const parts = path.split('/');
  return parts[parts.length - 1];
}

// Parse patch into structured format
function parsePatch(patch: string): ParsedFile[] {
  const files: ParsedFile[] = [];
  const lines = patch.split('\n');

  let currentFile: ParsedFile | null = null;
  let currentHunk: ParsedHunk | null = null;
  let oldLineNum = 0;
  let newLineNum = 0;

  for (const line of lines) {
    if (line.startsWith('diff ') || line.startsWith('--- ')) {
      continue;
    }

    if (line.startsWith('+++ ')) {
      // New file
      if (currentFile) {
        if (currentHunk) {
          currentFile.hunks.push(currentHunk);
        }
        files.push(currentFile);
      }

      let path = line.slice(4).trim();
      if (path.startsWith('b/')) {
        path = path.slice(2);
      }

      currentFile = { path, hunks: [], addedLines: 0, removedLines: 0 };
      currentHunk = null;
      continue;
    }

    if (line.startsWith('@@')) {
      // New hunk
      if (currentFile && currentHunk) {
        currentFile.hunks.push(currentHunk);
      }

      // Parse hunk header: @@ -oldStart,oldCount +newStart,newCount @@
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      oldLineNum = match ? parseInt(match[1], 10) : 1;
      newLineNum = match ? parseInt(match[2], 10) : 1;

      currentHunk = { header: line, lines: [], oldStart: oldLineNum, newStart: newLineNum };
      continue;
    }

    if (currentHunk && currentFile) {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        currentHunk.lines.push({
          content: line,
          type: 'add',
          oldLineNumber: null,
          newLineNumber: newLineNum++,
        });
        currentFile.addedLines++;
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        currentHunk.lines.push({
          content: line,
          type: 'remove',
          oldLineNumber: oldLineNum++,
          newLineNumber: null,
        });
        currentFile.removedLines++;
      } else {
        currentHunk.lines.push({
          content: line,
          type: 'context',
          oldLineNumber: oldLineNum++,
          newLineNumber: newLineNum++,
        });
      }
    }
  }

  // Push last file and hunk
  if (currentFile) {
    if (currentHunk) {
      currentFile.hunks.push(currentHunk);
    }
    files.push(currentFile);
  }

  return files;
}
