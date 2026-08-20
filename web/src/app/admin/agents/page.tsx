"use client";

// Agents section: what the pipeline actually is.
//
// The deliberation stream shows agents talking, but a juror watching it for
// forty seconds cannot tell how many there are, which of them is a model and
// which is arithmetic, or why that distinction is the whole argument. This
// page is the map of the machine, and it lights up from the live stream rather
// than being a drawing: an agent is marked as having run because the socket
// said so, and marked as having fallen back because the run reported it.

import { useMemo } from "react";
import { useAgents } from "../../_lib/AgentSocketProvider";
import type { AgentId, Bubble } from "../../_lib/types";
import ConsoleNav from "../ConsoleNav";
import "../admin.css";
import "./agents.css";

type Kind = "python" | "llm" | "human";

interface Stage {
  id: AgentId;
  n: string;
  name: string;
  kind: Kind;
  what: string;
  /** Why it is this kind. The claim the project rests on is that the split is
   *  principled, so every row has to justify its own side of the line. */
  why: string;
  optional?: boolean;
}

const STAGES: Stage[] = [
  {
    id: "a0_intake", n: "A0", name: "Intake Normalizer", kind: "python",
    what: "Turns the wire payload into one request object.",
    why: "Same shape whether it arrived by HTTP or SMS — that identity is the point, so nothing may reinterpret it.",
  },
  {
    id: "a1_dedupe", n: "A1", name: "Dedupe / Cluster", kind: "python",
    what: "Checks geohash-7 cells around the position over a 15-minute window.",
    why: "Whether two reports are the same emergency is a distance and a clock, not a judgement call.",
  },
  {
    id: "a2_triage", n: "A2", name: "Triage", kind: "llm",
    what: "Reads the decoded situation and returns a severity label and tier.",
    why: "Judging that trapped-in-debris outranks displaced-no-shelter is exactly what a model is for.",
  },
  {
    id: "a3_geo", n: "A3", name: "Geo Candidate Finder", kind: "python",
    what: "Runs $geoNear against the offers collection, widening 10 → 25 → 60 → 150 km.",
    why: "Who is nearby is a database query. The console shows the real call and its row count.",
  },
  {
    id: "a4_advocates", n: "A4", name: "Helper Advocates", kind: "llm",
    what: "One call carrying every candidate; each argues for its own claim.",
    why: "This is the debate. The model produces arguments and fit rankings — no amounts.",
  },
  {
    id: "a5_solver", n: "A5", name: "Allocation Solver", kind: "python",
    what: "Computes three named options: fastest, widest coverage, least depleting.",
    why: "Every quantity in the system is produced here, by arithmetic against real stock.",
  },
  {
    id: "a6_arbiter", n: "A6", name: "Arbiter", kind: "llm",
    what: "Chooses one option_id from the set A5 produced, and says why.",
    why: "It picks between options it did not write. An invented quantity is structurally impossible.",
  },
  {
    id: "a7_privacy", n: "A7", name: "Privacy Redactor", kind: "python",
    what: "Applies the field policy per audience and reports what it removed.",
    why: "A privacy rule that a model could talk its way around is not a rule.",
  },
  {
    id: "a8_gate", n: "A8", name: "Admin Gate", kind: "human",
    what: "Parks the run until you approve, override or reject it.",
    why: "The human is a stage in the pipeline, not a spectator. Autopilot only stands in when you let it.",
  },
  {
    id: "a9_narrator", n: "A9", name: "Narrator", kind: "llm",
    what: "Writes the helper's message and its SMS-length variant.",
    why: "Prose for a person to read. Nothing downstream parses it.",
  },
  {
    id: "a10_verify", n: "A10", name: "Verification", kind: "python",
    what: "Confirms delivery once a helper reports back.",
    why: "Runs after acceptance, so it is absent from a fresh request.", optional: true,
  },
  {
    id: "a11_replanner", n: "A11", name: "Replanner", kind: "python",
    what: "On a decline, re-enters at A3 with that helper excluded.",
    why: "Only triggered by a refusal, so most runs never reach it.", optional: true,
  },
];

