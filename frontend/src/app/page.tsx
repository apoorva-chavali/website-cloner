'use client';

import { useState } from 'react';

export default function Home() {
  const [html, setHtml] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<string[]>([]);

  const addDebug = (message: string) => {
    setDebugInfo(prev => [...prev, `${new Date().toLocaleTimeString()}: ${message}`]);
  };

  async function handleClone(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setHtml('');
    setLoading(true);
    setDebugInfo([]);

    const url = new FormData(e.currentTarget as HTMLFormElement)
                  .get('url') as string;

    addDebug(`Starting clone for URL: ${url}`);

    try {

      addDebug('Testing API route...');
      
      const res = await fetch('/api/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      addDebug(`API Response Status: ${res.status} ${res.statusText}`);
      addDebug(`Response Headers: ${JSON.stringify([...res.headers.entries()])}`);

      if (!res.ok) {
        const errorText = await res.text();
        addDebug(`Error Response Body: ${errorText}`);
        throw new Error(`API error ${res.status}: ${errorText}`);
      }

      if (!res.body) {
        addDebug('No response body received');
        throw new Error('Empty response body');
      }

      addDebug('Starting to read stream...');

      const reader = res.body
        .pipeThrough(new TextDecoderStream())
        .getReader();

      let chunk = '';
      let chunkCount = 0;
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          addDebug(`Stream ended. Total chunks: ${chunkCount}, Total length: ${chunk.length}`);
          break;
        }
        
        chunkCount++;
        chunk += value;
        addDebug(`Received chunk ${chunkCount}, size: ${value.length}, total: ${chunk.length}`);
        setHtml(chunk);
      }

      if (chunk.length === 0) {
        addDebug('Warning: Received empty content');
      }

    } catch (err: any) {
      const errorMsg = err.message ?? 'Unknown error';
      addDebug(`Error occurred: ${errorMsg}`);
      setError(errorMsg);
    } finally {
      setLoading(false);
      addDebug('Clone process completed');
    }
  }

  return (
    <main className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Website Cloner - Debug Mode</h1>
      
      <form onSubmit={handleClone} className="flex gap-2">
        <input
          name="url"
          placeholder="https://example.com"
          required
          className="flex-1 rounded border p-2"
          
        />
        <button
          className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-60"
          disabled={loading}
        >
          {loading ? 'Cloning…' : 'Clone'}
        </button>
      </form>

      {/* Debug Information */}
      <div className="rounded bg-black text-gray-200 p-3">
      <h3 className="font-semibold mb-2 text-white">Debug Info:</h3>
      <div className="text-sm space-y-1 max-h-40 overflow-y-auto">
        {debugInfo.map((info, i) => (
          <div key={i} className="font-mono text-xs">{info}</div>
        ))}
      </div>
    </div>


      {error && (
        <div className="rounded bg-red-100 p-3 text-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      {html && (
        <div className="space-y-2">
          <div className="text-sm text-gray-600">
            Generated HTML ({html.length} characters)
            {html.includes('<!-- Error:') && (
              <span className="text-red-600 ml-2">⚠ Contains error comment</span>
            )}
          </div>
          <iframe
            title="clone"
            sandbox="allow-scripts allow-same-origin"
            srcDoc={html}
            className="h-[60vh] w-full rounded border"
          />
          
          {/* Show raw HTML for debugging */}
          <details className="mt-2">
            <summary className="cursor-pointer text-sm text-gray-600">Show raw HTML</summary>
            <pre className="mt-2 bg-gray-100 p-2 text-xs overflow-auto max-h-40 rounded">
              {html}
            </pre>
          </details>
        </div>
      )}
    </main>
  );
}