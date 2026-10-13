import type { ReactNode } from "react";

interface SidePanelProps {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}

export default function SidePanel({
  title,
  isOpen,
  onClose,
  children,
}: SidePanelProps) {
  return (
    <div
      className={isOpen ? "sidepanel-overlay sidepanel-overlay--open" : "sidepanel-overlay"}
      onClick={onClose}
      aria-hidden={!isOpen}
    >
      <div
        className={isOpen ? "sidepanel sidepanel--open" : "sidepanel"}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <header className="sidepanel-header">
          <h2 className="sidepanel-title">{title}</h2>
          <button
            type="button"
            className="sidepanel-close"
            onClick={onClose}
            aria-label="Close panel"
          >
            ✕
          </button>
        </header>
        <div className="sidepanel-body">{children}</div>
      </div>
    </div>
  );
}
