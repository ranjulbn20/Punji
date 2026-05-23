import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

const { handlers } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider === "google") {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/auth/google`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ google_id_token: account.id_token }),
          }
        );
        if (!res.ok) return false;
        const data = await res.json();
        (user as any).backendAccessToken = data.access_token;
        (user as any).backendRefreshToken = data.refresh_token;
        (user as any).isNewUser = data.is_new_user;
        (user as any).backendUser = data.user;
      }
      return true;
    },
    async jwt({ token, user }) {
      if (user) {
        token.backendAccessToken = (user as any).backendAccessToken;
        token.backendRefreshToken = (user as any).backendRefreshToken;
        token.isNewUser = (user as any).isNewUser;
        token.backendUser = (user as any).backendUser;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).backendAccessToken = token.backendAccessToken as string;
      (session as any).isNewUser = token.isNewUser as boolean;
      (session as any).backendUser = token.backendUser;
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
});

export const { GET, POST } = handlers;
