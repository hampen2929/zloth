'use client';

interface DiffViewerProps {
  patch: string;
}

export function DiffViewer({ patch }: DiffViewerProps) {
  if (!patch) {
    return <p className="text-gray-500">No changes.</p>;
  }

  // Parse the patch into files
  const files = parsePatch(patch);

  return (
    <div className="space-y-4">
      {files.map((file, index) => (
        <div
          key={index}
          className="border border-gray-800 rounded-lg overflow-hidden"
        >
          <div className="px-3 py-2 bg-gray-800 text-sm font-mono">
            {file.path}
          </div>
          <div className="overflow-x-auto">
            <pre className="text-xs p-0 m-0 bg-gray-950">
              {file.hunks.map((hunk, hunkIndex) => (
                <div key={hunkIndex}>
                  <div className="px-3 py-1 bg-blue-900/30 text-blue-400 border-y border-gray-800">
                    {hunk.header}
                  </div>
                  {hunk.lines.map((line, lineIndex) => (
                    <div
                      key={lineIndex}
                      className={`px-3 py-0.5 font-mono ${getLineClass(line)}`}
                    >
                      {line}
                    </div>
                  ))}
                </div>
              ))}
            </pre>
          </div>
        </div>
      ))}
    </div>
  );
}

function getLineClass(line: string): string {
  if (line.startsWith('+') && !line.startsWith('+++')) {
    return 'bg-green-900/30 text-green-300';
  }
  if (line.startsWith('-') && !line.startsWith('---')) {
    return 'bg-red-900/30 text-red-300';
  }
  return 'text-gray-400';
}

interface ParsedFile {
  path: string;
  hunks: { header: string; lines: string[] }[];
}

function parsePatch(patch: string): ParsedFile[] {
  const files: ParsedFile[] = [];
  const lines = patch.split('\n');

  let currentFile: ParsedFile | null = null;
  let currentHunk: { header: string; lines: string[] } | null = null;

  for (const line of lines) {
    if (line.startsWith('diff ') || line.startsWith('--- ')) {
      // Skip diff header, we use +++ for file path
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

      currentFile = { path, hunks: [] };
      currentHunk = null;
      continue;
    }

    if (line.startsWith('@@')) {
      // New hunk
      if (currentFile && currentHunk) {
        currentFile.hunks.push(currentHunk);
      }
      currentHunk = { header: line, lines: [] };
      continue;
    }

    if (currentHunk) {
      currentHunk.lines.push(line);
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
