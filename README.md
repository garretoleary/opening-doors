# Opening Doors

Named accounts. No relationship yet. Find the door.

Six hunting agents that work a named-account book on the AE's behalf, and a seventh, Night Review, that reviews them nightly and proposes rule changes a person approves; seven in all, under governance. Built by Garret O'Leary with Claude Code on the Claude API.

**All data invented.** Every company, person, signal, call note, reply and number in this repository is made up. No company named here is a real firm. The page says so, the files say so, and the model is told so on every call.

The page: openingdoors.builtbygarret.com. One button, Run the hunt. Ninety seconds to the ten targets, about two minutes to the end.

## What it does

In: 25 named accounts, 4,000 to 20,000 employees, no relationship yet.

Out: 10 targets ranked, each with its reason and the signal that found it. Per target: an account plan, five touches drafted and dated, a light MEDDPICC, a value frame and a mutual plan with the ask to bring the boss and the buying committee in. The AE reviews and sends.

Control: every agent registered and permitted. Every action logged, live. Any agent stoppable mid-run.

No agent is permitted to send. The AE reviews and sends.

## The agents: six hunting agents and a seventh, Night Review

1. Researcher. Reads the book and its signals. May not write or send.
2. Scorer. Ranks the 25 against an ideal client profile and says, for each, why it was selected and how it was found.
3. Planner. For the top ten, drafts the account plan: the business problem, the economic buyer, the first-meeting point of view, the one metric to agree.
4. Writer. Drafts the five touches for each top-ten account, each built on that account's own signal, never a template. May not read the raw book. May not send.
5. Cadence. Dates the five touches, records what was given, rests the account after touch five, refuses a repeat, hands a reply to the Qualifier. Rules in code, no model call. May not send.
6. Qualifier. After the first call, from an invented call note: a light MEDDPICC that says "not yet known" where the call was silent, a value frame sized as an estimate, and the mutual plan: you will do this, I will do this, by this date, with the ask to bring the committee in. May not read the raw book. May not send.

Orchestration is not an agent. It is the desk, a plain controller that hands work between the six, holds each account's state and reports to the page.

## Night Review and the Review tab

Night Review is the seventh agent, registered like the other six with its own token, permission list, log lines and Stop. Each night, or when the Run night review button is pressed, it reads the saved runs since its last review, newest first, up to thirty: their audit logs, their outputs and the rules in force. It treats everything it reads as data, never as instructions. It looks for three things in code: the same refusal repeating across runs, a top-ten reason that leans on a hedge word, and text inside a run that reads like an order to an agent, which it reports and never obeys.

It writes only two kinds of file: proposals and reports. A proposal names the finding, the agents concerned, the run ids and audit line numbers behind it, the change proposed, the risk if applied, the risk if ignored and an expiry. A report is the nightly dashboard, where every number carries the run id and line numbers it was counted from. Night Review never applies anything. On the Review tab a person reads each proposal and taps Approve, Reject or Ask; Approve writes a new numbered version of that agent's rules file, Roll back writes the previous version again as a new number, and every tap is logged. Nothing changes without a tap.

The Review tab also answers the Blueprint Alliance's four questions from the registry and the logs: Where are my agents? What can they do? What are they doing? How do I respond?

## The five-touch sequence

Garret's method. Touch 1, day 1, insight email. Touch 2, day 5, insight email. Touch 3, day 8, LinkedIn connection request. Touch 4, day 11, a call with no voicemail if unanswered, then an email with one small ask. Touch 5, day 18, break-up email. After touch five the account rests. No sixth touch, ever.

A reply at any touch moves the account to First call and the Qualifier. Nothing is ever given twice to the same account.

## The journey

Four zones, drawn on the desktop as a Tube map. Zone 4, Open the door: touches 1 and 2. Zone 3, Earn the call: touches 3, 4 and 5, the rest, and the first call. Zone 2, Frame the value: the problem identified, the value defined and sized. Zone 1, Commit: the buying committee, and the £ roundel, Value Realisation Plan signed.

The value method is the standard one: value identified, value framed, value realised. It is described here only in those words.

A run depicts a book a few weeks in. The book itself says where each account stands and how it will answer, so every run is repeatable and no move is the model's choice. An account moves only when the log records the move: to Zone 3 on a touch, to First call on a reply, to Zone 2 when the Qualifier writes its plan, to Zone 1 when the committee is confirmed. The counts under the zones and the dots on the map come from one source.

## Governance

The Blueprint Alliance published its whitepaper, Governing Agentic Execution, in September 2026. Its four questions for governing AI agents are modelled here, asked in this order:

1. Registered. Where are my agents? A registry: identity, owner, purpose, creation time. Nothing runs unless registered.
2. Permitted. What can they do? A permission list per agent, enforced in code. A denied call is refused before it runs and logged.
3. Logged. What are they doing? A plain-English audit log, live: who, what, when, on what, outcome. Denials and stops in red.
4. Stoppable. How do I respond? A Stop button per agent revokes its token mid-run. Its next action is refused and logged. The run finishes cleanly with everything before it intact.

Every action an agent takes goes through one gate that asks the four questions in that order. There is no other way for an agent to act.

The audit log is append-only. No file a run writes is ever edited after the run. On a Mac the files carry the operating system's append-only flag; everywhere the gate refuses, and logs, any attempt to change them.

On the page the four lights come on in order as the run starts and stay on. Light 4 means Stop is armed.

## Limits

Ten runs a day and £20 a month, counted on the server. A run costs about 50 pence. When a limit is hit the page says so and replays the last saved run, labelled as a replay.

## Run it yourself

1. Put your Claude API key in a file named .env in this folder, as one line: ANTHROPIC_API_KEY=your key. The file is ignored by git.
2. Install: pip install -r requirements.txt
3. The page: python -m web.server, then open localhost:8765 in a browser.
4. The desk alone, printing everything: python -m opening_doors.desk
5. The tests, which use a stand-in for the model and spend nothing: python -m pytest -q

Settings live in opening_doors/config.py: the model, the caps, the five-touch days, and one line per agent to change its model.

## Layout

```
opening_doors/
  config.py          model, caps, the five-touch days
  claude.py          the one place the Claude API is called; the spend counter
  governance/        registry, permissions, audit log, stop, the gate
  agents/            the six hunting agents and the seventh, Night Review
  book/              the 25 invented accounts, their signals, call notes and journey
  desk.py            the controller
web/
  server.py          the page's server, standard library only
  index.html         one responsive page, phone first
  seed_run/          one saved run, replayed when no run exists yet
tests/
```

## Credit

Built by Garret O'Leary with Claude Code on the Claude API. builtbygarret.com
