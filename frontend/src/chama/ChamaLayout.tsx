import { NavLink, Outlet, useOutletContext, useParams } from "react-router-dom";

import { api } from "../api";
import { can } from "../format";
import { CogIcon, CoinsIcon, FileIcon, HomeIcon, ScaleIcon, ShieldIcon, UsersIcon } from "../icons";
import { ChamaDetail } from "../types";
import { useLoad } from "../ui";

export interface ChamaContext {
  chama: ChamaDetail;
  reloadChama: () => Promise<void>;
}

export function useChama(): ChamaContext {
  return useOutletContext<ChamaContext>();
}

export function ChamaLayout() {
  const { chamaId } = useParams();
  const { data: chama, error, reload } = useLoad(() => api<ChamaDetail>(`/api/chamas/${chamaId}/`), [chamaId]);

  if (error) return <main className="container"><p className="notice error">{error}</p></main>;
  if (!chama) return <p className="loading">Loading</p>;

  const links = [
    { to: "", label: "Overview", icon: <HomeIcon />, show: true },
    { to: "contributions", label: "Contributions", icon: <CoinsIcon />, show: true },
    { to: "members", label: "Members", icon: <UsersIcon />, show: true },
    { to: "rules", label: "Rules", icon: <ScaleIcon />, show: true },
    { to: "statements", label: "Statements", icon: <FileIcon />, show: true },
    { to: "audit", label: "Audit log", icon: <ShieldIcon />, show: can(chama.my_permissions, "view_audit") },
    { to: "settings", label: "Settings", icon: <CogIcon />, show: can(chama.my_permissions, "manage_chama") },
  ];

  return (
    <div className="chama">
      <nav className="sidenav" aria-label={`${chama.name} sections`}>
        <div className="sidenav-head">
          <strong>{chama.name}</strong>
          <span>{chama.my_role}</span>
        </div>
        {links
          .filter((link) => link.show)
          .map((link) => (
            <NavLink key={link.label} to={link.to} end={link.to === ""}>
              {link.icon}
              <span>{link.label}</span>
            </NavLink>
          ))}
      </nav>
      <main className="chama-main">
        <Outlet context={{ chama, reloadChama: reload } satisfies ChamaContext} />
      </main>
    </div>
  );
}
