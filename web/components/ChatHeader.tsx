export default function ChatHeader({ onMenuClick }: { onMenuClick: () => void }) {
    return (
        <header className="relative flex items-center justify-center border-b border-border-subtle bg-janet-cream px-4 py-3">
            {/* Hamburger -- mobile only (md:hidden). Absolutely positioned so it
            overlays the left edge without disturbing the logo's centering,
            which stays untouched on every screen size. */}
            <button
                onClick={onMenuClick}
                className="md:hidden absolute left-4 top-1/2 -translate-y-1/2 text-janet-ink p-1"
                aria-label="Open menu"
            >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <line x1="3" y1="6" x2="21" y2="6" />
                    <line x1="3" y1="12" x2="21" y2="12" />
                    <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
            </button>
            <img src="/janet-logo.png" alt="Janet Hotels & Resorts" className="h-20 md:h-35 w-auto" />
        </header>
    );
}
