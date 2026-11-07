import { useState } from "react";

import { api, post } from "../api";
import { can, day, money, words } from "../format";
import { PhoneIcon, PlusIcon, RefreshIcon } from "../icons";
import { ContributionRow, Member, PaymentRow, ScheduleRow } from "../types";
import { Badge, Card, Empty, Field, formData, Notice, Table, useAction, useLoad } from "../ui";
import { useChama } from "./ChamaLayout";

interface Loaded {
  schedule: ScheduleRow[];
  contributions: ContributionRow[];
  payments: PaymentRow[];
  members: Member[];
}

export function Contributions() {
  const { chama } = useChama();
  const officer = can(chama.my_permissions, "record_contributions");
  const viewsAll = can(chama.my_permissions, "view_finances");
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const [prompt, setPrompt] = useState<PaymentRow | null>(null);
  const { message, setMessage, clear, busy, run } = useAction();
  const base = `/api/chamas/${chama.id}`;
  const query = scope === "all" ? "?scope=all" : "";

  const { data, reload } = useLoad<Loaded>(async () => {
    const [schedule, contributions, payments, members] = await Promise.all([
      api<ScheduleRow[]>(`${base}/contribution-schedules/${query}`),
      api<ContributionRow[]>(`${base}/contributions/${query}`),
      api<PaymentRow[]>(`${base}/payments/${query}`),
      officer ? api<Member[]>(`${base}/members/`) : Promise.resolve([]),
    ]);
    return { schedule, contributions, payments, members };
  }, [chama.id, scope]);

  const c = chama.currency;

  async function payByMpesa(event: React.FormEvent<HTMLFormElement>) {
    const { amount } = formData(event);
    let payment: PaymentRow | null = null;
    const ok = await run(async () => {
      payment = await post<PaymentRow>("/api/payments/stk-push/", { chama_id: chama.id, amount });
    });
    if (!ok || !payment) return;
    if ((payment as PaymentRow).simulated) setPrompt(payment);
    else setMessage({ text: "Check your phone and enter your M-Pesa PIN." });
    await reload();
  }

  async function answer(accept: boolean) {
    const payment = prompt!;
    setPrompt(null);
    await run(() => post(`/api/payments/${payment.id}/simulate/`, { accept }), accept ? "Payment received. Thank you." : "Payment cancelled.");
    await reload();
  }

  async function recordCash(event: React.FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    const values = formData(event);
    if (await run(() => post(`${base}/contributions/`, values), "Contribution recorded.")) {
      form.reset();
      await reload();
    }
  }

  async function generate() {
    let created = 0;
    await run(async () => {
      created = (await post<{ created: number }>(`${base}/contribution-schedules/generate/`)).created;
    });
    setMessage({ text: `${created} new schedule entr${created === 1 ? "y" : "ies"} created.` });
    await reload();
  }

  async function reconcile() {
    let text = "";
    await run(async () => {
      const r = await post<Record<string, number>>("/api/payments/reconcile/", { chama_id: chama.id });
      text = `Checked ${r.checked}: ${r.confirmed} confirmed, ${r.failed} failed, ${r.expired} expired, ${r.still_pending} still waiting.`;
    });
    if (text) setMessage({ text });
    await reload();
  }

  const due = data?.schedule.filter((row) => row.status !== "paid" && row.status !== "upcoming") ?? [];

  return (
    <>
      <div className="hero">
        <h1>Contributions</h1>
        {viewsAll && (
          <div className="segmented" role="tablist">
            <button role="tab" aria-selected={scope === "mine"} onClick={() => setScope("mine")}>Mine</button>
            <button role="tab" aria-selected={scope === "all"} onClick={() => setScope("all")}>Everyone</button>
          </div>
        )}
      </div>
      <Notice message={message} onClose={clear} />

      <Card title="Pay with M-Pesa">
        <form className="inline-form" onSubmit={payByMpesa}>
          <Field label={`Amount (${c})`}>
            <input name="amount" type="number" min={1} step={1} required defaultValue={due[0] ? Math.ceil(Number(due[0].outstanding)) : undefined} />
          </Field>
          <button className="primary" disabled={busy}>
            <PhoneIcon /> Send prompt to my phone
          </button>
        </form>
        <p className="muted small">Your payment counts only after M-Pesa confirms it.</p>
      </Card>

      {officer && (
        <Card
          title="Record cash or a bank deposit"
          actions={
            <>
              <button className="ghost-dark" disabled={busy} onClick={() => void generate()}>
                <PlusIcon /> Generate schedules
              </button>
              <button className="ghost-dark" disabled={busy} onClick={() => void reconcile()}>
                <RefreshIcon /> Reconcile M-Pesa
              </button>
            </>
          }
        >
          <form className="inline-form" onSubmit={recordCash}>
            <Field label="Member">
              <select name="membership_id" required>
                {data?.members.filter((m) => m.status === "active").map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Amount (${c})`}>
              <input name="amount" type="number" min={1} step="0.01" required />
            </Field>
            <Field label="Method">
              <select name="method">
                <option value="cash">Cash</option>
                <option value="bank">Bank</option>
              </select>
            </Field>
            <Field label="Receipt or reference">
              <input name="reference" required maxLength={40} />
            </Field>
            <button className="primary" disabled={busy}>Record</button>
          </form>
        </Card>
      )}

      <Card title="Schedule">
        {data && data.schedule.length === 0 ? (
          <Empty>No schedule yet. A treasurer generates it from the chama's rules.</Empty>
        ) : (
          <Table headings={[...(scope === "all" ? ["Member"] : []), "Due", "Expected", "Paid", "Status", "Rule"]}>
            {data?.schedule.map((row) => (
              <tr key={row.id}>
                {scope === "all" && <td>{row.member}</td>}
                <td>{day(row.due_date)}</td>
                <td className="num">{money(row.expected, c)}</td>
                <td className="num">{money(row.paid, c)}</td>
                <td><Badge status={row.status} /></td>
                <td className="muted">v{row.rule_version}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card title="Money received">
        {data && data.contributions.length === 0 ? (
          <Empty>Nothing received yet.</Empty>
        ) : (
          <Table headings={[...(scope === "all" ? ["Member"] : []), "Date", "Amount", "Method", "Reference"]}>
            {data?.contributions.map((row) => (
              <tr key={row.id}>
                {scope === "all" && <td>{row.member}</td>}
                <td>{day(row.date)}</td>
                <td className="num gold-text">{money(row.amount, c)}</td>
                <td>{words(row.method)}</td>
                <td className="mono">{row.reference}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card title="M-Pesa requests">
        {data && data.payments.length === 0 ? (
          <Empty>No M-Pesa requests yet.</Empty>
        ) : (
          <Table headings={[...(scope === "all" ? ["Member"] : []), "Started", "Amount", "Status", "Receipt or reason"]}>
            {data?.payments.map((row) => (
              <tr key={row.id}>
                {scope === "all" && <td>{row.member}</td>}
                <td>{day(row.initiated_at)}</td>
                <td className="num">{money(row.amount, c)}</td>
                <td><Badge status={row.status} /></td>
                <td className="mono">{row.receipt ?? (row.failure_reason || "-")}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {prompt && (
        <div className="modal" role="dialog" aria-modal="true" aria-labelledby="prompt-title">
          <div className="modal-box">
            <h2 id="prompt-title"><PhoneIcon /> M-Pesa prompt (simulated)</h2>
            <p>
              Pay {money(prompt.amount, c)} to {chama.name}? On a real phone this is where you enter your PIN.
            </p>
            <div className="row end">
              <button className="ghost-dark" onClick={() => void answer(false)}>Cancel</button>
              <button className="primary" onClick={() => void answer(true)}>Enter PIN</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
