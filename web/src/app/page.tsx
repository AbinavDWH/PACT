import Link from "next/link";
import "./landing.css";

// The front door.
//
// This used to be `redirect("/admin")`, which dropped a first-time visitor
// straight into an operations console: a control panel labelled NEED /
// QUANTITY / LATITUDE / LONGITUDE, a "Codec console" holding a raw
// `Q|101|7F3K|...` string, and an otherwise empty screen. Everything on it was
// meaningful to someone who already knew the system and opaque to everyone
// else. The console is still one click away; it is no longer the first thing
// anyone sees.

export const metadata = {
  title: "PACT | Coordination that works when the network does not",
};

const STEPS = [
  {
    n: "01",
    title: "Someone asks for help",
    body:
      "They tap options in an app — no typing, no account beyond one screen. " +
      "Their selections compress to about 35 characters.",
  },
  {
    n: "02",
    title: "The message finds a way out",
    body:
      "With data, it posts over HTTP. Without data, the identical string goes " +
      "by SMS. One wire format, two transports.",
  },
  {
    n: "03",
    title: "Agents deliberate, in the open",
    body:
      "Triage assesses severity, a geospatial query finds nearby helpers, " +
      "advocates argue each candidate, and an arbiter picks between costed options.",
  },
  {
    n: "04",
    title: "A human decides",
    body:
      "Every allocation pauses for approval. Approve it, override it, or reject " +
      "it — and the reasoning is recorded either way.",
  },
];

const PROOF = [
  { k: "~35", u: "characters", d: "A full request, inside one SMS" },
  { k: "2", u: "transports", d: "Identical result over data or SMS" },
  { k: "0", u: "numbers from the model", d: "Every quantity is computed in code" },
  { k: "1 km", u: "until acceptance", d: "Exact position unlocks only on accept" },
];

export default function Home() {
  return (
    <main className="lp">
      <header className="lpNav">
        <span className="lpMark">
          PACT<span className="lpMarkDot" aria-hidden="true" />
        </span>
        <nav className="lpNavLinks" aria-label="Consoles">
          <Link href="/admin" className="lpNavLink">Admin console</Link>
          <Link href="/org" className="lpNavLink lpNavLinkStrong">Organization sign in</Link>
        </nav>
      </header>

      <section className="lpHero">
        <p className="lpEyebrow">
          <span className="lpPulse" aria-hidden="true" />
          Privacy-preserving humanitarian coordination
        </p>
        <h1 className="lpTitle">
          Coordination that still works
          <span className="lpTitleAccent"> when the network does not.</span>
        </h1>
        <p className="lpLede">
          In a disaster the people who need help have no way to ask, and the
          organizations who can help will not pool their data. PACT connects the
          two through autonomous agents that share only what an allocation
          actually requires — and keeps working over SMS when the internet is
          gone.
        </p>
        <div className="lpCtas">
          <Link href="/admin" className="lpBtn lpBtnPrimary">
            Watch the agents work
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" stroke="currentColor"
                    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
          <Link href="/org" className="lpBtn lpBtnGhost">I represent an organization</Link>
        </div>

        <dl className="lpProof">
          {PROOF.map((p) => (
            <div key={p.u} className="lpProofItem">
              <dt className="lpProofK">
                {p.k} <span className="lpProofU">{p.u}</span>
              </dt>
              <dd className="lpProofD">{p.d}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="lpSection" aria-labelledby="how">
        <h2 className="lpH2" id="how">How a request becomes help</h2>
        <ol className="lpSteps">
          {STEPS.map((s) => (
            <li key={s.n} className="lpStep">
              <span className="lpStepN" aria-hidden="true">{s.n}</span>
              <h3 className="lpStepT">{s.title}</h3>
              <p className="lpStepB">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="lpSection lpSplit" aria-labelledby="privacy">
        <div>
          <h2 className="lpH2" id="privacy">What is shared, and what is not</h2>
          <p className="lpBody">
            Coordination normally demands that everyone hand their data to a
            central authority. Nobody wants to, so it does not happen. PACT
            inverts that: each party discloses only what an allocation needs,
            and identity unlocks at the last possible moment.
          </p>
        </div>
        <div className="lpBoundary">
          <div className="lpBoundaryCol">
            <span className="lpTag lpTagShared">Shared</span>
            <ul className="lpList">
              <li>Resource type and approximate quantity</li>
              <li>An area, rounded to about a kilometre</li>
              <li>Urgency and response time</li>
              <li>Why the allocation was made</li>
            </ul>
          </div>
          <div className="lpBoundaryCol">
            <span className="lpTag lpTagHeld">Never shared</span>
            <ul className="lpList">
              <li>Names and phone numbers, until a helper accepts</li>
              <li>Exact coordinates, until a helper accepts</li>
              <li>Another organization&rsquo;s stock or assignments</li>
              <li>The cross-organization deliberation</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="lpSection lpDoors" aria-labelledby="enter">
        <h2 className="lpH2" id="enter">Two ways in</h2>
        <div className="lpDoorGrid">
          <Link href="/admin" className="lpDoor">
            <span className="lpDoorTag">Operator</span>
            <h3 className="lpDoorT">Admin console</h3>
            <p className="lpDoorB">
              Watch every agent deliberate in real time, see the database query
              that found each candidate, and approve or override any allocation
              before it commits.
            </p>
            <span className="lpDoorGo">Open the console →</span>
          </Link>
          <Link href="/org" className="lpDoor">
            <span className="lpDoorTag">NGO · CSR · Government</span>
            <h3 className="lpDoorT">Organization portal</h3>
            <p className="lpDoorB">
              See the allocations made to you and why, assign them to a named
              person on your roster, and share your group code with field staff.
              You see your own slice and nothing else.
            </p>
            <span className="lpDoorGo">Sign in →</span>
          </Link>
        </div>
      </section>

      <footer className="lpFoot">
        <span>PACT — Privacy-Preserving Multi-Agent Humanitarian Coordination</span>
      </footer>
    </main>
  );
}
