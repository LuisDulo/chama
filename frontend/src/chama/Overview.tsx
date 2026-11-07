import { Link } from "react-router-dom";

import { api } from "../api";
import { day, money, words } from "../format";
import { CoinsIcon } from "../icons";
import { Overview } from "../types";
import { Card, Stat, Table, useLoad } from "../ui";
import { useChama } from "./ChamaLayout";

export function OverviewPage() {
  const { chama } = useChama();
  const { data } = useLoad(() => api<Overview>(`/api/chamas/${chama.id}/reports/overview/`), [chama.id]);
  if (!data) return <p className="loading">Loading</p>;
  const c = data.currency;

  return (
    <>
      <div className="hero">
        <div>
          <p className="eyebrow">{words(chama.category)}</p>
          <h1>{chama.name}</h1>
        </div>
        <Link className="button primary" to="contributions">
          <CoinsIcon /> Contribute
        </Link>
      </div>
      <div className="stats">
        <Stat label="My savings" value={money(data.my_savings, c)} tone="gold" />
        <Stat label="Owed now" value={money(data.my_outstanding, c)} tone={Number(data.my_outstanding) > 0 ? "alert" : undefined} />
        <Stat label="Next due" value={data.next_due ? `${money(data.next_due.amount, c)} on ${day(data.next_due.date)}` : "Nothing due"} />
      </div>
      {data.my_overdue_periods > 0 && (
        <p className="notice error">
          You have {data.my_overdue_periods} overdue contribution{data.my_overdue_periods === 1 ? "" : "s"}.
        </p>
      )}
      {data.group && (
        <Card title="Group books">
          <div className="stats">
            <Stat label="Active members" value={String(data.group.members)} />
            <Stat label="Members overdue" value={String(data.group.members_overdue)} tone={data.group.members_overdue ? "alert" : undefined} />
          </div>
          <Table headings={["Account", "Type", "Balance"]}>
            {data.group.accounts.map((account) => (
              <tr key={account.code}>
                <td>{account.name}</td>
                <td>{words(account.type)}</td>
                <td className="num">{money(account.balance, c)}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </>
  );
}
