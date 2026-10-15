# Opening Doors

Named accounts. No relationship yet. Find the door.

Six AI Agents that hunt a named-account book, on the AE's behalf, under governance.
Built with Claude Code on the Claude API.

**All data invented.** Every company, person, signal and number in this repository is made up. No company named here is a real firm.

## What it does

In: 25 named accounts, 4,000 to 20,000 employees, no relationship yet.

Out: 10 targets ranked, each with its reason. Per target: an account plan, five touches drafted and scheduled, a light MEDDPICC, a mutual plan. Under 3 minutes. The AE reviews and sends.

Control: every agent registered and permitted. Every action logged, live. Any agent stoppable mid-run.

No agent is permitted to send. The AE reviews and sends.

## The six agents

1. Researcher. Reads the book and its signals.
2. Scorer. Ranks the 25 against an ideal client profile and says why.
3. Planner. Drafts the account plan for the top ten.
4. Writer. Drafts the five touches per account, matched to its signal.
5. Cadence. Schedules the five touches; after touch five the account rests.
6. Qualifier. After the first call, a light MEDDPICC, the value frame and the mutual plan.

Orchestration is not an agent. It is the desk, a plain controller that hands work between the six, holds each account's state and reports to the page.

## Governance

Modelled on the Blueprint Alliance's four questions, asked in this order:

1. Registered. Where are my agents? A registry: identity, owner, purpose, creation time. Nothing runs unless registered.
2. Permitted. What can they do? A permission list per agent, enforced in code. A denied call is logged and refused.
3. Logged. What are they doing? A plain-English audit log: who, what, when, on what, outcome.
4. Stoppable. How do I respond? A Stop button per agent revokes its token mid-run.

## The journey

Four zones, drawn as a Tube map. Zone 4 Open the door. Zone 3 Earn the call. Zone 2 Frame the value. Zone 1 Commit, ending at a £ roundel: Value Realization Plan signed.

Zones 4 and 3 carry Garret's five-touch sequence. Touch 1, day 1, insight email. Touch 2, day 5, insight email. Touch 3, day 8, LinkedIn connection request. Touch 4, day 11, a call with no voicemail if unanswered, then an email with one small ask. Touch 5, day 18, break-up email. After touch five the account rests. No sixth touch.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env   # add your Anthropic API key
python -m opening_doors.desk
```

Spend is capped. Runs are limited per day. If the cap is hit the page says so and links the recorded video.

## Layout

```
opening_doors/
  config.py          model, caps, paths
  governance/        registry, permissions, audit log, stop
  agents/            the six agents
  book/              the 25 invented accounts and their signals
  desk.py            the controller
web/                 the page (Saturday)
tests/
PLAN.md              progress, next steps, open questions
```

Built by Garret O'Leary, 2026. builtbygarret.com
