import { download } from "../api";
import { can } from "../format";
import { DownloadIcon } from "../icons";
import { Card, Notice, useAction } from "../ui";
import { useChama } from "./ChamaLayout";

export function Statements() {
  const { chama } = useChama();
  const { message, clear, busy, run } = useAction();
  const base = `/api/chamas/${chama.id}/reports`;
  const slug = chama.name.toLowerCase().replace(/[^a-z0-9]+/g, "-");

  const get = (path: string, name: string, format: "pdf" | "xlsx") =>
    run(() => download(`${base}/${path}/?format=${format}`, `${slug}-${name}.${format}`));

  return (
    <>
      <h1>Statements</h1>
      <Notice message={message} onClose={clear} />
      <Card title="My statement">
        <p className="muted">Every confirmed payment with a running balance, and your contribution schedule.</p>
        <div className="row">
          <button className="primary" disabled={busy} onClick={() => void get("my-statement", "my-statement", "pdf")}><DownloadIcon /> PDF</button>
          <button className="ghost-dark" disabled={busy} onClick={() => void get("my-statement", "my-statement", "xlsx")}><DownloadIcon /> Excel</button>
        </div>
      </Card>
      {can(chama.my_permissions, "view_finances") && (
        <Card title="Group financial statement">
          <p className="muted">Account balances and every member's savings and arrears. Downloads are recorded in the audit log.</p>
          <div className="row">
            <button className="primary" disabled={busy} onClick={() => void get("financial-statements", "financial-statement", "pdf")}><DownloadIcon /> PDF</button>
            <button className="ghost-dark" disabled={busy} onClick={() => void get("financial-statements", "financial-statement", "xlsx")}><DownloadIcon /> Excel</button>
          </div>
        </Card>
      )}
    </>
  );
}
