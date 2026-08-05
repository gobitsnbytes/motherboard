import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { auth } from "./lib/auth";

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const isAuthPage = req.nextUrl.pathname === "/login";
  const isDashboardPage = req.nextUrl.pathname.startsWith("/dashboard") || req.nextUrl.pathname.startsWith("/finance");

  if (isAuthPage && isLoggedIn) {
    return NextResponse.redirect(new URL("/dashboard/overview", req.url));
  }

  if (isDashboardPage && !isLoggedIn) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
});

export const config = {
  matcher: ["/login", "/dashboard(.*)", "/finance(.*)"],
};
