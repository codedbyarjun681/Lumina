import { useEffect, useRef, useState } from "react";
import { api, type ProviderInfo, type ProviderModel } from "../services/api";

interface ModelPickerProps {
  providerId: string | null;
  currentModel: string;
  onSelect: (providerId: string, model: string) => void;
}

export default function ModelPicker({
  providerId,
  currentModel,
  onSelect,
}: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keysSet, setKeysSet] = useState<Record<string, boolean>>({});
  const [pickedProvider, setPickedProvider] = useState<string | null>(null);
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const usableProviders = providers.filter(
    (p) => !p.needs_api_key || keysSet[p.id],
  );
  const activeProvider = providers.find((p) => p.id === pickedProvider);

  useEffect(() => {
    if (!open) {
      return;
    }
    void (async () => {
      try {
        const [providerList, settings] = await Promise.all([
          api.getProviders(),
          api.getSettings(),
        ]);
        setProviders(providerList);
        setKeysSet(settings.api_keys_set);
        setPickedProvider((prev) => prev ?? providerId);
      } catch {
        setProviders([]);
      }
    })();
  }, [open, providerId]);

  useEffect(() => {
    if (!open || pickedProvider === null) {
      return;
    }
    void (async () => {
      setLoading(true);
      try {
        setModels(await api.getModels(pickedProvider));
      } catch {
        setModels([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [open, pickedProvider]);

  // Close when clicking outside
  useEffect(() => {
    if (!open) {
      return;
    }
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div className="model-picker" ref={ref}>
      <button
        type="button"
        className="model-picker-trigger"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) {
            setPickedProvider(providerId);
          }
        }}
      >
        <span className="model-picker-dot" />
        <span className="model-picker-label">
          {currentModel || "Model"}
        </span>
        <span className="model-picker-caret">▾</span>
      </button>

      {open && (
        <div className="model-picker-popover">
          <p className="model-picker-section-label">Provider</p>
          <div className="model-picker-providers">
            {usableProviders.map((p) => (
              <button
                key={p.id}
                type="button"
                className={
                  p.id === pickedProvider
                    ? "model-picker-option model-picker-option--active"
                    : "model-picker-option"
                }
                onClick={() => setPickedProvider(p.id)}
              >
                {p.name}
              </button>
            ))}
            {usableProviders.length === 0 && (
              <p className="model-picker-empty">
                No usable providers — add an API key in Settings.
              </p>
            )}
          </div>

          <p className="model-picker-section-label">Models</p>
          {!pickedProvider ? (
            <p className="model-picker-empty">Pick a provider first</p>
          ) : loading || models.length === 0 ? (
            <p className="model-picker-empty">
              {loading
                ? "Loading models…"
                : activeProvider
                  ? `No models from ${activeProvider.name}`
                  : "No models found"}
            </p>
          ) : (
            <div className="model-picker-list">
              {models.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className={
                    m.id === currentModel && pickedProvider === providerId
                      ? "model-picker-option model-picker-option--active"
                      : "model-picker-option"
                  }
                  onClick={() => {
                    onSelect(pickedProvider, m.id);
                    setOpen(false);
                  }}
                >
                  {m.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
