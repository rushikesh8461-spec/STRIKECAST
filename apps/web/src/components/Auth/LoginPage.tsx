import { ShieldCheck, Zap } from "lucide-react";

type Props = { onLogin: (label: string) => void };

export default function LoginPage({ onLogin }: Props) {
  return (
    <div className="login-shell">
      <div className="login-radar radar-a" />
      <div className="login-radar radar-b" />
      <div className="login-grid" />
      <div className="login-particles" />
      <div className="login-topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><Zap size={18} fill="currentColor" /></div>
          <div><div className="brand-name">STRIKECAST</div><div className="brand-subtitle">Atmospheric Risk Intelligence</div></div>
        </div>
        <div className="login-secure"><ShieldCheck size={14} /> LOCAL DEMO</div>
      </div>
      <main className="login-center">
        <section className="login-copy">
          <div className="login-eyebrow">AI WEATHER &amp; LIGHTNING SOFTWARE DEMO</div>
          <h1>Explore the<br /><span>command center.</span></h1>
          <p>View the existing M1–M6 interface. The bundled model and lightning fixtures are demo-only and do not provide validated operational forecasts.</p>
          <div className="login-metrics"><div><strong>M1–M6</strong><span>PIPELINE</span></div><div><strong>60 MIN</strong><span>DEMO HORIZON</span></div><div><strong>3D</strong><span>GEOSPATIAL</span></div></div>
        </section>
        <section className="login-card">
          <div className="login-card-head"><div className="login-card-icon"><Zap size={18} /></div><div><div className="section-kicker">DEMO ACCESS</div><h2>Open dashboard</h2></div></div>
          <p>This local-only entry screen does not authenticate users. Do not expose the demo deployment to untrusted networks.</p>
          <button className="login-submit" onClick={() => onLogin("Local demo")}>ENTER DEMO COMMAND CENTER <span>→</span></button>
          <div className="login-footer-note">Production access control requires a server-side identity provider and authorization checks.</div>
        </section>
      </main>
    </div>
  );
}
