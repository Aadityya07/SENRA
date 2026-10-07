export default function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <radialGradient id="senra-logo" cx="35%" cy="30%" r="80%">
          <stop offset="0" stopColor="#ffb36b" />
          <stop offset="0.45" stopColor="#ff3ea5" />
          <stop offset="0.8" stopColor="#8a5cff" />
          <stop offset="1" stopColor="#3b82f6" />
        </radialGradient>
      </defs>
      <circle cx="16" cy="16" r="13" fill="url(#senra-logo)" />
      <g fill="none" stroke="rgba(0,0,0,0.35)" strokeWidth="1">
        <ellipse cx="16" cy="16" rx="13" ry="4.5" />
        <ellipse cx="16" cy="16" rx="13" ry="9" />
      </g>
    </svg>
  )
}
