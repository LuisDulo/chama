import { Link } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { words } from "../format";
import { PlusIcon, SearchIcon } from "../icons";
import { MyChama } from "../types";
import { Empty, useLoad } from "../ui";

export function Home() {
  const { user } = useAuth();
  const { data: chamas, error } = useLoad(() => api<MyChama[]>("/api/chamas/"), []);

  return (
    <main className="container">
      <div className="hero">
        <div>
          <p className="eyebrow">Karibu, {user?.first_name}</p>
          <h1>Your chamas</h1>
        </div>
        <div className="row">
          <Link className="button ghost-dark" to="/discover">
            <SearchIcon /> Find a chama
          </Link>
          <Link className="button primary" to="/new">
            <PlusIcon /> Create a chama
          </Link>
        </div>
      </div>
      {error && <p className="notice error">{error}</p>}
      {chamas && chamas.length === 0 && (
        <Empty>You are not in any chama yet. Create one, or accept an invitation from a group you know.</Empty>
      )}
      <div className="chama-grid">
        {chamas?.map((item) => (
          <Link key={item.id} to={`/c/${item.chama.id}`} className="chama-card">
            <span className="chip">{words(item.chama.category)}</span>
            <h2>{item.chama.name}</h2>
            <p>{item.chama.description || "No description yet."}</p>
            <footer>
              <span>{item.role}</span>
              <span>{item.chama.currency}</span>
            </footer>
          </Link>
        ))}
      </div>
    </main>
  );
}
