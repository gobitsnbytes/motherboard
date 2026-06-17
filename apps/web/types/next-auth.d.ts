import type { DefaultSession } from "next-auth";
import type { JWT } from "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    user: {
      discordId: string;
    } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    discordId: string;
    accessToken: string;
  }
}
