import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { post } from "../api";
import { useAuth } from "../auth";
import { Logo } from "../icons";
import { Field, formData, Notice, useAction } from "../ui";

function AuthFrame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="auth">
      <aside className="auth-brand">
        <Logo size={44} />
        <h1>Run your chama with confidence.</h1>
        <p>Contributions, rules and statements in one place, for every group you belong to.</p>
      </aside>
      <section className="auth-panel">
        <h2>{title}</h2>
        {children}
      </section>
    </main>
  );
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { message, clear, busy, run } = useAction();

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    const { login: name, password } = formData(event);
    if (await run(() => login(name, password))) {
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    }
  }

  return (
    <AuthFrame title="Log in">
      <Notice message={message} onClose={clear} />
      <form className="stack" onSubmit={submit}>
        <Field label="Email or phone number">
          <input name="login" required autoComplete="username" />
        </Field>
        <Field label="Password">
          <input name="password" type="password" required autoComplete="current-password" />
        </Field>
        <button className="primary" disabled={busy}>
          Log in
        </button>
      </form>
      <p className="muted">
        New here? <Link to="/register">Create an account</Link>
      </p>
    </AuthFrame>
  );
}

export function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { message, clear, busy, run } = useAction();
  const [done, setDone] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    const values = formData(event);
    const ok = await run(async () => {
      await post("/api/auth/register/", values);
      await login(values.email, values.password);
    });
    if (ok) {
      setDone(true);
      navigate("/", { replace: true });
    }
  }

  return (
    <AuthFrame title="Create your account">
      <Notice message={message} onClose={clear} />
      <form className="stack" onSubmit={submit}>
        <div className="row-2">
          <Field label="First name">
            <input name="first_name" required maxLength={60} autoComplete="given-name" />
          </Field>
          <Field label="Last name">
            <input name="last_name" required maxLength={60} autoComplete="family-name" />
          </Field>
        </div>
        <Field label="Email">
          <input name="email" type="email" required autoComplete="email" />
        </Field>
        <Field label="Phone number" hint="Used for M-Pesa payments">
          <input name="phone_number" required inputMode="tel" placeholder="0712345678" autoComplete="tel" />
        </Field>
        <Field label="Password" hint="At least 8 characters, not a common password">
          <input name="password" type="password" required minLength={8} autoComplete="new-password" />
        </Field>
        <button className="primary" disabled={busy || done}>
          Create account
        </button>
      </form>
      <p className="muted">
        Already registered? <Link to="/login">Log in</Link>
      </p>
    </AuthFrame>
  );
}
