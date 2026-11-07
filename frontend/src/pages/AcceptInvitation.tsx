import { useNavigate, useParams } from "react-router-dom";

import { post } from "../api";
import { MailIcon } from "../icons";
import { Card, Notice, useAction } from "../ui";

export function AcceptInvitation() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { message, clear, busy, run } = useAction();

  async function accept() {
    let chamaId = "";
    const ok = await run(async () => {
      chamaId = (await post<{ chama_id: string }>("/api/invitations/accept/", { token })).chama_id;
    });
    if (ok) navigate(`/c/${chamaId}`);
  }

  return (
    <main className="container narrow">
      <Card title="You have been invited">
        <Notice message={message} onClose={clear} />
        <p>Accepting adds this chama to your account. You can belong to several chamas at once.</p>
        <button className="primary" disabled={busy} onClick={() => void accept()}>
          <MailIcon /> Accept invitation
        </button>
      </Card>
    </main>
  );
}
