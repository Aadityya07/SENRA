import { memo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import rehypeHighlight from 'rehype-highlight'
import { Check, Copy } from 'lucide-react'

function CodeBlock({ children, ...props }: React.HTMLAttributes<HTMLPreElement>) {
  const [copied, setCopied] = useState(false)
  const copy = (e: React.MouseEvent<HTMLButtonElement>) => {
    const pre = e.currentTarget.parentElement?.querySelector('pre')
    navigator.clipboard?.writeText(pre?.innerText ?? '')
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }
  return (
    <div className="group relative">
      <button
        onClick={copy}
        className="absolute right-2 top-2 z-10 rounded-md bg-white/10 p-1.5 text-white/60 opacity-0 transition hover:text-white group-hover:opacity-100"
        aria-label="Copy code"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      <pre {...props}>{children}</pre>
    </div>
  )
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="senra-md prose prose-invert max-w-none prose-p:my-3 prose-headings:font-semibold prose-headings:tracking-tight prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-li:my-1 prose-strong:text-white prose-a:text-sky-300 prose-hr:border-white/10 text-[15px] text-white/90">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          pre: CodeBlock,
          a: ({ ...p }) => <a {...p} target="_blank" rel="noreferrer" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

export default memo(Markdown)
