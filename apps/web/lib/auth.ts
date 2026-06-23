import NextAuth from "next-auth";
import Discord from "next-auth/providers/discord";

type DiscordProfile = {
  id: string;
  email?: string | null;
  username?: string | null;
  global_name?: string | null;
  avatar?: string | null;
};

async function upsertBackendUser(profile: DiscordProfile, accessToken?: string) {
  const apiUrl = process.env.API_URL;
  const internalSecret = process.env.API_INTERNAL_SECRET;

  if (!apiUrl || !internalSecret) {
    throw new Error("Backend auth bridge is not configured");
  }

  const response = await fetch(`${apiUrl}/api/auth/upsert`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Internal-Secret": internalSecret,
    },
    body: JSON.stringify({
      discord_id: profile.id,
      email: profile.email,
      username: profile.username,
      global_name: profile.global_name,
      avatar: profile.avatar,
      access_token: accessToken,
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to sync Discord identity with backend");
  }

  const data = (await response.json()) as { user_id?: string };
  if (!data.user_id) {
    throw new Error("Backend auth bridge did not return a user id");
  }

  return data.user_id;
}

export const { auth, handlers, signIn, signOut } = NextAuth({
  providers: [
    Discord({
      clientId: process.env.DISCORD_CLIENT_ID,
      clientSecret: process.env.DISCORD_CLIENT_SECRET,
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
      token.internalUserId ??= "";

      if (account && profile) {
        const discordProfile = profile as DiscordProfile;
        token.discordId = discordProfile.id;
        token.accessToken = account.access_token ?? "";
        token.internalUserId = await upsertBackendUser(
          discordProfile,
          account.access_token,
        );
      }

      return token;
    },
    async session({ session, token }) {
      session.user.discordId = token.discordId;
      session.user.internalUserId = token.internalUserId;
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
});
