import { api, post } from "../api";
import { words } from "../format";
import { Chama } from "../types";
import { Card, Empty, Notice, useAction, useLoad } from "../ui";

export function Discover() {
  const { data, reload } = useLoad(() => api<Chama[]>("/api/chamas/discover/"), []);
  const { message, setMessage, clear, busy, run } = useAction();

  async function join(chama: Chama) {
    let status = "";
    const ok = await run(async () => {
      status = (await post<{ status: string }>(`/api/chamas/${chama.id}/join/`)).status;
    });
    if (!ok) return;
    setMessage({
      text: status === "pending" ? `Request sent. ${chama.name} will review it.` : `You joined ${chama.name}.`,
    });
    await reload();
  }

  return (
    <main className="container narrow">
      <h1>Find a chama</h1>
      <p className="muted">Public chamas that anyone can ask to join.</p>
      <Notice message={message} onClose={clear} />
      {data && data.length === 0 && <Empty>No open chamas right now.</Empty>}
      {data?.map((chama) => (
        <Card
          key={chama.id}
          title={chama.name}
          actions={
            <button className="primary" disabled={busy} onClick={() => void join(chama)}>
              {chama.requires_approval ? "Ask to join" : "Join"}
            </button>
          }
        >
          <p>{chama.description}</p>
          <p className="muted">
            {words(chama.category)}
            {chama.location ? `, ${chama.location}` : ""}
          </p>
        </Card>
      ))}
    </main>
  );
}
