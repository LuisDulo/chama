import { ReactNode, useEffect, useRef, useState } from "react";
import { Link, useMatch, useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { ChevronIcon, Logo, LogoutIcon, PlusIcon, SearchIcon } from "../icons";
import { MyChama } from "../types";

/** The top bar on every signed-in page, with the chama switcher (FR-02). */
export function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const match = useMatch("/c/:chamaId/*");
  const [chamas, setChamas] = useState<MyChama[]>([]);
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<MyChama[]>("/api/chamas/").then(setChamas).catch(() => setChamas([]));
  }, [match?.params.chamaId]);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (menu.current && !menu.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  const current = chamas.find((c) => c.chama.id === match?.params.chamaId);

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <Logo />
          <span>CHAMA</span>
        </Link>
        <div className="switcher" ref={menu}>
          <button type="button" className="switch-button" aria-expanded={open} onClick={() => setOpen(!open)}>
            <span>{current ? current.chama.name : "My chamas"}</span>
            <ChevronIcon />
          </button>
          {open && (
            <div className="switch-menu" role="menu">
              {chamas.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="menuitem"
                  className={item.chama.id === current?.chama.id ? "current" : ""}
                  onClick={() => {
                    setOpen(false);
                    navigate(`/c/${item.chama.id}`);
                  }}
                >
                  <strong>{item.chama.name}</strong>
                  <small>{item.role}</small>
                </button>
              ))}
              <hr />
              <button type="button" role="menuitem" onClick={() => { setOpen(false); navigate("/new"); }}>
                <PlusIcon /> Create a chama
              </button>
              <button type="button" role="menuitem" onClick={() => { setOpen(false); navigate("/discover"); }}>
                <SearchIcon /> Find a chama to join
              </button>
            </div>
          )}
        </div>
        <span className="who">{user?.first_name}</span>
        <button type="button" className="ghost" onClick={() => logout().then(() => navigate("/login"))}>
          <LogoutIcon /> <span className="hide-small">Log out</span>
        </button>
      </header>
      <div className="page">{children}</div>
    </div>
  );
}
