import NextAuth from "next-auth";

declare module "next-auth" {
  interface Session {
    backendAccessToken: string;
    isNewUser: boolean;
    backendUser?: { id: string; email: string; full_name?: string; onboarding_step: number };
  }
  interface User {
    backendAccessToken: string;
    backendRefreshToken: string;
    isNewUser: boolean;
    backendUser?: { id: string; email: string; full_name?: string; onboarding_step: number };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendAccessToken: string;
    backendRefreshToken: string;
    isNewUser: boolean;
    backendUser?: { id: string; email: string; full_name?: string; onboarding_step: number };
  }
}
