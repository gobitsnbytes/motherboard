// Generates the 5 onboarding compositions from one template.
// Run: bun build.ts   (then `npx hyperframes check` inside each folder)
import { cpSync, mkdirSync, writeFileSync } from "node:fs";

type Why = { t: string; d: string };
type Step = { t: string; d: string };
type Video = {
  slug: string; title: string; sub: string;
  what: string; whatMock: string;
  why: Why[];
  how: Step[]; howMock: string;
  recap: string; where: string;
};

// Scene timing (seconds). Same skeleton for every video.
const S = { title: [0, 4], what: [4, 8], why: [12, 8], how: [20, 15], recap: [35, 4] } as const;
const TOTAL = 39;
const WHY_AT = [0.6, 2.3, 4.0];
const stepTimes = (n: number) => Array.from({ length: n }, (_, i) => +(0.6 + i * (n > 4 ? 2.7 : 3.4)).toFixed(2));

const videos: Video[] = [
  {
    slug: "01-sign-in",
    title: "Signing in",
    sub: "No passwords. Your Discord account is your ID.",
    what: `You sign in to Motherboard with your <em>Discord</em> account. There is no separate password.`,
    whatMock: `
      <div class="mock login" data-in="1.2">
        <div class="chip">Member sign-in</div>
        <div class="mh">Motherboard</div>
        <div class="sk w90"></div><div class="sk w70"></div>
        <div class="btn discord" data-in="2.0">Continue with Discord</div>
        <div class="tiny">Private access · Verified Discord identity required</div>
      </div>`,
    why: [
      { t: "Nothing to leak", d: "No passwords stored, none to forget." },
      { t: "One identity", d: "Your Discord roles already say who you are." },
      { t: "Logged", d: "Every sign-in is recorded for audit." },
    ],
    how: [
      { t: "Click “Continue with Discord”", d: "On the Motherboard login page." },
      { t: "Allow on Discord", d: "It shares your profile, email and servers." },
      { t: "We match your account", d: "Motherboard finds or creates your member record." },
      { t: "You land on your dashboard", d: "You stay signed in with a secure session." },
    ],
    howMock: `
      <div class="flow">
        <div class="node" data-step="0"><span class="mono">/login</span><div class="btn discord sm">Continue with Discord</div></div>
        <div class="arrow" data-step="1">↓</div>
        <div class="node" data-step="1"><span class="mono">discord.com</span><div class="sk w80"></div><div class="btn sm">Authorize</div></div>
        <div class="arrow" data-step="2">↓</div>
        <div class="node" data-step="2"><span class="mono">Motherboard API</span><div class="line">Member found ✓</div></div>
        <div class="arrow" data-step="3">↓</div>
        <div class="node dark" data-step="3"><span class="mono">/dashboard/overview</span><div class="sk w70 onDark"></div></div>
      </div>`,
    recap: "Your Discord account is your Motherboard account. Protect it with two-factor login.",
    where: "Motherboard → /login",
  },
  {
    slug: "02-permissions",
    title: "Permissions",
    sub: "Who can do what, and in which city.",
    what: `A <em>permission</em> is one action. A <em>grant</em> gives it to a person or group, for every city or just one.`,
    whatMock: `
      <div class="mock grant" data-in="1.4">
        <div class="mh">Grant</div>
        <div class="row" data-in="2.0"><span>Permission</span><b class="mono">meetings.write</b></div>
        <div class="row" data-in="2.5"><span>Scope</span><b class="mono">fork:delhi</b></div>
        <div class="row" data-in="3.0"><span>Given to</span><b>Group · Fork Lead</b></div>
        <div class="row" data-in="3.5"><span>Expires</span><b>31 Mar 2027</b></div>
      </div>`,
    why: [
      { t: "City boundaries", d: "Delhi’s lead can’t change Mumbai by accident." },
      { t: "Access expires", d: "Temporary access ends on its own." },
      { t: "Explainable", d: "Every “yes” or “no” has a clear reason." },
    ],
    how: [
      { t: "Discord role → group", d: "e.g. the fork-lead role puts you in “Fork Lead”." },
      { t: "Groups hold grants", d: "A grant is a permission plus a scope." },
      { t: "Global or one city", d: "Global covers every city. fork:delhi covers only Delhi." },
      { t: "Missing one? You’ll see why", d: "The app names the permission you need. Ask an admin." },
    ],
    howMock: `
      <div class="flow">
        <div class="node" data-step="0"><span class="mono">Discord role</span><div class="line mono">fork-lead</div></div>
        <div class="arrow" data-step="1">↓</div>
        <div class="node" data-step="1"><span class="mono">Group</span><div class="line">Fork Lead</div></div>
        <div class="arrow" data-step="2">↓</div>
        <div class="node" data-step="2"><span class="mono">Grants</span><div class="line mono">forks.read · meetings.write</div><div class="chip">scope fork:delhi</div></div>
        <div class="toast" data-step="3">Missing permission: finance.admin on fork:delhi</div>
      </div>`,
    recap: "You can only give someone a permission you already hold.",
    where: "Dashboard → IAM",
  },
  {
    slug: "03-onboarding",
    title: "Onboarding",
    sub: "How a new volunteer or fork lead joins.",
    what: `HQ opens a <em>case</em> for each new person. They get a private link to fill in and sign their documents.`,
    whatMock: `
      <div class="stack">
        <div class="mock" data-in="1.2">
          <div class="mh">Start a case</div>
          <div class="tabs"><span class="on">Volunteer</span><span>Fork lead</span></div>
          <div class="sk w90"></div><div class="sk w70"></div>
        </div>
        <div class="mock" data-in="2.2">
          <div class="mh sm">bits&amp;bytes onboarding workspace</div>
          <div class="line">1. Fill and submit.</div>
          <div class="line">2. Address comments.</div>
          <div class="line">3. HQ finalizes.</div>
        </div>
      </div>`,
    why: [
      { t: "One place", d: "All joining paperwork lives in one workspace." },
      { t: "Safe for minors", d: "Under-18s get guardian consent built in." },
      { t: "Reviewed", d: "HQ checks every document before it counts." },
    ],
    how: [
      { t: "HQ clicks “Start a case”", d: "Volunteer or Fork lead, name and email." },
      { t: "The person fills and submits", d: "From their private link. No login needed." },
      { t: "A reviewer approves", d: "Or asks for changes, and they fix and resend." },
      { t: "Everyone signs, HQ finalizes", d: "The case is marked approved." },
    ],
    howMock: `
      <div class="mock doc">
        <div class="mh sm">Code of Conduct.pdf</div>
        <div class="sk w90"></div><div class="sk w80"></div><div class="sk w60"></div>
        <div class="states">
          <span data-step="0">awaiting completion</span>
          <span data-step="1">review requested</span>
          <span data-step="2">approved</span>
          <span data-step="3">signed ✓</span>
        </div>
      </div>`,
    recap: "Everyone must be 13 or older. Under 18? A guardian consents in their own workspace.",
    where: "/dashboard/onboarding",
  },
  {
    slug: "04-signatures",
    title: "Signatures",
    sub: "Send and sign contracts online. No printing.",
    what: `Our own e-sign tool. Upload a contract, add signers, and each person signs from a <em>link in their email</em>.`,
    whatMock: `
      <div class="mock doc" data-in="1.2">
        <div class="mh sm">Partnership Agreement.pdf</div>
        <div class="sk w90"></div><div class="sk w80"></div><div class="sk w90"></div><div class="sk w50"></div>
        <div class="fields">
          <span class="field" data-in="2.0">Signature</span>
          <span class="field" data-in="2.4">Full Name</span>
          <span class="field" data-in="2.8">Date Signed</span>
        </div>
      </div>`,
    why: [
      { t: "Legally valid", d: "E-signatures under India’s IT Act, 2000." },
      { t: "Verified signers", d: "A 6-digit email PIN confirms each person." },
      { t: "Tamper-proof", d: "Sealed PDF with a full audit trail." },
    ],
    how: [
      { t: "Upload the document", d: "PDF or Word. Word files are converted." },
      { t: "Add signers, place fields", d: "Name and email for each signer." },
      { t: "“Finalize & Send Links”", d: "Each signer gets their own email link." },
      { t: "Signer enters PIN and signs", d: "Draw, type or upload a signature." },
      { t: "Executed & Sealed", d: "Everyone’s signed. The PDF is sealed." },
    ],
    howMock: `
      <div class="flow tight">
        <div class="node" data-step="0"><span class="mono">upload</span><div class="line">Partnership Agreement.pdf</div></div>
        <div class="node" data-step="1"><span class="mono">signers</span><div class="line">Aarav · Primary Signer</div><div class="line">Meera · Authorized Signatory</div></div>
        <div class="btn" data-step="2">Finalize &amp; Send Links</div>
        <div class="node" data-step="3"><span class="mono">/sign/…</span><div class="pin"><i>4</i><i>8</i><i>1</i><i>9</i><i>0</i><i>2</i></div></div>
        <div class="stamp" data-step="4">Executed &amp; Sealed ✓</div>
      </div>`,
    recap: "Anyone can check that a signed PDF is genuine on the Verify page.",
    where: "/dashboard/signatures",
  },
  {
    slug: "05-calendar-pools",
    title: "Calendar pools",
    sub: "One booking link. Many hosts.",
    what: `A <em>routing pool</em> puts several hosts’ Cal.com calendars behind one link. Bookers see everyone’s free time as one.`,
    whatMock: `
      <div class="pool" data-in="1.2">
        <div class="cals">
          <div class="cal" data-in="1.4"><b>Host A</b><i></i><i class="free"></i><i></i><i class="free"></i></div>
          <div class="cal" data-in="1.7"><b>Host B</b><i class="free"></i><i></i><i></i><i class="free"></i></div>
          <div class="cal" data-in="2.0"><b>Host C</b><i></i><i class="free"></i><i class="free"></i><i></i></div>
        </div>
        <div class="arrow" data-in="2.6">↓</div>
        <div class="link mono" data-in="2.9">/book/community-onboarding</div>
      </div>`,
    why: [
      { t: "Nobody gets swamped", d: "Bookings are shared out across hosts." },
      { t: "One link to share", d: "Bookers never chase the right person." },
      { t: "Invites are automatic", d: "Cal.com sends emails and the Google Meet." },
    ],
    how: [
      { t: "Hosts connect Cal.com", d: "Paste a Cal.com API key, then Verify." },
      { t: "Admin creates a pool", d: "Name, public link, and “Round robin”." },
      { t: "Add hosts to the pool", d: "Pick each host and their event type." },
      { t: "Share the link", d: "Motherboard picks a free host for every booking." },
    ],
    howMock: `
      <div class="mock ops">
        <div class="mh sm">Calendar operations</div>
        <div class="row" data-step="0"><span>Host connection</span><b>Verified ✓</b></div>
        <div class="row" data-step="1"><span>Pool</span><b class="mono">community-onboarding · Round robin</b></div>
        <div class="row" data-step="2"><span>Hosts</span><b>Host A · Host B · Host C</b></div>
        <div class="booked" data-step="3"><b>You’re booked.</b><span class="btn sm">Open Google Meet</span></div>
      </div>`,
    recap: "Chrono, the old booking portal, is read-only history now. New bookings go through pools.",
    where: "/dashboard/meetings",
  },
];

