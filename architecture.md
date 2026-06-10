overall architecture:

Trigger -> Workflows -> Commands -> Metaprompts -> templates

Breakdown:
trigger: self explanatory. usually a task.md to start, until we build a ticket-management dashboard or use free software like notion or github issues (need to discuss with agent on options for personal projects)
workflows: highest level dictator implemented as DETERMINISTIC .py scripts. They are to orchestrate the entire SDLC. we call them adw (agentic developmoent workflows). e.g bug_plan_implement_test.md, or trivial_implement_test.md, or feat_full_cycle.md. different workflows calls different lower level commands, metaprompts, and templates. 

commands: light weight, reusable prompts. E.g. /PRIME command implemented as PRIME.md, allows the new agent in the codebase to quickly get context on the codebase, git hooks, rules, styles, git status. E.g. /PLAN command to tell the agent to invoke the plan stage specifically, /IMPLEMENT, etc.

metaprompts: prompts that build prompts. These are supposed to be detailed. For example, meta_plan.md. This should include a section called "plan_format" which details exactly how a bug/feat/chore type ticket should be planned, to be consistent and deterministic throughout the repo/project.
Or another: meta_test.md. this should explicitly state how a bug/feat/chore type should be tested, which tools the agent should use, testing steps, non-negotiable core workflows, etc.

templates: These are .mds that are general on purpose to solve classes of problems, NOT a specific ticket plan. specific ticket plans should not be preserved in the codebase, but templates should. They are another level of granularity more than metaprompts. They specify how a particular class of problem, such as creating an mcp, developing a page on the frontend, adding an api, should be implemented. They serve as a TEMPLATE for the TRIGGER to point at. E.g. at the very beginning, when an agent picks up a ticket, it will look through templates to see if a similar class of problem has already been solved and provided, then it can point the new agent at that template set for the entire sdlc.
e.g. we already built an api. that means we went through plan, implement, test, review for the api already. which means, we don't need to go through plan, implement, test, review workflows or metaprompts to generate another template, but rather, we can point the agent at each of template_api_plan.md, template_api_test.md, etc. for it to carry through the SDLC without doing redundant work.

proposed architecture:

each of workflows, commands, metaprompts, templates, observability (for logging, history, etc.), configs (per-repo configs, rules, etc.), hooks, should have their own dir. 


how the SDLC works:

human: problem identification, solution proposal, spins up tickets
Agent: Cron triggers to poll tickets or task.md, agentically break features down into manageable tickets pick ticket, then goes through plan, implement, test, review, push (for personal project, which is scope of our repo, no pr required). 

Key to prevent context rot: Instead of using 1 agent for everything or sub agents, the workflow should terminate the old agent and spawn in new agent instance at each stage of the workflow, using state.json as a way to offload context compactly.

Looping: testing and review should validate different things that could direct back to plan:
test -> did everything pass? build, smoke, unit, regression...
review -> did what's build reflect what was tasked? E.g. refer back to original ticket.

past failure notes:
- no redundant logs. observability is good, but note that for smaller features it's unlikely that these logs are going to get reviewed. logs as hand-offs between agents within 1 run is fine, but remember to delete
- parallelization via git worktrees
- deterministic harness via json, via shell scripts, via git pre-commit and post-commit hooks
- Timeouts: stall/timeout require fixing the system
- adjust models based on task importance and phase. list as config.sh or config.json to be deterministic. 
- Being deterministic and explicit: tell the agents exactly what to run, what tools to use (built in tools to claude code, or software tools implemented from third party libraries like Playwright, or agentic tools like a ___.md)
- deterministic data flow: explicitly allow prompts being ran as scripts, and prompts being passed into scripts as --flags, and explicit file paths passed in as inputs into scripts to ensure the right data flows through entire sdlc.
- Context preservation: modularize .mds. never have giant CLAUDE.mds or instructions due to the "loss of middle" problem with agents and context bloat. Architect the .mds such that the agent will explicitly know what it should be looking for. 
- Use front-matter in every single .mds as a label for the md that's more specific than just the title. Explicitly state what the md is for, when should an agent bother reading through it, at waht stage of SDLC, under waht conditions, etc.
- Detailed naming description. Don't be afraid to use long, descriptive names
- No redundant PR and commit messages. Sure, they are good as documentation to figure out why a change was made a month later, but they should be made succinct. NOTE: since we're not doing PR in any personal projects, we will keep track of a singular history.md with short PRs documenting what has been implemented and why. This is never read by agents and therefore will not contribute to context bloat. this is for human observability only.

concept of self-healing system:
when an agent reviewing discover a mistake in previous stages that is due to ambiguity in the .md harnesses, it should make a new ticket to repair the system itself. 

