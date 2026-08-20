"use client";

// Privacy section.
//
// The privacy boundary is the project's central claim, and it used to live at
// the bottom of a run card where a juror had to scroll past the whole
// deliberation to reach it. Here it is a section of its own, reading off A7's
// own measured report rather than a fixed list — so the numbers move when the
// redactor does, and a rule that stops matching shows up as a smaller count.

import { useMemo } from "react";
import { useAgents } from "../../_lib/AgentSocketProvider";
import ConsoleNav from "../ConsoleNav";
import "../admin.css";
import "./privacy.css";

export default function PrivacySection() {
  const { orderedRuns, connected, eventCount } = useAgents();

  const withPrivacy = useMemo(
    () => orderedRuns.filter((r) => r.privacy),
    [orderedRuns],
  );

  const totals = useMemo(() => {
    const byField: Record<string, number> = {};
    let redacted = 0;
    let reveals = 0;
    for (const r of orderedRuns) {
      redacted += r.privacy?.fieldsRedacted ?? 0;
      reveals += r.reveals?.length ?? 0;
      for (const [k, v] of Object.entries(r.privacy?.byField ?? {})) {
        byField[k] = (byField[k] ?? 0) + v;
      }
    }
    return { byField, redacted, reveals };
  }, [orderedRuns]);

  const latest = withPrivacy[0];
  const ranked = Object.entries(totals.byField).sort((a, b) => b[1] - a[1]);

  return (
    <div className="admin">
      <ConsoleNav connected={connected} eventCount={eventCount} />

      <section className="sectionIntro">
        <h1 className="controlTitle">What was hidden, and from whom</h1>
        <p className="controlHint">
          Every outbound payload passes through a deterministic field policy
          before anyone sees it. Nothing here is a fixed list — these are the
          fields the redactor actually removed on the runs below.
        </p>
      </section>

      {withPrivacy.length === 0 ? (
        <div className="empty">
          <h2>Nothing redacted yet</h2>
          <p>
            Send a request from the <strong>Deliberation</strong> section. The
            redactor reports what it removed as soon as a run reaches it.
          </p>
        </div>
      ) : (
        <>
          <div className="privStats">
            <div className="privStat">
              <span className="privStatK">{totals.redacted.toLocaleString()}</span>
              <span className="privStatL">field instances redacted</span>
            </div>
            <div className="privStat">
              <span className="privStatK">{withPrivacy.length}</span>
              <span className="privStatL">
                {withPrivacy.length === 1 ? "run" : "runs"} passed through the
                policy
              </span>
            </div>
            <div className="privStat">
              <span className="privStatK">{totals.reveals}</span>
              <span className="privStatL">
                reveals — only after a helper accepted
              </span>
            </div>
          </div>

          {latest?.privacy && (
            <section className="privBoard" aria-label="Audience boundary">
              <div className="privCol">
                <span className="pLabel shared">Shared</span>
                <ul className="privList">
                  {latest.privacy.shared.map((f) => <li key={f}>{f}</li>)}
                </ul>
              </div>
              <div className="privCol">
                <span className="pLabel masked">Masked</span>
                <ul className="privList">
                  {latest.privacy.masked.map((f) => <li key={f}>{f}</li>)}
                </ul>
                <p className="privNote">Reduced, not removed — an area, not a point.</p>
              </div>
              <div className="privCol">
                <span className="pLabel held">Withheld</span>
                <ul className="privList">
                  {latest.privacy.withheld.map((f) => <li key={f}>{f}</li>)}
                </ul>
                <p className="privNote">
                  Never sent to a helper before they accept.
                </p>
              </div>
            </section>
          )}

          {ranked.length > 0 && (
            <section aria-label="Most redacted fields">
              <h2 className="sectionTitle">What the redactor removed most</h2>
              <ul className="privBars">
                {ranked.slice(0, 8).map(([field, n]) => (
                  <li key={field} className="privBar">
                    <span className="privBarL">{field.replace(/_/g, " ")}</span>
                    <span className="privBarTrack" aria-hidden="true">
                      <span
                        className="privBarFill"
                        style={{ width: `${(n / ranked[0][1]) * 100}%` }}
                      />
                    </span>
                    <span className="privBarN">{n}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {latest?.privacy?.orgBlockedTypes?.length ? (
            <section aria-label="Withheld from organizations">
              <h2 className="sectionTitle">
                Organizations additionally never receive
              </h2>
              <ul className="privChips">
                {latest.privacy.orgBlockedTypes.map((t) => (
                  <li key={t} className="privChip">{t}</li>
                ))}
              </ul>
              <p className="privNote privNoteWide">
                An organization sees its own allocation and the reason for it —
                never the cross-organization deliberation that produced it, and
                never a rival&rsquo;s stock.
              </p>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
