import { patch } from "../api";
import { Card, Field, formData, Notice, useAction } from "../ui";
import { useChama } from "./ChamaLayout";

export function Settings() {
  const { chama, reloadChama } = useChama();
  const { message, clear, busy, run } = useAction();

  async function save(event: React.FormEvent<HTMLFormElement>) {
    const values = formData(event);
    const ok = await run(
      () =>
        patch(`/api/chamas/${chama.id}/`, {
          ...values,
          maximum_members: Number(values.maximum_members),
          requires_approval: values.requires_approval === "on",
        }),
      "Settings saved.",
    );
    if (ok) await reloadChama();
  }

  return (
    <>
      <h1>Settings</h1>
      <Notice message={message} onClose={clear} />
      <Card title="About this chama">
        <form className="stack" onSubmit={save}>
          <Field label="Name">
            <input name="name" defaultValue={chama.name} required maxLength={120} />
          </Field>
          <Field label="Description">
            <textarea name="description" defaultValue={chama.description} rows={3} />
          </Field>
          <div className="row-3">
            <Field label="Visibility">
              <select name="visibility" defaultValue={chama.visibility}>
                <option value="private">Private</option>
                <option value="public">Public</option>
              </select>
            </Field>
            <Field label="Joining">
              <select name="membership_type" defaultValue={chama.membership_type}>
                <option value="invitation">By invitation</option>
                <option value="open">Anyone can ask</option>
              </select>
            </Field>
            <Field label="Most members">
              <input name="maximum_members" type="number" min={2} max={1000} defaultValue={chama.maximum_members} required />
            </Field>
          </div>
          <label className="check">
            <input name="requires_approval" type="checkbox" defaultChecked={chama.requires_approval} /> New members need approval
          </label>
          <div className="row end">
            <button className="primary" disabled={busy}>Save</button>
          </div>
        </form>
      </Card>
    </>
  );
}
