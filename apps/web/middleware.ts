// TODO: Wire up real auth middleware when backend is ready
export default function middleware() {
  // passthrough — no auth check yet
}

export const config = {
  matcher: ["/dashboard(.*)"],
};
