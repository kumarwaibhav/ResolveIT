/**
 * Demo scenario library: realistic tickets as employees actually write them.
 * `observed` outcomes are filled from the live demo engine by scripts/verify_scenarios.py
 * (see generated/scenario-results.json); nothing here is assumed to be correct.
 */
export type ScenarioKind = "clear" | "vague" | "multilingual" | "compound" | "error_code" | "security" | "outage";

export interface Scenario {
  id: string;
  kind: ScenarioKind;
  title: string;
  who: string;
  channel: "Slack" | "Email" | "Teams chat" | "Portal" | "Phone transcript" | "WhatsApp";
  text: string;
  locale: "en" | "hi" | "hinglish";
  why: string;
}

export const KIND_LABEL: Record<ScenarioKind, { label: string; blurb: string }> = {
  clear: { label: "Clear", blurb: "The system is named, so the team is identifiable." },
  vague: { label: "Vague", blurb: "No system named. Watch it ask instead of guess." },
  multilingual: { label: "Hindi & Hinglish", blurb: "Mixed scripts and code-switching, as people really type." },
  compound: { label: "Two problems", blurb: "Two systems in one report. It should not pick at random." },
  error_code: { label: "Error codes", blurb: "Codes are kept exactly as typed and used as evidence." },
  security: { label: "Security", blurb: "No questions. Straight to a person, flagged for Security." },
  outage: { label: "Wide outage", blurb: "Many people affected; urgency and scope are read." },
};

