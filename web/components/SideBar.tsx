const GUEST_NAV_ITEMS = [
    { label: "Chat", active: true },
    { label: "New conversation", active: false },
    { label: "My bookings", active: false },
    { label: "Hotel information", active: false },
  ];
  
  export default function SideBar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    return (
      <>
        {/* Dims the content behind the open drawer and closes it on tap.
            Mobile-only (md:hidden) -- the desktop sidebar has no backdrop. */}
        {isOpen && (
          <div className="fixed inset-0 bg-black/40 z-30 md:hidden" onClick={onClose} />
        )}
  
        <aside
          className={`fixed md:static inset-y-0 left-0 z-40 w-60 h-full bg-janet-espresso flex flex-col shrink-0 px-4 py-6 transform transition-transform duration-200 md:translate-x-0 ${
            isOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-8 px-2">
            <div className="font-display text-2xl text-janet-champagne leading-none">Janet</div>
            <div className="text-[10px] uppercase tracking-widest text-janet-sand mt-1">
              Hotels &amp; Resorts
            </div>
          </div>
  
          <nav className="flex flex-col gap-1">
            {GUEST_NAV_ITEMS.map((item) => (
              <div
                key={item.label}
                className={
                  item.active
                    ? "rounded-lg px-3 py-2 text-sm bg-janet-espresso-elevated text-janet-cream cursor-default"
                    : "rounded-lg px-3 py-2 text-sm text-janet-walnut-light cursor-not-allowed"
                }
              >
                {item.label}
              </div>
            ))}
          </nav>
  
          <div className="border-t border-janet-espresso-elevated my-4" />
  
          <div className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-janet-walnut-light cursor-not-allowed">
            <span>Staff</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-janet-sand-soft text-janet-espresso">
              Coming soon
            </span>
          </div>
        </aside>
      </>
    );
  }