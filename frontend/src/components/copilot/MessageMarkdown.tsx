import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/** Render advisor responses as text and Markdown, without executing model-provided HTML. */
export function MessageMarkdown({ content }: { content: string }) {
  return (
    <div className="min-w-0 space-y-3 leading-relaxed [overflow-wrap:anywhere]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={['img']}
        components={{
          h1: ({ children }) => <h3 className="pt-2 text-base font-semibold first:pt-0">{children}</h3>,
          h2: ({ children }) => <h3 className="pt-2 text-sm font-semibold first:pt-0">{children}</h3>,
          h3: ({ children }) => <h3 className="pt-2 text-sm font-semibold first:pt-0">{children}</h3>,
          h4: ({ children }) => <h4 className="pt-2 font-semibold">{children}</h4>,
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          ul: ({ children }) => <ul className="list-disc space-y-1.5 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1.5 pl-5">{children}</ol>,
          li: ({ children }) => <li className="pl-0.5 [&>p]:my-1">{children}</li>,
          hr: () => <hr className="border-border-subtle" />,
          blockquote: ({ children }) => <blockquote className="border-l border-border-subtle pl-3 text-text-secondary">{children}</blockquote>,
          a: ({ href, children }) => href
            ? <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent-emerald underline underline-offset-2">{children}</a>
            : <span>{children}</span>,
          pre: ({ children }) => <pre className="max-w-full overflow-x-auto rounded-lg bg-surface-container-high p-3 text-[11px] [overflow-wrap:normal]">{children}</pre>,
          code: ({ children }) => <code className="font-mono text-[0.95em]">{children}</code>,
          table: ({ children }) => (
            <div className="max-w-full overflow-x-auto rounded-lg border border-border-subtle">
              <table className="w-full border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="border-b border-border-subtle bg-surface-container-high px-3 py-2 font-semibold">{children}</th>,
          td: ({ children }) => <td className="border-b border-border-subtle px-3 py-2 last:border-b-0">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
