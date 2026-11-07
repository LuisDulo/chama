import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { post } from "../api";
import { describeContributions } from "../format";
import { Card, Field, Notice, useAction } from "../ui";

const STEPS = ["About", "Membership", "Contributions", "Review"];

const START = {
  name: "",
  description: "",
  category: "savings",
  location: "",
  currency: "KES",
  visibility: "private",
  membership_type: "invitation",
  requires_approval: true,
  maximum_members: 30,
  amount_type: "fixed",
  minimum_amount: "1000",
  maximum_amount: "1000",
  frequency: "monthly",
  due_day: 5,
  due_weekday: "friday",
  grace_period_days: 3,
  late_penalty: "100",
};

/** The creation wizard (FR-03). Financial settings become the chama's first rule version. */
export function CreateChama() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(START);
  const { message, clear, busy, run } = useAction();

  const set = (name: keyof typeof START) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const target = event.target as HTMLInputElement;
    const value = target.type === "checkbox" ? target.checked : target.value;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const contributions = {
    amount_type: form.amount_type,
    minimum_amount: form.minimum_amount,
    maximum_amount: form.amount_type === "fixed" ? form.minimum_amount : form.maximum_amount,
    frequency: form.frequency,
    ...(form.frequency === "monthly" ? { due_day: Number(form.due_day) } : { due_weekday: form.due_weekday }),
    grace_period_days: Number(form.grace_period_days),
    late_penalty: form.late_penalty,
  };

  async function create() {
    let id = "";
    const ok = await run(async () => {
      const chama = await post<{ id: string }>("/api/chamas/", {
        name: form.name,
        description: form.description,
        category: form.category,
        location: form.location,
        currency: form.currency,
        visibility: form.visibility,
        membership_type: form.membership_type,
        requires_approval: form.requires_approval,
        maximum_members: Number(form.maximum_members),
        rules: { contributions },
      });
      id = chama.id;
    });
    if (ok) navigate(`/c/${id}`);
  }

  function next(event: React.FormEvent) {
    event.preventDefault();
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }

  return (
    <main className="container narrow">
      <h1>Create a chama</h1>
      <ol className="steps">
        {STEPS.map((name, index) => (
          <li key={name} className={index === step ? "current" : index < step ? "done" : ""}>
            {name}
          </li>
        ))}
      </ol>
      <Notice message={message} onClose={clear} />
      <Card>
        <form className="stack" onSubmit={step === STEPS.length - 1 ? (e) => { e.preventDefault(); void create(); } : next}>
          {step === 0 && (
            <>
              <Field label="Name">
                <input value={form.name} onChange={set("name")} required maxLength={120} />
              </Field>
              <Field label="Description">
                <textarea value={form.description} onChange={set("description")} rows={3} />
              </Field>
              <div className="row-2">
                <Field label="Type">
                  <select value={form.category} onChange={set("category")}>
                    <option value="savings">Savings group</option>
                    <option value="investment">Investment club</option>
                    <option value="merry_go_round">Merry-go-round</option>
                    <option value="welfare">Welfare group</option>
                    <option value="other">Other</option>
                  </select>
                </Field>
                <Field label="Location">
                  <input value={form.location} onChange={set("location")} maxLength={120} />
                </Field>
              </div>
            </>
          )}
          {step === 1 && (
            <>
              <div className="row-2">
                <Field label="Who can see it">
                  <select value={form.visibility} onChange={set("visibility")}>
                    <option value="private">Private</option>
                    <option value="public">Public</option>
                  </select>
                </Field>
                <Field label="How people join">
                  <select value={form.membership_type} onChange={set("membership_type")}>
                    <option value="invitation">By invitation</option>
                    <option value="open">Anyone can ask</option>
                  </select>
                </Field>
              </div>
              <Field label="Most members">
                <input type="number" min={2} max={1000} value={form.maximum_members} onChange={set("maximum_members")} required />
              </Field>
              <label className="check">
                <input type="checkbox" checked={form.requires_approval} onChange={set("requires_approval")} />
                New members need approval
              </label>
            </>
          )}
          {step === 2 && (
            <>
              <div className="row-2">
                <Field label="Amount">
                  <select value={form.amount_type} onChange={set("amount_type")}>
                    <option value="fixed">The same for everyone</option>
                    <option value="flexible">A range</option>
                  </select>
                </Field>
                <Field label="How often">
                  <select value={form.frequency} onChange={set("frequency")}>
                    <option value="monthly">Monthly</option>
                    <option value="weekly">Weekly</option>
                  </select>
                </Field>
              </div>
              <div className="row-2">
                <Field label={form.amount_type === "fixed" ? "Contribution (KES)" : "Minimum (KES)"}>
                  <input type="number" min={1} value={form.minimum_amount} onChange={set("minimum_amount")} required />
                </Field>
                {form.amount_type === "flexible" && (
                  <Field label="Maximum (KES)">
                    <input type="number" min={1} value={form.maximum_amount} onChange={set("maximum_amount")} required />
                  </Field>
                )}
              </div>
              <div className="row-2">
                {form.frequency === "monthly" ? (
                  <Field label="Due on day of the month">
                    <input type="number" min={1} max={28} value={form.due_day} onChange={set("due_day")} required />
                  </Field>
                ) : (
                  <Field label="Due every">
                    <select value={form.due_weekday} onChange={set("due_weekday")}>
                      {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((d) => (
                        <option key={d} value={d}>
                          {d.charAt(0).toUpperCase() + d.slice(1)}
                        </option>
                      ))}
                    </select>
                  </Field>
                )}
                <Field label="Grace period (days)">
                  <input type="number" min={0} max={60} value={form.grace_period_days} onChange={set("grace_period_days")} required />
                </Field>
              </div>
              <Field label="Late penalty (KES)">
                <input type="number" min={0} value={form.late_penalty} onChange={set("late_penalty")} required />
              </Field>
            </>
          )}
          {step === 3 && (
            <div className="review">
              <h2>{form.name || "Unnamed chama"}</h2>
              <p>{form.description}</p>
              <p>
                <strong>Membership:</strong> {form.visibility}, {form.membership_type === "open" ? "anyone can ask" : "by invitation"}, up to{" "}
                {form.maximum_members} members{form.requires_approval ? ", with approval" : ""}.
              </p>
              <p>
                <strong>Contributions:</strong> {describeContributions(contributions, form.currency)}.
              </p>
              <p className="muted">You become the Chairperson. Every rule can be changed later through a proposal and approval.</p>
            </div>
          )}
          <div className="row end">
            {step > 0 && (
              <button type="button" className="ghost-dark" onClick={() => setStep(step - 1)}>
                Back
              </button>
            )}
            <button className="primary" disabled={busy}>
              {step === STEPS.length - 1 ? "Create chama" : "Continue"}
            </button>
          </div>
        </form>
      </Card>
    </main>
  );
}
