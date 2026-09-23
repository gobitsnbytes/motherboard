import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Onboarding videos",
  description: "Short videos on how Motherboard works: sign-in, permissions, onboarding, signatures and calendar pools.",
};

// Videos live in apps/web/public/onboarding/, rendered from brag-output-onboarding/.
const VIDEOS = [
  {
    slug: "01-sign-in",
    title: "Signing in",
    summary: "You sign in with your Discord account. There is no separate password. Click “Continue with Discord”, allow access, and you land on your dashboard.",
    help: "Can’t get in, or not sure which account to use.",
  },
  {
    slug: "02-permissions",
    title: "Permissions",
    summary: "A permission is one action. A grant gives it to a person or group, either for every city or for just one. Your Discord role puts you in a group, and the group holds the grants.",
    help: "You saw “Missing permission”, or a button is missing.",
  },
  {
    slug: "03-onboarding",
    title: "Onboarding",
    summary: "HQ opens a case for each new volunteer or fork lead. The person fills in and signs their documents from a private link, a reviewer approves them, and HQ finalizes.",
    help: "You got an onboarding link, or you’re reviewing a new member.",
  },
  {
    slug: "04-signatures",
    title: "Signatures",
    summary: "Our own e-sign tool. Upload a contract, add signers and fields, and send the links. Each signer confirms a 6-digit email PIN and signs. The final PDF is sealed with an audit trail.",
    help: "You need to send a contract, sign one, or check that a PDF is genuine.",
  },
  {
    slug: "05-calendar-pools",
    title: "Calendar pools",
    summary: "A routing pool puts several hosts’ Cal.com calendars behind one booking link. Bookers pick a time, Motherboard picks a free host, and Cal.com sends the invite and Google Meet.",
    help: "You’re setting up a shared booking link or joining as a host.",
  },
];

export default function OnboardingVideosPage() {
  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="mb-8 sm:mb-10">
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-burgundy">bits&amp;bytes™ Motherboard</p>
        <h1 className="mt-2 font-display text-5xl uppercase leading-none text-dark sm:text-7xl">Onboarding videos</h1>
        <p className="mt-4 max-w-2xl font-heading text-base text-[#4f4c48] sm:text-lg">
          Five short videos, about 40 seconds each. Each one explains what a feature is, why we use it, and how it works. Stuck on something? Find the matching video below.
        </p>
        <nav aria-label="Videos" className="mt-6 flex flex-wrap gap-2">
          {VIDEOS.map((v, i) => (
            <a
              key={v.slug}
              href={`#${v.slug}`}
              className="rounded-md border-2 border-dark bg-white px-3 py-1.5 font-heading text-sm font-semibold text-dark shadow-light hover:bg-orange focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy"
            >
              {i + 1}. {v.title}
            </a>
          ))}
        </nav>
      </header>

      <ol className="flex flex-col gap-10 sm:gap-12">
        {VIDEOS.map((v, i) => (
          <li key={v.slug} id={v.slug} className="scroll-mt-6 rounded-md border-2 border-dark bg-white p-3 shadow-dark sm:p-5">
            <video
              className="aspect-video w-full rounded-sm border-2 border-dark bg-dark"
              controls
              playsInline
              preload="metadata"
              poster={`/onboarding/${v.slug}.jpg`}
            >
              <source src={`/onboarding/${v.slug}.mp4`} type="video/mp4" />
              Your browser can’t play this video. <a href={`/onboarding/${v.slug}.mp4`}>Download it</a> instead.
            </video>
            <div className="px-1 pt-4 sm:px-2">
              <h2 className="font-heading text-2xl font-extrabold text-dark sm:text-3xl">
                <span className="text-burgundy">{String(i + 1).padStart(2, "0")}</span> {v.title}
              </h2>
              <p className="mt-2 font-heading text-base leading-relaxed text-[#2b2824]">{v.summary}</p>
              <p className="mt-3 inline-block rounded-md bg-[#f8f1e7] px-3 py-1.5 font-heading text-sm text-dark">
                <strong>Watch this if:</strong> {v.help}
              </p>
            </div>
          </li>
        ))}
      </ol>

      <footer className="mt-12 font-heading text-sm text-[#4f4c48]">
        Still stuck? Ask in the bits&amp;bytes Discord or ping HQ.
      </footer>
    </main>
  );
}
