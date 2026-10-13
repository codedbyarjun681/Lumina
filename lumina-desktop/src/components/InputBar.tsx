import type { KeyboardEvent } from "react";

interface InputBarProps {
  input: string;
  setInput: (value: string) => void;
  handleSend: () => void;
}

export default function InputBar({ input, setInput, handleSend }: InputBarProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="input-bar">
      <input
        type="text"
        className="input-bar-field"
        placeholder="Ask about this workspace's documents…"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button
        type="button"
        className="input-bar-send"
        onClick={handleSend}
        disabled={input.trim().length === 0}
      >
        Send
      </button>
    </div>
  );
}
