import { useState } from "react";

import { api, post } from "../api";
import { can, day, words } from "../format";
import { MailIcon } from "../icons";
import { Member, Role } from "../types";
import { Badge, Card, Field, formData, Notice, Table, useAction, useLoad } from "../ui";
import { useChama } from "./ChamaLayout";

const ACTIONS: Record<string, string[]> = {
  pending: ["approve", "reject"],
  active: ["suspend", "remove"],
  suspended: ["reinstate", "remove"],
};

export function Members() {
  const { chama } = useChama();
  const manages = can(chama.my_permissions, "manage_members");
  const managesRoles = can(chama.my_permissions, "manage_roles");
  const [link, setLink] = useState<string | null>(null);
  const { message, clear, busy, run } = useAction();
  const base = `/api/chamas/${chama.id}`;

  const { data, reload } = useLoad(async () => {
    const [members, roles] = await Promise.all([api<Member[]>(`${base}/members/`), api<Role[]>(`${base}/roles/`)]);
    return { members, roles };
  }, [chama.id]);

  async function act(member: Member, action: string) {
    if (await run(() => post(`${base}/members/${member.id}/${action}/`), `${member.name}: ${action} done.`)) await reload();
  }

  async function changeRole(member: Member, roleId: string) {
    if (await run(() => post(`${base}/members/${member.id}/role/`, { role_id: Number(roleId) }), `${member.name} is now ${data?.roles.find((r) => r.id === Number(roleId))?.role_name}.`)) await reload();
  }

  async function invite(event: React.FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    const values = formData(event);
    const body: Record<string, unknown> = {};
    if (values.contact.includes("@")) body.email = values.contact;
    else body.phone_number = values.contact;
    if (values.role_id) body.role_id = Number(values.role_id);
    let token = "";
    const ok = await run(async () => {
      token = (await post<{ token: string }>(`${base}/invite/`, body)).token;
    }, "Invitation created.");
    if (ok) {
      setLink(`${window.location.origin}/invitations/${token}`);
      form.reset();
    }
  }

  const isMe = (member: Member) => member.is_me;

  return (
    <>
      <h1>Members</h1>
      <Notice message={message} onClose={clear} />

      {manages && (
        <Card title="Invite someone">
          <form className="inline-form" onSubmit={invite}>
            <Field label="Email or phone number">
              <input name="contact" required />
            </Field>
            <Field label="Role">
              <select name="role_id" defaultValue="">
                <option value="">Member</option>
                {data?.roles.filter((r) => r.role_name !== "Member").map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.role_name}
                  </option>
                ))}
              </select>
            </Field>
            <button className="primary" disabled={busy}>
              <MailIcon /> Invite
            </button>
          </form>
          {link && (
            <p className="share">
              Share this link with them. It works once, for 7 days, and only for that person:
              <input readOnly value={link} onFocus={(e) => e.currentTarget.select()} aria-label="Invitation link" />
            </p>
          )}
        </Card>
      )}

      <Card title={`${data?.members.filter((m) => m.status === "active").length ?? 0} of ${chama.maximum_members} places taken`}>
        <Table headings={["Name", ...(manages ? ["Phone"] : []), "Role", "Status", "Joined", ...(manages ? [""] : [])]}>
          {data?.members.map((member) => (
            <tr key={member.id}>
              <td>{member.name}</td>
              {manages && <td className="mono">{member.phone_number}</td>}
              <td>
                {managesRoles && member.status === "active" && !isMe(member) ? (
                  <select aria-label={`Role for ${member.name}`} value={member.role_id} disabled={busy} onChange={(e) => void changeRole(member, e.target.value)}>
                    {data.roles.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.role_name}
                      </option>
                    ))}
                  </select>
                ) : (
                  member.role
                )}
              </td>
              <td><Badge status={member.status} /></td>
              <td>{day(member.joined_at)}</td>
              {manages && (
                <td>
                  <div className="row">
                    {!isMe(member) &&
                      (ACTIONS[member.status] ?? []).map((action) => (
                        <button key={action} className={action === "approve" || action === "reinstate" ? "small primary" : "small ghost-dark"} disabled={busy} onClick={() => void act(member, action)}>
                          {words(action)}
                        </button>
                      ))}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </Table>
      </Card>

      <Card title="Roles and permissions">
        <Table headings={["Role", "Can do"]}>
          {data?.roles.map((role) => (
            <tr key={role.id}>
              <td><strong>{role.role_name}</strong></td>
              <td className="wrap">{role.permissions.length ? role.permissions.map(words).join(", ") : "Contribute and view their own records"}</td>
            </tr>
          ))}
        </Table>
      </Card>
    </>
  );
}
