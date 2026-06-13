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
    async jwt({ token, account }) {
      if (account?.provider === "google" && account.id_token) {
        try {
          const res = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/auth/google`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ google_id_token: account.id_token }),
            }
          );
          if (res.ok) {
            const data = await res.json();
            token.backendAccessToken = data.access_token;
            token.backendRefreshToken = data.refresh_token;
            token.isNewUser = data.is_new_user;
            token.backendUser = data.user;
          }
        } catch {
          // token stays empty; AuthGuard will redirect to /login
        }
      }
      return token;
    },
    async session({ session, token }) {
      // Store backend data inside session.user — top-level session props are stripped by NextAuth v5
      if (session.user) {
        (session.user as any).backendAccessToken = token.backendAccessToken;
        (session.user as any).backendRefreshToken = token.backendRefreshToken;
        (session.user as any).isNewUser = token.isNewUser;
        (session.user as any).backendUser = token.backendUser;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
});

export const { GET, POST } = handlers;
