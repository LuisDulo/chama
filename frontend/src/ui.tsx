import { ReactNode, useCallback, useEffect, useState } from "react";

import { ApiError } from "./api";
import { CheckIcon } from "./icons";

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, tone }: { label: string; value: string; tone?: "gold" | "alert" }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

const GOOD = ["paid", "active", "approved", "confirmed"];
const BAD = ["overdue", "failed", "rejected", "suspended", "expired"];
const WAITING = ["pending", "proposed", "due", "partial"];

export function Badge({ status }: { status: string }) {
  const tone = GOOD.includes(status) ? "good" : BAD.includes(status) ? "bad" : WAITING.includes(status) ? "wait" : "";
  return <span className={`badge ${tone}`}>{status}</span>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Table({ headings, children }: { headings: string[]; children: ReactNode }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headings.map((heading) => (
              <th key={heading} scope="col">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Notice({ message, onClose }: { message: { text: string; error?: boolean } | null; onClose: () => void }) {
  if (!message) return null;
  return (
    <div className={`notice ${message.error ? "error" : ""}`} role={message.error ? "alert" : "status"}>
      {!message.error && <CheckIcon />}
      <span>{message.text}</span>
      <button type="button" className="link" onClick={onClose} aria-label="Dismiss">
        Dismiss
      </button>
    </div>
  );
}

/** Loads data for a screen and exposes a reload, a loading flag and the last error. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await load());
      setError(null);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Could not load this page.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload };
}

/** Runs an action and turns its outcome into a notice. */
export function useAction() {
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>, success?: string) {
    setBusy(true);
    try {
      await action();
      if (success) setMessage({ text: success });
      return true;
    } catch (problem) {
      setMessage({ text: problem instanceof Error ? problem.message : "Something went wrong.", error: true });
      return false;
    } finally {
      setBusy(false);
    }
  }

  return { message, setMessage, busy, run, clear: () => setMessage(null) };
}

export function formData(event: React.FormEvent<HTMLFormElement>): Record<string, string> {
  event.preventDefault();
  return Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
}
