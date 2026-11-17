/** Three-step "how to use this page" guides, shared by the app and the docs. */
export const GUIDES = {
  intake: ["Describe the problem in your own words, or load a real example.", "Send it. The details it understood are underlined in your text.", "Answer the one question if it asks, or skip. Either way the ticket is saved."],
  review: ["Pick a ticket from the queue.", "Choose the right team and mark each of the 11 details.", "Save. A second person labels it blind; an admin settles any disagreement."],
  bounce: ["Upload or paste ticket assignment history, or load the example.", "Analyse it here in your browser, or with your workspace.", "Read the map. Thick bands are where tickets get passed around."],
  evaluation: ["See which model is serving and what data it learned from.", "Follow the certification steps: what is proven, what is not yet.", "Optional: upload a predictions file to score it yourself."],
  mcp: ["Inspect the handshake a standard AI agent receives.", "Send a report as an agent and watch each round trip.", "Answer the server's question by quoting the user's words."],
  settings: ["Map each of the 12 teams to one of your real queues.", "Set how costly a wrong route is compared with a human triage.", "Erase a person's incidents on request, in the danger zone."],
} as const;