const KIND_LABEL: Record<Kind, string> = {
  python: "Python", llm: "Groq", human: "You",
};

export default function AgentsSection() {
  const { orderedRuns, connected, eventCount } = useAgents();
  const run = orderedRuns[0];

  // What the newest run actually did, keyed by agent id. `llmAgents` is only
  // reported on run.completed, so mid-run an agent can be "ran" with its
  // model/fallback state still unknown -- shown as unknown rather than guessed.
  const live = useMemo(() => {
    const seen = new Set<string>(run?.agentsSeen ?? []);
    const fellBack = new Set(
      (run?.errors ?? []).filter((e) => e.fallback_used).map((e) => e.agent as string),
    );
    const llm = run?.llmAgents ?? {};

    // The newest bubble each agent produced. Keyed rather than filtered so a
    // stage shows its current line, including a half-streamed one -- which is
    // the whole reason to watch this page during a run rather than after it.
    const say = new Map<string, Bubble>();
    for (const bub of run?.bubbles ?? []) say.set(bub.agent, bub);

    // The stage the run is actually sitting in right now.
    const order = run?.agentsSeen ?? [];
    const at = run?.status === "running" || run?.status === "awaiting_admin"
      ? order[order.length - 1]
      : undefined;

    return { seen, fellBack, llm, say, at };
  }, [run]);

  // Counted against the core pipeline only. A10 and A11 fire on verification
  // and decline, so including them would make a perfectly normal run look
  // permanently two stages short.
  const CORE = STAGES.filter((s) => !s.optional);
  const ranCount = CORE.filter((s) => live.seen.has(s.id)).length;

  return (
    <div className="admin">
      <ConsoleNav connected={connected} eventCount={eventCount} />

      <section className="sectionIntro">
        <h1 className="controlTitle">One request, twelve stages</h1>
        <p className="controlHint">
          Ten stages run on every request: five are ordinary Python, four call a
          model, one is you. Two more run only when something goes wrong. The
          colour of each row is the claim:{" "}
          <strong>a model never writes a number into the database.</strong>
        </p>
      </section>

      <div className="lawStrip">
        <div className="lawHalf llmHalf">
          <span className="lawTag llm">Groq decides</span>
          <p>labels · rankings · arguments · a choice between options · prose</p>
        </div>
        <div className="lawArrow" aria-hidden="true">→</div>
        <div className="lawHalf detHalf">
          <span className="lawTag det">Python decides</span>
          <p>every quantity · every distance · every ETA · every redaction</p>
        </div>
      </div>

      <div className="pipeHead">
        <h2 className="sectionTitle">The pipeline</h2>
        {run ? (
          <span className="pipeLive">
            <span className="trace">{run.traceId}</span>
            <span className={`badge ${run.status}`}>{run.status.replace(/_/g, " ")}</span>
            <span className="pipeCount">{ranCount} of {CORE.length} stages entered</span>
            {run.msTotal != null && (
              <span className="pipeCount">{(run.msTotal / 1000).toFixed(1)}s</span>
            )}
          </span>
        ) : (
          <span className="pipeCount">
            no run yet — dispatch one from Deliberation and these light up
          </span>
        )}
      </div>

      <ol className="pipe">
        {STAGES.map((s) => {
          const ran = live.seen.has(s.id);
          const fell = live.fellBack.has(s.id);
          const usedLlm = live.llm[s.id.replace(/^a\d+_/, "")];
          const bub = live.say.get(s.id);
          const here = live.at === s.id;

          // Evidence from this run. Kept separate from the bubble because the
          // advocates stage speaks in debate turns and emits no message of its
          // own -- keyed off the bubble alone, A4 showed nothing at all while
          // it was the loudest stage in the pipeline.
          const facts: string[] = [];
          if (run) {
            if (s.id === "a1_dedupe" && run.cluster) {
              facts.push(run.cluster.duplicate
                ? `duplicate of an existing cluster (${run.cluster.size})`
                : "no duplicate in range");
            }
            if (s.id === "a4_advocates" && run.turns.length > 0) {
              facts.push(`${run.turns.length} arguments made`);
              if (run.debateWinner) facts.push(`resolved to ${run.debateWinner}`);
            }
            if (s.id === "a5_solver" && run.options.length > 0) {
              facts.push(`${run.options.length} options built · ` +
                run.options.map((o) => o.label.replace(/_/g, " ")).join(" / "));
            }
            if (s.id === "a6_arbiter" && run.chosenOptionId) {
              facts.push(`chose ${run.chosenOptionId}`);
            }
            if (s.id === "a7_privacy" && run.privacy) {
              facts.push(`${run.privacy.fieldsRedacted} field instances removed`);
            }
            if (s.id === "a8_gate" && run.adminAction) {
              facts.push(run.adminAction.action.replace(/_/g, " ") +
                (run.adminAction.option_id ? ` → ${run.adminAction.option_id}` : ""));
            }
            if (s.id === "a9_narrator" && run.notifications.length > 0) {
              facts.push(`${run.notifications.length} helper notified`);
            }
          }
          return (
            <li key={s.id}
                className={`stage ${s.kind} ${ran ? "ran" : ""} ${here ? "here" : ""} ${s.optional ? "opt" : ""}`}>
              <span className="stageN" aria-hidden="true">{s.n}</span>
              <div className="stageBody">
                <div className="stageTop">
                  <span className="stageName">{s.name}</span>
                  <span className={`kindChip ${s.kind}`}>{KIND_LABEL[s.kind]}</span>
                  {ran && <span className="ranChip">entered</span>}
                  {/* Honest about the degraded path: a stage that fell back to
                      its deterministic answer is not the same as one the model
                      actually answered, and the console says which. */}
                  {fell && <span className="fellChip">fell back to Python</span>}
                  {!fell && usedLlm === true && <span className="ranChip llmOk">model answered</span>}
                  {here && <span className="hereChip">running now</span>}
                  {s.optional && <span className="optChip">only when triggered</span>}
                </div>
                <p className="stageWhat">{s.what}</p>
                <p className="stageWhy">{s.why}</p>

                {/* What this stage actually said on the current run. The tool
                    call is rendered verbatim rather than described: seeing the
                    real $geoNear and its row count is the difference between
                    claiming a database was queried and showing it. */}
                {(bub || facts.length > 0) && (
                  <div className="stageOut">
                    {bub?.toolCall ? (
                      <code className="stageTool">
                        {bub.toolCall.tool}({JSON.stringify(bub.toolCall.args)}){" "}
                        → {bub.toolCall.result_count} rows
                        <span className="ms"> {bub.toolCall.ms}ms</span>
                      </code>
                    ) : bub ? (
                      <p className="stageSaid">
                        {bub.text}
                        {bub.streaming && <span className="caret" />}
                        {typeof bub.confidence === "number" && (
                          <span className="conf">conf {bub.confidence.toFixed(2)}</span>
                        )}
                      </p>
                    ) : null}
                    {/* Stage-specific evidence, so each row proves its own
                        claim with a number from this run. */}
                    {facts.map((f) => (
                      <span key={f} className="stageFact">{f}</span>
                    ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <p className="pipeFoot">
        A5 and A6 are deliberately two stages. The solver builds the options and
        owns every number in them; the arbiter may only return one{" "}
        <code>option_id</code>, validated against that set. That is the answer
        to &ldquo;what if the model hallucinates an allocation&rdquo; — it has
        nothing to hallucinate with.
      </p>
    </div>
  );
}
