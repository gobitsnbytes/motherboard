import NextAuth from "next-auth";
import Discord from "next-auth/providers/discord";

export const { auth, handlers, signIn, signOut } = NextAuth({
  providers: [
    Discord({
      authorization: {
        params: {
          scope: "identify email guilds guilds.members.read",
        },
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, account, profile }) {
      token.discordId ??= "";
      token.accessToken ??= "";
      if (account && profile) {
        token.discordId = (profile as { id: string }).id;
        token.accessToken = account.access_token ?? "";

        // Fire-and-forget upsert to backend API
        const apiUrl = process.env.API_URL;
        const internalSecret = process.env.API_INTERNAL_SECRET;

        if (apiUrl && internalSecret) {
          fetch(`${apiUrl}/api/auth/upsert`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Internal-Secret": internalSecret,
            },
            body: JSON.stringify({
              discordId: (profile as { id: string }).id,
              email: (profile as { email?: string }).email,
              username: (profile as { username?: string }).username,
              avatar: (profile as { avatar?: string }).avatar,
              accessToken: account.access_token,
            }),
          }).catch(() => {
            // Silently ignore — never block sign-in on API failure
          });
        }
      }
      return token;
    },
    async session({ session, token }) {
      session.user.discordId = token.discordId;
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
});
