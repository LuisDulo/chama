import { useState } from "react";

import { api, post } from "../api";
import { can, day, describeContributions, words } from "../format";
import { CheckIcon, CloseIcon, ScaleIcon } from "../icons";
import { RuleState, RuleVersion } from "../types";
import { Badge, Card, Field, formData, Notice, Table, useAction, useLoad } from "../ui";
import { useChama } from "./ChamaLayout";

function summary(version: RuleVersion, currency: string) {
  if (version.category === "contributions") return describeContributions(version.configuration, currency);
  return Object.entries(version.configuration)
    .map(([key, value]) => `${words(key)}: ${typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}`)
    .join(", ");
}

function tomorrow() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return date.toISOString().slice(0, 10);
}

export function Rules() {
  const { chama } = useChama();
  const proposes = can(chama.my_permissions, "propose_rules");
  const approves = can(chama.my_permissions, "approve_rules");
  const [editing, setEditing] = useState(false);
  const { message, clear, busy, run } = useAction();
  const base = `/api/chamas/${chama.id}/rules`;

  const { data, reload } = useLoad(async () => {
    const [rules, history] = await Promise.all([api<RuleState[]>(`${base}/`), api<RuleVersion[]>(`${base}/history/`)]);
    return { rules, history };
  }, [chama.id]);

  const contributions = data?.rules.find((r) => r.category === "contributions");
  const current = contributions?.current?.configuration;

  async function propose(event: React.FormEvent<HTMLFormElement>) {
    const v = formData(event);
    const configuration = {
      amount_type: v.amount_type,
      minimum_amount: v.minimum_amount,
      maximum_amount: v.amount_type === "fixed" ? v.minimum_amount : v.maximum_amount,
      frequency: v.frequency,
      ...(v.frequency === "monthly" ? { due_day: Number(v.due_day) } : { due_weekday: v.due_weekday }),
      grace_period_days: Number(v.grace_period_days),
      late_penalty: v.late_penalty,
    };
    const ok = await run(
      () => post(`${base}/`, { category: "contributions", configuration, effective_from: v.effective_from, reason: v.reason }),
      "Change proposed. Another officer needs to approve it.",
    );
    if (ok) {
      setEditing(false);
      await reload();
    }
  }

  async function decide(version: RuleVersion, decision: "approve" | "reject") {
    if (await run(() => post(`${base}/${version.id}/${decision}/`), decision === "approve" ? `Approved. It applies from ${day(version.effective_from)}.` : "Change rejected.")) await reload();
  }

  return (
    <>
      <div className="hero">
        <h1>Rules and constitution</h1>
        {proposes && !editing && (
          <button className="primary" onClick={() => setEditing(true)}>
            <ScaleIcon /> Propose a change
          </button>
        )}
      </div>
      <Notice message={message} onClose={clear} />
      <p className="muted">Changes never rewrite the past. Each one starts on its own date, and earlier contributions keep the rule that applied to them.</p>

      {editing && current && (
        <Card title="Propose new contribution rules">
          <form className="stack" onSubmit={propose}>
            <div className="row-3">
              <Field label="Amount">
                <select name="amount_type" defaultValue={String(current.amount_type)}>
                  <option value="fixed">Fixed</option>
                  <option value="flexible">A range</option>
                </select>
              </Field>
              <Field label="Minimum (KES)">
                <input name="minimum_amount" type="number" min={1} defaultValue={String(current.minimum_amount)} required />
              </Field>
              <Field label="Maximum (KES)" hint="Ignored when fixed">
                <input name="maximum_amount" type="number" min={1} defaultValue={String(current.maximum_amount)} required />
              </Field>
            </div>
            <div className="row-3">
              <Field label="How often">
                <select name="frequency" defaultValue={String(current.frequency)}>
                  <option value="monthly">Monthly</option>
                  <option value="weekly">Weekly</option>
                </select>
              </Field>
              <Field label="Due day (monthly)">
                <input name="due_day" type="number" min={1} max={28} defaultValue={String(current.due_day ?? 5)} />
              </Field>
              <Field label="Due weekday (weekly)">
                <select name="due_weekday" defaultValue={String(current.due_weekday ?? "friday")}>
                  {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((d) => (
                    <option key={d} value={d}>{words(d)}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="row-3">
              <Field label="Grace days">
                <input name="grace_period_days" type="number" min={0} max={60} defaultValue={String(current.grace_period_days)} required />
              </Field>
              <Field label="Late penalty (KES)">
                <input name="late_penalty" type="number" min={0} defaultValue={String(current.late_penalty)} required />
              </Field>
              <Field label="Starts on">
                <input name="effective_from" type="date" min={tomorrow()} defaultValue={tomorrow()} required />
              </Field>
            </div>
            <Field label="Reason">
              <input name="reason" maxLength={300} placeholder="Why the change is needed" />
            </Field>
            <div className="row end">
              <button type="button" className="ghost-dark" onClick={() => setEditing(false)}>Cancel</button>
              <button className="primary" disabled={busy}>Propose</button>
            </div>
          </form>
        </Card>
      )}

      {data?.rules.map((rule) => (
        <Card key={rule.category} title={words(rule.category)}>
          {rule.current && (
            <p>
              <span className="chip">In force, v{rule.current.version_number}</span> {summary(rule.current, chama.currency)}
            </p>
          )}
          {rule.upcoming && (
            <p>
              <span className="chip gold">From {day(rule.upcoming.effective_from)}, v{rule.upcoming.version_number}</span> {summary(rule.upcoming, chama.currency)}
            </p>
          )}
          {rule.pending && (
            <div className="pending">
              <p>
                <span className="chip wait">Waiting for approval, v{rule.pending.version_number}</span> {summary(rule.pending, chama.currency)}
              </p>
              <p className="muted small">
                Proposed by {rule.pending.proposed_by} to start {day(rule.pending.effective_from)}. {rule.pending.reason}
              </p>
              {approves && (
                <div className="row">
                  <button className="small primary" disabled={busy} onClick={() => void decide(rule.pending!, "approve")}><CheckIcon /> Approve</button>
                  <button className="small ghost-dark" disabled={busy} onClick={() => void decide(rule.pending!, "reject")}><CloseIcon /> Reject</button>
                </div>
              )}
            </div>
          )}
        </Card>
      ))}

      <Card title="History">
        <Table headings={["Rule", "Version", "Status", "Starts", "Proposed by", "Decided by"]}>
          {data?.history.map((version) => (
            <tr key={version.id}>
              <td>{words(version.category)}</td>
              <td>v{version.version_number}</td>
              <td><Badge status={version.status} /></td>
              <td>{day(version.effective_from)}</td>
              <td>{version.proposed_by}</td>
              <td>{version.decided_by ?? "-"}</td>
            </tr>
          ))}
        </Table>
      </Card>
    </>
  );
}
