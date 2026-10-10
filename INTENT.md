All right, the idea now has somewhat evolved. We're going to use neat logs, so there's a lot of traceability involved: 

1. Taking a look at what happened and what sort of steps happened.
2. Writing a bunch of evaluations to take a look at what's ideal and what needs to happen versus what actually happened in terms of traces and the outputs.
3. Once we know that has happened, we make a modification, then use Japa to come up with different transformations.
4. Wear a red hat and take a look at what sort of prompts won't work.
5. Take a look at all of those trajectories across our agents. Pass that on to evaluators again, fix it, and then write a PR to fix the whole flow.

 That's going to be the idea right now. Just let me know what you think about it. I want you to take a look at YC organisations and maybe EF, and so on and so forth. Who else has done it? That's what I want you to do. Nothing else. You have literally no other work. This is all you have to do, okay? Just take a look at my idea, see who has done it, Just say who has done it. I think Agnost has done something similar. They have done the GitHub part of it, but I'm doing the prehand, where I fix regions. Okay, let's do this: take and see whether or not we need to fill with memory. 

initial :
Ive been meanign to build something useful an agent that becomes a self healing loop that ends up abalysing trajectories and harnesses Oauth to connect to your favorite apps to build skills as you wish! 

this aims to become a harness to create agents as you wish! I aim to bring together the composio ecosystem and use the connectivity form that to create loops that heal themselves. 

Right now I'm thinking about a setup roughly like:

`agent → tools → trajectory → evaluator → learn from failure → updated skill`

I need you to tell one pain point that you've been dealing with, a niche that isnt technical or very technical where this loop can be put to use.

Right now Im planning to run this over a bunch of Datasets for LLMs to evaluate and create specialised skills accordingly and running evals on em. 

Im doing this to understand what you guys are facing, im not altman to say its gonna be open-source and ignore it. I will keep this fully open-source and ill post a repo url once im done.

Does GEPA suffice this?