export const SCENARIOS: Scenario[] = [
  { id: "net-vpn", kind: "clear", title: "VPN drops every few minutes", who: "Sales executive, Pune", channel: "Slack", locale: "en", text: "VPN keeps disconnecting every few minutes since this morning, I can't stay on the CRM", why: "Names the VPN, gives frequency and start time." },
  { id: "net-wifi", kind: "clear", title: "Wi-Fi gone on one floor", who: "Facilities coordinator", channel: "Teams chat", locale: "en", text: "Wifi is not working on the 3rd floor since today, laptops show no internet", why: "Network symptom with a clear location." },
  { id: "idm-sso", kind: "clear", title: "Okta MFA loop", who: "Finance analyst", channel: "Portal", locale: "en", text: "Okta keeps asking for MFA again and again and never lets me in", why: "Identity provider named; repeated behaviour." },
  { id: "idm-password", kind: "clear", title: "Locked out after password change", who: "New joiner", channel: "Phone transcript", locale: "en", text: "I changed my password yesterday and now my account is locked on every app", why: "Account lockout points to Identity & Access." },
  { id: "mail-outlook", kind: "clear", title: "Outlook crashing for a floor", who: "Office manager, Gurugram", channel: "Email", locale: "en", text: "Outlook keeps crashing for the whole floor since this morning", why: "System, scope and start time all stated." },
  { id: "mail-teams", kind: "clear", title: "Teams calls dropping", who: "Customer success lead", channel: "Slack", locale: "en", text: "Microsoft Teams calls drop after a few seconds, happens every time I present", why: "Collaboration tool named with a repeatable trigger." },
  { id: "hw-laptop", kind: "clear", title: "Laptop won't boot", who: "Field engineer", channel: "WhatsApp", locale: "en", text: "My ThinkPad laptop is stuck on the boot screen since yesterday", why: "Hardware named; only one user affected." },
  { id: "hw-printer", kind: "clear", title: "Printer queue stuck", who: "HR assistant", channel: "Portal", locale: "en", text: "The printer on floor 2 is not printing, print queue is stuck, not urgent", why: "Low urgency is read as well as the device." },
  { id: "sw-licence", kind: "clear", title: "Licence expired", who: "Designer", channel: "Email", locale: "en", text: "My Adobe licence says expired and the activation key is not accepted", why: "Licensing language maps to Software & Licensing." },
  { id: "db-postgres", kind: "clear", title: "Database timeouts", who: "Backend developer", channel: "Slack", locale: "en", text: "Postgres database queries are timing out for the orders service since 10 minutes ago", why: "Database named with a precise start time." },
  { id: "cloud-k8s", kind: "clear", title: "Kubernetes pods crashing", who: "SRE on call", channel: "Slack", locale: "en", text: "Kubernetes pods in the payments cluster keep restarting on AWS, production is down", why: "Cloud platform named; production impact raises urgency." },
  { id: "erp-sap", kind: "clear", title: "SAP posting fails", who: "Accounts payable", channel: "Email", locale: "en", text: "SAP is not letting me post invoices today, month end close is blocked", why: "ERP named; business-critical timing." },
  { id: "hr-payslip", kind: "clear", title: "Payslip missing", who: "Operations associate", channel: "Portal", locale: "en", text: "My payslip for this month is not showing in Workday", why: "HR system named." },
  { id: "devops-pipeline", kind: "clear", title: "Build agents offline", who: "Mobile developer", channel: "Slack", locale: "en", text: "Jenkins pipeline is failing because all build agents are offline, nobody can deploy", why: "CI/CD system named; team-wide impact." },
  { id: "av-projector", kind: "clear", title: "Boardroom projector", who: "Executive assistant", channel: "Phone transcript", locale: "en", text: "The projector in the main conference room shows no signal, board meeting in 20 minutes", why: "Meeting room equipment named; time pressure." },

  { id: "vague-nothing", kind: "vague", title: "Nothing works", who: "Store manager", channel: "WhatsApp", locale: "hinglish", text: "kal se kuch bhi kaam nahi kar raha, please jaldi dekho", why: "No system named. The right move is one question." },
  { id: "vague-slow", kind: "vague", title: "Everything is slow", who: "Recruiter", channel: "Teams chat", locale: "en", text: "everything is super slow today, please help", why: "A symptom without a system." },
  { id: "vague-stopped", kind: "vague", title: "It stopped again", who: "Warehouse supervisor", channel: "Phone transcript", locale: "en", text: "it stopped working again, same as last week", why: "Refers to an unnamed 'it'." },

  { id: "ml-hindi-mail", kind: "multilingual", title: "Email in Devanagari", who: "Branch officer, Lucknow", channel: "WhatsApp", locale: "hi", text: "मेरा ईमेल सुबह से नहीं खुल रहा, बहुत ज़रूरी है", why: "Hindi script: system, start time and urgency." },
  { id: "ml-hinglish-vpn", kind: "multilingual", title: "Hinglish VPN", who: "Analyst, Hyderabad", channel: "Slack", locale: "hinglish", text: "vpn baar baar disconnect ho raha hai subah se, poori team ka same issue", why: "Code-switching with frequency and team scope." },
  { id: "ml-hinglish-laptop", kind: "multilingual", title: "Laptop slow, Hinglish", who: "Intern", channel: "WhatsApp", locale: "hinglish", text: "mera laptop bahut slow hai pehli baar aisa hua, sirf mera issue hai", why: "Single-user scope and first occurrence, in Hinglish." },

  { id: "cmp-vpn-teams", kind: "compound", title: "VPN then Teams", who: "Team lead", channel: "Slack", locale: "en", text: "VPN disconnects every few minutes and after that MS Teams calls drop, whole team since yesterday", why: "Two systems. It should narrow down before routing." },
  { id: "cmp-sso-sap", kind: "compound", title: "SSO blocks SAP", who: "Finance controller", channel: "Email", locale: "en", text: "After the Okta update I cannot open SAP or Workday, error on login", why: "Identity issue surfacing in two business apps." },

  { id: "err-hex", kind: "error_code", title: "Windows error 0x80070005", who: "Accountant", channel: "Portal", locale: "en", text: "Outlook shows error 0x80070005 when I open shared mailbox, urgent", why: "Hex code kept verbatim and linked as evidence." },
  { id: "err-ora", kind: "error_code", title: "Oracle ORA-12541", who: "Data engineer", channel: "Slack", locale: "en", text: "Reports fail with ORA-12541 since 2 hours ago, database unreachable", why: "Vendor error code plus database." },
  { id: "err-http", kind: "error_code", title: "HTTP 503 on portal", who: "Support agent", channel: "Teams chat", locale: "en", text: "The HR portal returns status 503 for everyone since this morning", why: "HTTP status and organisation-wide scope." },

  { id: "sec-phish", kind: "security", title: "Typed password into a link", who: "Marketing manager", channel: "Email", locale: "en", text: "I clicked a link in an email and typed my password, now my account is sending spam to everyone", why: "Credential phishing. Must escalate, never ask." },
  { id: "sec-ransom", kind: "security", title: "Files encrypted", who: "Branch cashier", channel: "Phone transcript", locale: "en", text: "all files on the shared drive have strange extensions and there is a ransom note on my screen", why: "Nobody says “ransomware”: they describe a ransom note and files that won’t open. That wording now counts as a security signal, so it goes straight to a person." },
  { id: "sec-suspicious", kind: "security", title: "Suspicious login alert", who: "CFO's assistant", channel: "Slack", locale: "en", text: "got a suspicious login alert from another country on my email account", why: "Possible account compromise." },

  { id: "out-everyone", kind: "outage", title: "Company-wide email outage", who: "IT desk, 40 calls", channel: "Phone transcript", locale: "en", text: "email is down for everyone in the company since 10 minutes ago, critical", why: "Organisation-wide scope with critical urgency." },
];

export function scenarioById(id: string | null | undefined): Scenario | undefined {
  return id ? SCENARIOS.find((s) => s.id === id) : undefined;
}