const esc = (s: string) => s.replace(/&(?!amp;|#)/g, "&amp;");

function page(v: Video, idx: number) {
  const n = String(idx + 1).padStart(2, "0");
  const st = stepTimes(v.how.length);
  // Map data-step="k" in the how mockup to an absolute data-in time.
  const howMock = v.howMock.replace(/data-step="(\d)"/g, (_, k) => `data-in="${st[+k]}"`);
  const sfx: string[] = [];
  let track = 11;
  const add = (t: number, file: string, vol = 0.6) =>
    sfx.push(`<audio id="sfx-${track}" data-start="${t.toFixed(2)}" data-track-index="${track++}" data-volume="${vol}" src="assets/sfx/${file}"></audio>`);
  add(0.25, "bong_001.ogg", 0.45);
  for (const s of [S.what, S.why, S.how, S.recap]) add(s[0] + 0.05, "drop_002.ogg", 0.4);
  WHY_AT.forEach((t) => add(S.why[0] + t - 0.05, "drop_001.ogg", 0.55));
  st.forEach((t) => add(S.how[0] + t - 0.05, "mouseclick1.ogg", 0.5));

  const scene = (id: string, [start, dur]: readonly number[], section: string, inner: string) =>
    `<section id="${id}" class="clip scene" data-start="${start}" data-duration="${dur}" data-section="${section}" data-track-index="1"><div class="inner">${inner}</div></section>`;

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<title>Motherboard onboarding ${n}: ${v.title}</title>
<script src="assets/gsap.min.js"></script>
<link rel="stylesheet" href="assets/style.css" />
<style>
@font-face { font-family: "Anton"; src: url("assets/fonts/anton-latin-400-normal.woff2") format("woff2"); font-weight: 400; }
@font-face { font-family: "Inter"; src: url("assets/fonts/inter-latin-400-normal.woff2") format("woff2"); font-weight: 400; }
@font-face { font-family: "Inter"; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); font-weight: 600; }
@font-face { font-family: "Inter"; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); font-weight: 800; }
@font-face { font-family: "JetBrains Mono"; src: url("assets/fonts/jetbrains-mono-latin-500-normal.woff2") format("woff2"); font-weight: 500; }
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1920" data-height="1080" data-duration="${TOTAL}">
  <header id="topbar">
    <div class="brand"><b>bits&amp;bytes™</b> Motherboard · Onboarding ${n}/05</div>
    <div class="rail"><span id="rail-what">What</span><span id="rail-why">Why</span><span id="rail-how">How</span></div>
  </header>
  <div id="progress"><div id="progress-fill"></div></div>

  ${scene("s-title", S.title, "", `
    <div class="titlecard">
      <div class="kicker" data-in="0.2">Onboarding ${n} / 05</div>
      <h1 data-in="0.4">${v.title}</h1>
      <p class="sub" data-in="0.9">${esc(v.sub)}</p>
      <div class="outline" data-in="1.5"><span>What it is</span><span>Why we use it</span><span>How it works</span></div>
    </div>`)}

  ${scene("s-what", S.what, "what", `
    <div class="split">
      <div class="col">
        <div class="kicker" data-in="0.2">What</div>
        <h2 data-in="0.4">${esc(v.what)}</h2>
      </div>
      <div class="col mockcol">${v.whatMock}</div>
    </div>`)}

  ${scene("s-why", S.why, "why", `
    <div class="kicker" data-in="0.2">Why</div>
    <div class="cards">${v.why.map((w, i) => `
      <div class="card" data-in="${WHY_AT[i]}"><div class="num">${i + 1}</div><h3>${esc(w.t)}</h3><p>${esc(w.d)}</p></div>`).join("")}
    </div>`)}

  ${scene("s-how", S.how, "how", `
    <div class="split how">
      <div class="col">
        <div class="kicker" data-in="0.2">How</div>
        <ol class="steps">${v.how.map((s, i) => `
          <li class="step" data-in="${st[i]}" data-active="${st[i]}"><span class="n">${i + 1}</span><div><h4>${esc(s.t)}</h4><p>${esc(s.d)}</p></div></li>`).join("")}
        </ol>
      </div>
      <div class="col mockcol">${howMock}</div>
    </div>`)}

  ${scene("s-recap", S.recap, "", `
    <div class="titlecard">
      <div class="kicker" data-in="0.2">Remember</div>
      <h2 class="big" data-in="0.4">${esc(v.recap)}</h2>
      <div class="where mono" data-in="1.0">Find it: ${esc(v.where)}</div>
    </div>`)}

  <audio id="bgm" data-start="0" data-duration="${TOTAL}" data-track-index="10" data-volume="1" src="assets/music/bed.mp3"></audio>
  ${sfx.join("\n  ")}
</div>
<script>
  const tl = gsap.timeline({ paused: true });
  const INK = "#120f0a", CREAM = "#f8f1e7", BURG = "#97192c";
  tl.fromTo("#progress-fill", { scaleX: 0 }, { scaleX: 1, duration: ${TOTAL}, ease: "none" }, 0);
  tl.fromTo("#bgm", { volume: 0 }, { volume: 0.22, duration: 1.2 }, 0);
  tl.to("#bgm", { volume: 0, duration: 1.8 }, ${TOTAL - 2});

  document.querySelectorAll(".scene").forEach((scene) => {
    const start = +scene.dataset.start, dur = +scene.dataset.duration;
    scene.querySelectorAll("[data-in]").forEach((el) => {
      tl.fromTo(el, { opacity: 0, y: 28 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }, start + +el.dataset.in);
    });
    // Highlight the current step; previous ones settle back.
    const steps = [...scene.querySelectorAll("[data-active]")];
    steps.forEach((el, i) => {
      const t = start + +el.dataset.active;
      tl.fromTo(el, { backgroundColor: "rgba(255,255,255,0)", boxShadow: "0px 0px 0px #120f0a" },
        { backgroundColor: "rgba(255,255,255,1)", boxShadow: "6px 6px 0px #120f0a", duration: 0.3 }, t);
      if (i > 0) tl.to(steps[i - 1], { backgroundColor: "rgba(255,255,255,0)", boxShadow: "0px 0px 0px #120f0a", duration: 0.3 }, t);
    });
    // Skeleton rail: light up What / Why / How.
    const sec = scene.dataset.section;
    ["what", "why", "how"].forEach((k) => {
      const on = k === sec;
      tl.to("#rail-" + k, { backgroundColor: on ? BURG : "rgba(0,0,0,0)", color: on ? CREAM : INK, duration: 0.25 }, start);
    });
    tl.to(scene.querySelector(".inner"), { opacity: 0, duration: 0.35 }, start + dur - 0.45);
  });
  window.__timelines["main"] = tl;
</script>
</body>
</html>
`;
}

videos.forEach((v, i) => {
  const dir = `${import.meta.dir}/${v.slug}`;
  mkdirSync(dir, { recursive: true });
  cpSync(`${import.meta.dir}/shared`, `${dir}/assets`, { recursive: true });
  writeFileSync(`${dir}/index.html`, page(v, i));
});
console.log("built", videos.map((v) => v.slug).join(", "));
