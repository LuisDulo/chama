import { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth";
import { Audit } from "./chama/Audit";
import { ChamaLayout } from "./chama/ChamaLayout";
import { Contributions } from "./chama/Contributions";
import { Members } from "./chama/Members";
import { OverviewPage } from "./chama/Overview";
import { Rules } from "./chama/Rules";
import { Settings } from "./chama/Settings";
import { Statements } from "./chama/Statements";
import { AcceptInvitation } from "./pages/AcceptInvitation";
import { CreateChama } from "./pages/CreateChama";
import { Discover } from "./pages/Discover";
import { Home } from "./pages/Home";
import { Login, Register } from "./pages/Login";
import { Shell } from "./pages/Shell";

function Private({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <p className="loading">Loading</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <Shell>{children}</Shell>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={<Private><Home /></Private>} />
      <Route path="/new" element={<Private><CreateChama /></Private>} />
      <Route path="/discover" element={<Private><Discover /></Private>} />
      <Route path="/invitations/:token" element={<Private><AcceptInvitation /></Private>} />
      <Route path="/c/:chamaId" element={<Private><ChamaLayout /></Private>}>
        <Route index element={<OverviewPage />} />
        <Route path="contributions" element={<Contributions />} />
        <Route path="members" element={<Members />} />
        <Route path="rules" element={<Rules />} />
        <Route path="statements" element={<Statements />} />
        <Route path="audit" element={<Audit />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
