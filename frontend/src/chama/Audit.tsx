import { api } from "../api";
import { words } from "../format";
import { AuditEntry } from "../types";
import { Card, Table, useLoad } from "../ui";
import { useChama } from "./ChamaLayout";

export function Audit() {
  const { chama } = useChama();
  const { data, error } = useLoad(() => api<AuditEntry[]>(`/api/chamas/${chama.id}/audit-logs/`), [chama.id]);

  return (
    <>
      <h1>Audit log</h1>
      <p className="muted">Every important action, who did it and when. Entries cannot be changed or deleted.</p>
      {error && <p className="notice error">{error}</p>}
      <Card>
        <Table headings={["When", "Who", "What", "Details"]}>
          {data?.map((entry) => (
            <tr key={entry.id}>
              <td>{new Date(entry.created_at).toLocaleString("en-KE")}</td>
              <td>{entry.actor}</td>
              <td>{words(entry.action.replace(".", " "))}</td>
              <td className="wrap muted">
                {Object.entries(entry.details)
                  .map(([key, value]) => `${words(key)}: ${value}`)
                  .join(", ")}
              </td>
            </tr>
          ))}
        </Table>
      </Card>
    </>
  );
}
